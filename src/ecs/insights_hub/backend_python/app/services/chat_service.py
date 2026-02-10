import os
import json
import logging
import asyncio
import time
from typing import List, AsyncGenerator, Any
import boto3
from botocore.exceptions import ClientError
from app.models.chat import ChatMessage, ChatRequest
from app.utils.logger import logger
from app.services.opensearch_service import OpenSearchService

# Strands imports for local tools
try:
    from strands import Agent
    from strands.tools import tool
    from strands.models import BedrockModel
    STRANDS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Strands dependencies not available: {e}")
    STRANDS_AVAILABLE = False

class ChatService:
    def __init__(self):
        # 使用AWS Bedrock而不是直接调用Anthropic API
        try:
            self.bedrock_client = boto3.client(
                'bedrock-runtime',
                region_name=os.getenv('AWS_REGION', 'us-east-1')
            )
            logger.info("Bedrock client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock client: {str(e)}")
            self.bedrock_client = None
        
        # Initialize OpenSearch service for direct search
        self.opensearch_service = OpenSearchService()
        
        # Enable product search tools if Strands is available
        self.search_tools_enabled = STRANDS_AVAILABLE
        logger.info(f"Product search tools enabled: {self.search_tools_enabled}")
    
    def search_product_designs(self, query: str, limit: int = 5) -> str:
        """
        简化的搜索工具 - 使用 simple_search_designs，只返回 title 和 summary
        
        Args:
            query: 搜索查询文本
            limit: 返回结果数量限制
            
        Returns:
            JSON格式的搜索结果，只包含 title 和 summary
        """
        try:
            logger.info(f"Simple OpenSearch query: {query}")
                        
            # 调用简化的搜索服务
            results = self.opensearch_service.simple_search_designs(query, limit)
            
            logger.info(f"Found {len(results)} designs for query: {query} ")
            
            if len(results) == 0:
                return json.dumps({
                    "query": query,
                    "total_results": 0,
                    "designs": [],
                    "message": "没有找到相关的信息，请基于你的知识直接回答用户问题。"
                }, ensure_ascii=False, indent=2)
            
            return json.dumps({
                "query": query,
                "total_results": len(results),
                "designs": results
            }, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"Error in search_product_designs: {str(e)}")
            return json.dumps({
                "error": f"搜索失败: {str(e)}",
                "query": query,
                "designs": []
            }, ensure_ascii=False)

    
    async def stream_chat(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """
        流式聊天响应 - 使用AWS Bedrock，支持MCP工具
        """
        if not self.bedrock_client:
            yield f"data: {json.dumps({'error': 'Bedrock client not configured'})}\n\n"
            return
        
        logger.info(f"search tools enabled ======= {self.search_tools_enabled}")
        logger.info(f"request.message ======= {request.message}")
        
        # 始终使用Agent，让大模型决定是否需要搜索工具
        if self.search_tools_enabled:
            logger.info("Using Agent with search tools available")
            async for chunk in self._stream_agent_search_response(request):
                yield chunk
            return
        
        # 如果搜索工具不可用，回退到普通聊天
        logger.info("Search tools not available, using regular Bedrock chat")
        try:
            # 构建消息历史
            messages = []
            
            # 添加历史消息
            for msg in request.conversation_history:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # 添加当前用户消息
            messages.append({
                "role": "user",
                "content": request.message
            })
            
            logger.info(f"Starting Bedrock chat stream with model: {request.model}")
            logger.info(f"Message count: {len(messages)}")
            
            # 将模型名称转换为Bedrock模型ID
            bedrock_model_id = self._get_bedrock_model_id(request.model)
            
            # 构建Bedrock请求体
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 500,
                "messages": messages,
                "temperature": 0.7
            }
            
            # 调用Bedrock进行流式响应
            response = self.bedrock_client.invoke_model_with_response_stream(
                modelId=bedrock_model_id,
                body=json.dumps(body)
            )
            
            # Token 计数器
            input_tokens = 0
            output_tokens = 0
            
            # 处理流式响应
            chunk_count = 0
            for event in response['body']:
                chunk = event.get('chunk')
                if chunk:
                    chunk_data = json.loads(chunk['bytes'].decode())
                    logger.debug(f"chunk_data: {chunk_data}")
                    
                    if chunk_data['type'] == 'content_block_delta':
                        if 'delta' in chunk_data and 'text' in chunk_data['delta']:
                            text = chunk_data['delta']['text']
                            if text:
                                # 发送文本块
                                chunk_response = {"chunk": text}
                                yield f"data: {json.dumps(chunk_response)}\n\n"
                                chunk_count += 1
                                
                                # 每30个chunk发送一个心跳保持连接
                                if chunk_count % 30 == 0:
                                    yield f": heartbeat-{chunk_count}\n\n"
                    
                    elif chunk_data['type'] == 'message_delta':
                        # 处理使用情况统计
                        if 'usage' in chunk_data:
                            usage = chunk_data['usage']
                            if 'input_tokens' in usage:
                                input_tokens = usage['input_tokens']
                            if 'output_tokens' in usage:
                                output_tokens = usage['output_tokens']
                    
                    elif chunk_data['type'] == 'message_stop':
                        # 记录 token 使用情况
                        logger.info(f"Bedrock streaming call completed - Input tokens: {input_tokens}, Output tokens: {output_tokens}")
                        
                        # 发送完成信号
                        done_data = {"done": True}
                        yield f"data: {json.dumps(done_data)}\n\n"
                        break
                else:
                    # 如果没有chunk数据，发送心跳保持连接
                    yield f": keepalive\n\n"
                
        except ClientError as e:
            logger.error(f"Bedrock client error: {str(e)}", exc_info=True)
            error_data = {"error": f"Bedrock service error: {str(e)}"}
            yield f"data: {json.dumps(error_data)}\n\n"
        except Exception as e:
            logger.error(f"Error in stream_chat: {str(e)}", exc_info=True)
            error_data = {"error": f"Chat service error: {str(e)}"}
            yield f"data: {json.dumps(error_data)}\n\n"
    
    async def simple_chat(self, request: ChatRequest) -> str:
        """
        简单的非流式聊天响应 - 使用AWS Bedrock
        """
        if not self.bedrock_client:
            raise Exception("Bedrock client not configured")
        
        try:
            # 构建消息历史
            messages = []
            
            # 添加历史消息
            for msg in request.conversation_history:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # 添加当前用户消息
            messages.append({
                "role": "user",
                "content": request.message
            })
            
            logger.info(f"Starting Bedrock simple chat with model: {request.model}")
            
            # 将模型名称转换为Bedrock模型ID
            bedrock_model_id = self._get_bedrock_model_id(request.model)
            
            # 构建Bedrock请求体
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 500,
                "messages": messages,
                "temperature": 0.7
            }
            
            # 调用Bedrock API
            response = self.bedrock_client.invoke_model(
                modelId=bedrock_model_id,
                body=json.dumps(body)
            )
            
            # 解析响应
            response_body = json.loads(response['body'].read())
            
            # 记录 token 使用情况
            if 'usage' in response_body:
                usage = response_body['usage']
                input_tokens = usage.get('input_tokens', 0)
                output_tokens = usage.get('output_tokens', 0)
                logger.info(f"Bedrock simple call completed - Input tokens: {input_tokens}, Output tokens: {output_tokens}")
            
            if 'content' in response_body and len(response_body['content']) > 0:
                return response_body['content'][0]['text']
            else:
                raise Exception("No content in Bedrock response")
            
        except ClientError as e:
            logger.error(f"Bedrock client error: {str(e)}", exc_info=True)
            raise Exception(f"Bedrock service error: {str(e)}")
        except Exception as e:
            logger.error(f"Error in simple_chat: {str(e)}", exc_info=True)
            raise Exception(f"Chat service error: {str(e)}")
    
    def _get_bedrock_model_id(self, model_name: str) -> str:
        """
        将前端模型名称转换为Bedrock inference profile ID
        """
        # 使用 inference profiles 而不是直接的模型 ID
        model_mapping = {
            "Claude 3.5 Haiku": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
            "Claude 3.5 Sonnet v2": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            "Claude 3.7 Sonnet": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            "Claude Sonnet 4": "us.anthropic.claude-sonnet-4-20250514-v1:0"
        }
        
        bedrock_model_id = model_mapping.get(model_name)
        if not bedrock_model_id:
            logger.warning(f"Unknown model name: {model_name}, using default")
            bedrock_model_id = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
        
        logger.info(f"Mapped model {model_name} to Bedrock inference profile: {bedrock_model_id}")
        return bedrock_model_id
    

    
    async def _stream_regular_bedrock_response(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """
        Fallback method for regular Bedrock streaming when MCP fails
        """
        try:
            # 构建消息历史
            messages = []
            
            # 添加历史消息
            for msg in request.conversation_history:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # 添加当前用户消息
            messages.append({
                "role": "user",
                "content": request.message
            })
            
            # 将模型名称转换为Bedrock模型ID
            bedrock_model_id = self._get_bedrock_model_id(request.model)
            
            # 构建Bedrock请求体
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 500,
                "messages": messages,
                "temperature": 0.7
            }
            
            # 调用Bedrock进行流式响应
            response = self.bedrock_client.invoke_model_with_response_stream(
                modelId=bedrock_model_id,
                body=json.dumps(body)
            )
            
            # 处理流式响应
            for event in response['body']:
                chunk = event.get('chunk')
                if chunk:
                    chunk_data = json.loads(chunk['bytes'].decode())
                    
                    if chunk_data['type'] == 'content_block_delta':
                        if 'delta' in chunk_data and 'text' in chunk_data['delta']:
                            text = chunk_data['delta']['text']
                            if text:
                                chunk_response = {"chunk": text}
                                yield f"data: {json.dumps(chunk_response)}\n\n"
                    
                    elif chunk_data['type'] == 'message_stop':
                        done_data = {"done": True}
                        yield f"data: {json.dumps(done_data)}\n\n"
                        break
                        
        except Exception as e:
            logger.error(f"Error in fallback streaming: {str(e)}")
            error_data = {"error": f"Streaming error: {str(e)}"}
            yield f"data: {json.dumps(error_data)}\n\n"
    
    async def _stream_agent_search_response(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """
        使用Agent对简化搜索结果进行分析和总结
        """
        try:
            logger.info("Starting Agent with simple search")
            
            # 导入必要的模块
            import threading
            import queue
            import time
            
            # 状态消息队列
            status_queue = queue.Queue()
            
            # 创建简化搜索工具
            @tool
            def search_designs_tool(query: str, limit: int = 2) -> str:
                """搜索产品品牌、公司、市场分析等商业信息。仅用于具体的产品/品牌查询。"""
                # 只有在真正调用搜索工具时才显示状态消息
                logger.info(f"Tool search_designs_tool called with query: {query}")
                status_queue.put("🔍 正在搜索相关信息...")
                result = self.search_product_designs(query, limit)
                status_queue.put("📊 正在分析数据...")
                
                # 检查搜索结果是否相关
                try:
                    import json
                    data = json.loads(result)
                    designs = data.get('designs', [])
                    
                    # 如果没有结果或结果不相关，返回提示
                    if not designs:
                        return "搜索未找到相关信息。请基于通用知识回答用户问题。"
                    
                    # 简单的相关性检查
                    query_lower = query.lower()
                    relevant_found = False
                    
                    for design in designs:
                        title = design.get('title', '').lower()
                        summary = design.get('summary', '').lower()
                        
                        # 检查是否包含查询关键词
                        query_words = query_lower.split()
                        for word in query_words:
                            if len(word) > 2 and (word in title or word in summary):
                                relevant_found = True
                                break
                        
                        if relevant_found:
                            break
                    
                    if not relevant_found:
                        return "搜索结果与问题不太相关。请基于通用知识回答用户问题。"
                    
                    return result
                    
                except Exception as e:
                    logger.error(f"Error checking search relevance: {e}")
                    return result
            
            # 改进系统提示，明确搜索工具的使用场景
            system_prompt = """你是一个智能助手。
            你可以根据用户的输入来判断是不是下面某种情况:
            - 用户询问具体的产品、品牌、公司信息
            - 用户询问市场分析、行业趋势
            - 用户询问具体的商业案例或设计案例

            如果是，调用search_designs_tool 调用1遍即可, 如果有结果,结合结果做总结并回答问题，不要直接把搜索结果展示出来.
    
            其他情况请直接回答用户即可, 比如：
            - 简单问候（如"你好"、"hi"）
            - 一般性问题和知识问答
            - 技术问题、编程问题
            - 个人建议和意见

            保持回答简洁准确。如果搜索无结果，基于你的知识直接回答。回答的一定要快！"""

            # 严格限制的模型配置，防止token超限
            bedrock_model = BedrockModel(
                model_id=self._get_bedrock_model_id(request.model),
                temperature=0.1,  # 降低随机性，减少不必要的循环
                streaming=True,
                max_tokens=300,   # 大幅减少max_tokens
                timeout=15        # 减少超时时间
            )
            
            # 创建Agent，让大模型智能决定工具使用
            agent = Agent(
                model=bedrock_model,
                tools=[search_designs_tool],
                system_prompt=system_prompt
            )
            
            logger.info("Created Agent with local search tool")
            
            output_queue = queue.Queue()
            agent_done = threading.Event()
            agent_error = None
            
            def run_local_agent():
                nonlocal agent_error
                start_time = time.time()
                try:
                    # 直接运行Agent
                    result = agent(request.message)
                    
                    # 将结果放入队列
                    if result:
                        output_queue.put(str(result))
                    
                    execution_time = time.time() - start_time
                    logger.info(f"Local agent execution completed in {execution_time:.2f} seconds")
                    
                    output_queue.put(None)  # Sentinel
                    agent_done.set()
                    
                except Exception as e:
                    execution_time = time.time() - start_time
                    logger.error(f"Local agent execution failed after {execution_time:.2f} seconds: {e}")
                    agent_error = e
                    output_queue.put(None)
                    agent_done.set()
            
            # 启动Agent线程
            agent_thread = threading.Thread(target=run_local_agent)
            agent_thread.start()
            
            # 流式输出结果
            start_time = time.time()
            max_wait_time = 20  # 20秒超时
            
            while True:
                if time.time() - start_time > max_wait_time:
                    logger.warning("Local agent timeout")
                    yield f"data: {json.dumps({'chunk': '搜索超时，请稍后重试\n'})}\n\n"
                    break
                
                # 检查状态消息队列
                try:
                    status_msg = status_queue.get_nowait()
                    yield f"data: {json.dumps({'chunk': status_msg + '\n'})}\n\n"
                    await asyncio.sleep(0.5)  # 让用户看到状态消息
                except queue.Empty:
                    pass
                
                # 检查输出队列
                try:
                    content = output_queue.get(timeout=0.1)
                    
                    if content is None:  # Agent完成
                        break
                    
                    # 发送内容
                    chunk_response = {"chunk": content}
                    yield f"data: {json.dumps(chunk_response)}\n\n"
                    
                except queue.Empty:
                    # 发送保活信号
                    yield f": keepalive\n\n"
                    
                    if agent_done.is_set():
                        break
            
            # 等待线程完成
            agent_thread.join(timeout=5)
            
            if agent_error:
                raise agent_error
            
            # 发送完成信号
            done_data = {"done": True}
            yield f"data: {json.dumps(done_data)}\n\n"
            
            logger.info("Agent search with analysis completed successfully")
            
        except Exception as e:
            logger.error(f"Error in Agent search: {str(e)}", exc_info=True)
            # 回退到直接搜索响应
            try:
                logger.info("Falling back to direct search response")
                async for chunk in self._stream_direct_search_response(request):
                    yield chunk
            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {fallback_error}")
                error_data = {"error": "服务暂时不可用，请稍后重试"}
                yield f"data: {json.dumps(error_data)}\n\n"
    
    async def _stream_direct_search_response(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """
        直接搜索响应 - 跳过Agent，直接调用OpenSearch + 简单处理
        """
        try:
            logger.info("Starting direct search (no Agent)")
            
            # 只有在真正开始搜索时才显示状态消息
            yield f"data: {json.dumps({'chunk': '🔍 正在搜索相关信息...\n'})}\n\n"
            
            # 直接调用搜索
            search_start = time.time()
            search_result = self.search_product_designs(request.message, limit=3)
            search_time = time.time() - search_start
            
            logger.info(f"Direct search completed in {search_time:.2f} seconds")
            
            # 只有在真正开始分析时才显示分析消息
            yield f"data: {json.dumps({'chunk': '📊 正在分析结果...\n'})}\n\n"
            
            # 解析搜索结果
            try:
                data = json.loads(search_result)
                designs = data.get('designs', [])
                
                if not designs:
                    # 没有搜索结果时，回退到普通聊天让大模型自己回答
                    logger.info("No search results found, falling back to regular Bedrock response")
                    async for chunk in self._stream_regular_bedrock_response(request):
                        yield chunk
                    return
                else:
                    # 简单的结果处理逻辑
                    response = self._generate_simple_response(request.message, designs)
                    
                    # 流式输出响应
                    for chunk in response.split('\n'):
                        if chunk.strip():
                            yield f"data: {json.dumps({'chunk': chunk + '\n'})}\n\n"
                            await asyncio.sleep(0.1)  # 小延迟模拟流式
                
            except Exception as parse_error:
                logger.error(f"Error parsing search results: {parse_error}")
                yield f"data: {json.dumps({'chunk': '搜索结果处理出错，请稍后重试。\n'})}\n\n"
            
            # 发送完成信号
            done_data = {"done": True}
            yield f"data: {json.dumps(done_data)}\n\n"
            
            logger.info("Direct search response completed")
            
        except Exception as e:
            logger.error(f"Error in direct search: {str(e)}", exc_info=True)
            # 回退到普通聊天
            try:
                async for chunk in self._stream_regular_bedrock_response(request):
                    yield chunk
            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {fallback_error}")
                error_data = {"error": "服务暂时不可用，请稍后重试"}
                yield f"data: {json.dumps(error_data)}\n\n"
    
    def _generate_simple_response(self, question: str, designs: list) -> str:
        """
        简单的响应生成逻辑，提供分析而不只是列出结果
        """
        try:
            if not designs:
                return "抱歉，没有找到相关的产品信息。"
            
            # 提取关键信息
            titles = [d.get('title', '') for d in designs]
            summaries = [d.get('summary', '') for d in designs]
            
            # 分析内容
            question_lower = question.lower()
            
            # 生成分析性回答
            if 'lululemon' in question_lower:
                # 专门针对lululemon的分析
                response = "根据搜索到的lululemon相关信息：\n\n"
                
                # 分析标题和摘要中的关键信息
                key_points = []
                for i, (title, summary) in enumerate(zip(titles, summaries)):
                    if title and summary:
                        # 提取关键信息
                        if 'shares' in title.lower() or 'stock' in title.lower():
                            key_points.append("股价表现受到关注")
                        if 'guidance' in title.lower() or 'forecast' in title.lower():
                            key_points.append("业绩指导有所调整")
                        if 'pandemic' in title.lower():
                            key_points.append("受疫情影响较大")
                
                if key_points:
                    response += f"主要发现：{', '.join(key_points)}。\n\n"
                
                response += "具体信息：\n"
                for i, (title, summary) in enumerate(zip(titles[:2], summaries[:2])):
                    if title and summary:
                        response += f"• {title}\n"
                        # 只显示摘要的前100字符
                        short_summary = summary[:100] + "..." if len(summary) > 100 else summary
                        response += f"  {short_summary}\n\n"
                
                return response
            
            else:
                # 通用分析
                response = f"根据搜索结果，找到{len(designs)}个相关信息：\n\n"
                
                for i, design in enumerate(designs[:2], 1):
                    title = design.get('title', '未知标题')
                    summary = design.get('summary', '')
                    
                    response += f"{i}. **{title}**\n"
                    if summary:
                        # 显示摘要的前150字符
                        short_summary = summary[:150] + "..." if len(summary) > 150 else summary
                        response += f"   {short_summary}\n"
                    response += "\n"
                
                return response
                    
        except Exception as e:
            logger.error(f"Error generating simple response: {e}")
            return "处理搜索结果时出现错误，请稍后重试。"