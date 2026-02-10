import json
import logging
from typing import Any

from strands import Agent
# from strands_tools import mem0_memory
from strands.tools.mcp import MCPClient
from strands.handlers.callback_handler import (
    CompositeCallbackHandler,
    PrintingCallbackHandler,
)
from strands.models import BedrockModel


import boto3
from mcp.client.streamable_http import streamablehttp_client

# Configure logging
logging.basicConfig(
    level=logging.WARNING, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

client_cloudfront_url = "https://dl4z093ct08bc.cloudfront.net/mcp/"  # must have this backslash for now

secret_name = "MCPServerAPIKey0B7E869D-qVgQOKvRIKcG"

sys_prompt = question = """你是一个专业的产品洞察分析师。我需要你帮我分析特定主题的产品洞察并制作演示内容。

## 工作流程：

### 步骤1：智能查询
根据我的输入，使用 `find_documents_with_similar_summaries` 工具查询相关文档：
- 查询文本：使用我提供的关键词和描述
- 文档数量：获取10-15个最相关的文档
- 行业过滤：如果我提到特定行业（furniture/fashion/car），请使用industry参数

### 步骤2：深度分析
分析返回文档的以下字段：
- `summary`：产品核心洞察
- `mainContentHTML`：详细产品信息
- `keywords`：相关标签和特征
- 其他元数据字段

### 步骤3：PPT内容生成
创建5页专业PPT内容：

**第1页：执行摘要**
- 标题：[主题] 产品洞察报告
- 核心发现（3-4点）
- 分析范围和数据来源
- 关键数字或统计

**第2页：市场趋势**
- 标题：当前市场趋势
- 主要趋势（4-5个）
- 趋势驱动因素
- 市场机会点

**第3页：产品洞察**
- 标题：产品特征与创新点
- 热门产品特征
- 创新设计元素
- 用户需求分析
- 价格策略洞察

**第4页：竞争分析**
- 标题：竞争格局与定位
- 主要竞争维度
- 差异化策略
- 市场空白点
- 品牌定位机会

**第5页：战略建议**
- 标题：行动计划与建议
- 短期行动项（1-3个月）
- 中期策略（3-6个月）
- 长期规划（6-12个月）
- 成功指标

## 输出要求：
✅ 每页使用 "## 第X页：[标题]" 格式
✅ 要点使用 "- " 项目符号
✅ 每个要点简洁有力（1-2行）
✅ 包含具体例子和数据
✅ 使用商业专业术语
✅ 突出可执行的洞察

现在请开始分析我的查询：[用户输入]

"""

def get_secret_api_key(secret_name: str) -> str:
    """
    Retrieves an API key from AWS Secrets Manager.

    Args:
        secret_name: The name of the secret in AWS Secrets Manager

    Returns:
        The API key stored in the secret
    """
    logging.info(f"Retrieving secret {secret_name} from AWS Secrets Manager")
    # Create a Secrets Manager client
    session = boto3.session.Session()

    client = session.client(
        service_name="secretsmanager", region_name=session.region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secret = get_secret_value_response["SecretString"]
        logging.info("Successfully retrieved secret")
        return json.loads(secret)["api-key"]
    except Exception as e:
        logging.error(f"Error retrieving secret: {str(e)}")
        raise


def interactive_session():
    print("Demo News Agent (type 'exit' to quit)")
    print("-----------------------------------------------------------")

    AUTH_TOKEN = get_secret_api_key(
        secret_name,
    )
    logging.info("Retrieved API key from AWS Secrets Manager")

    aws_docs_client = MCPClient(
        lambda: streamablehttp_client(
            client_cloudfront_url, headers={f"Authorization": f"Bearer {AUTH_TOKEN}"}
        )
    )
    logging.info("Initialized MCP client")

    with aws_docs_client:
        logging.info("Setting up Agent with tools and system prompt")

        # Bedrock model
        bedrock_model = BedrockModel(
            model_id="us.amazon.nova-pro-v1:0",
            temperature=0.3,
            streaming=True,  # Enable/disable streaming
        )
        agent = Agent(model=bedrock_model, tools=aws_docs_client.list_tools_sync(), system_prompt=sys_prompt)

        # This agent will use default model, which is Claude 3.7 sonnet
        # agent = Agent(tools=aws_docs_client.list_tools_sync(), system_prompt=sys_prompt)


        while True:
            # Get user input
            user_input = input("\nYour question: ")
            if user_input.strip() == "":
                print("Empty input detected, please enter valid text.")
                continue
            agent(user_input)



if __name__ == "__main__":
    interactive_session()