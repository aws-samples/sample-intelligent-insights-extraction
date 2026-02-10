import boto3
import json
from typing import Dict, List, Any, Optional
from app.core.config import settings
from app.utils.logger import logger
from app.utils.mock_data import mock_designs
from app.utils.bedrock_embedding import get_embedding_from_text, get_bedrock_runtime_client
from app.models.design import Design, DesignDetail
from opensearchpy import RequestsHttpConnection, AWSV4SignerAuth, OpenSearch
import datetime

_opensearch_client = None


class OpenSearchService:
    def __init__(self):
        self.region = settings.AWS_REGION
        self.collection_endpoint = settings.OPENSEARCH_COLLECTION_ENDPOINT
        self.index_name = settings.OPENSEARCH_INDEX

    def _create_client(self):
        """
        Create and return an OpenSearch client using environment variables
        This is implemented as a singleton pattern to avoid creating multiple clients.

        This function creates an authenticated connection to the OpenSearch
        serverless collection using AWS SigV4 authentication. It reads the
        endpoint from environment variables.

        Returns:
            OpenSearch: Configured OpenSearch client ready to use

        Environment Variables:
            OPENSEARCH_ENDPOINT: The host endpoint for OpenSearch
            AWS_REGION: The AWS region (defaults to us-east-1)
        """
        global _opensearch_client

        # Return existing client if already initialized
        if _opensearch_client is not None:
            return _opensearch_client

        host = self.collection_endpoint
        region = self.region

        service = "aoss"  # Amazon OpenSearch Serverless service name for SigV4
        credentials = boto3.Session().get_credentials()
        auth = AWSV4SignerAuth(credentials, region, service)

        _opensearch_client = OpenSearch(
            hosts=[{"host": host[8:], "port": 443}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=300,  # Increased timeout for potentially large operations
            pool_maxsize=20,
        )

        return _opensearch_client

    def _transform_opensearch_data(self, hit: Dict[str, Any]) -> Design:
        source = hit.get("_source", {})

        # 查找第一个in_main_content为True的图片
        images = source.get("images", [])
        main_image = next((img for img in images if img.get("in_main_content") is True), None)

        # 如果没有找到主图片，使用基于大小的选择逻辑
        if not main_image and images:
            # 查找第一个size大于21000的图片
            large_image = next((img for img in images if img.get("size", 0) > 21000), None)

            if large_image:
                main_image = large_image
            else:
                # 如果都不大于21000，则使用第一张图片
                main_image = images[0]

        # Log the selected image for debugging
        if main_image:
            logger.info(f"Selected main image URL: {main_image.get('original_url', 'No URL')}")

        # Import all model classes
        from app.models.design import (
            TargetUsers, BasicProductInfo, ProductDependencies,
            PricingInfo, ProductInnovation, DurabilityInfo,
            MarketInfo, SupplyChainInfo
        )

        # Extract Target Users and Application Scenarios
        target_users_data = source.get("Target Users and Application Scenarios", {})
        target_users = None
        if target_users_data:
            target_users = TargetUsers(
                mainConsumers=target_users_data.get("mainConsumers", ""),
                applicationScenarios=target_users_data.get("applicationScenarios", "")
            )

        # Extract Basic Product Information
        basic_product_data = source.get("Basic Product Information", {})
        basic_product_info = None
        if basic_product_data:
            basic_product_info = BasicProductInfo(
                coreFunctions=basic_product_data.get("coreFunctions", ""),
                materialsSpecs=basic_product_data.get("materialsSpecs", ""),
                imagesDescriptions=basic_product_data.get("imagesDescriptions", "")
            )

        # Extract Product Dependencies
        dependencies_data = source.get("Product Dependencies and Complementary Needs", {})
        product_dependencies = None
        if dependencies_data:
            product_dependencies = ProductDependencies(
                independentUsage=dependencies_data.get("independentUsage", True),
                essentialAccessories=dependencies_data.get("essentialAccessories", []),
                recommendedComplements=dependencies_data.get("recommendedComplements", []),
                relatedPrompts=dependencies_data.get("relatedPrompts", "")
            )

        # Extract Pricing Information
        pricing_data = source.get("Pricing and Competitive Landscape", {})
        pricing_info = None
        if pricing_data:
            pricing_info = PricingInfo(
                price=pricing_data.get("price", ""),
                salesVolume=pricing_data.get("salesVolume", ""),
                competitionSection=pricing_data.get("competitionSection", ""),
                priceDifferentiators=pricing_data.get("priceDifferentiators", [])
            )

        # Extract Product Innovation
        innovation_data = source.get("Product Innovation and Differentiation", {})
        product_innovation = None
        if innovation_data:
            product_innovation = ProductInnovation(
                innovations=innovation_data.get("innovations", ""),
                differentiation=innovation_data.get("differentiation", ""),
                patentOrExclusive=innovation_data.get("patentOrExclusive", "")
            )

        # Extract Durability Information
        durability_data = source.get("Durability and Environmental Attributes", {})
        durability_info = None
        if durability_data:
            # Combine environmentalMaterials and environmentalCerts into environmentalInfo
            environmental_materials = durability_data.get("environmentalMaterials", "")
            environmental_certs = durability_data.get("environmentalCerts", "")

            # If both fields exist, combine them
            environmental_info = ""
            if environmental_materials and environmental_certs:
                environmental_info = f"{environmental_materials}. {environmental_certs}"
            elif environmental_materials:
                environmental_info = environmental_materials
            elif environmental_certs:
                environmental_info = environmental_certs
            else:
                # Check if the new combined field exists directly
                environmental_info = durability_data.get("environmentalInfo", "")

            # Get durability information
            durability = durability_data.get("durability", "")

            # Format durability to highlight estimated lifespan if it exists
            if durability:
                # Check if durability already contains an estimated lifespan
                lifespan_patterns = [
                    r'\d+[-–]\d+\s*years?',
                    r'\d+\s*years?',
                    r'\d+,\d+\s*hours?',
                    r'\d+,\d+\s*cycles?',
                    r'\d+\s*cycles?',
                    r'\d+\s*operations?'
                ]

                import re
                has_lifespan = any(re.search(pattern, durability, re.IGNORECASE) for pattern in lifespan_patterns)

                # If no lifespan is found, try to infer one based on other durability information
                if not has_lifespan and ("resistant" in durability or "durable" in durability):
                    if "highly" in durability or "very" in durability:
                        durability = "Estimated lifespan of 5+ years with normal use. " + durability
                    else:
                        durability = "Estimated lifespan of 3-5 years with normal use. " + durability

            durability_info = DurabilityInfo(
                durability=durability,
                environmentalInfo=environmental_info
            )

        # Extract User Feedback Information
        from app.models.design import UserFeedbackInfo
        user_feedback_data = source.get("User Concerns and Feedback", {})
        user_feedback_info = None

        if user_feedback_data:
            user_feedback_info = UserFeedbackInfo(
                userConcerns=user_feedback_data.get("userConcerns", ""),
                commonIssues=user_feedback_data.get("commonIssues", ""),
                positiveHighlights=user_feedback_data.get("positiveHighlights", "")
            )
        else:
            # For backward compatibility, check if userConcerns exists in durability_data
            user_concerns = durability_data.get("userConcerns", "") if durability_data else ""
            if user_concerns:
                user_feedback_info = UserFeedbackInfo(
                    userConcerns=user_concerns,
                    commonIssues="",
                    positiveHighlights=""
                )

        # Extract Market Information
        market_data = source.get("Market Opportunities and Risks", {})
        market_info = None
        if market_data:
            market_info = MarketInfo(
                opportunities=market_data.get("opportunities", ""),
                risks=market_data.get("risks", "")
            )

        # Extract Supply Chain Information
        supply_data = source.get("Supply Chain and Inventory", {})
        supply_chain_info = None
        if supply_data:
            supply_chain_info = SupplyChainInfo(
                inventory=supply_data.get("inventory", ""),
                supplyStability=supply_data.get("supplyStability", "")
            )

        return Design(
            id=hit.get("_id", "").replace("%3A", ":"),
            title=source.get("title", ""),
            description=source.get("summary", ""),
            imageUrl=main_image.get("original_url", "") if main_image else "",
            tags=source.get("keywords", []),
            s3Path=main_image.get("local_path", "") if main_image else "",
            industryFigures=source.get("industryFigures", []),
            source=source.get("source", ""),
            company=source.get("company", ""),
            industry=source.get("industry", ""),
            contentType=source.get("contentType", ""),
            publicationDate=source.get("publicationDate", ""),
            technicalFocus=source.get("technicalFocus", ""),
            applicationAreas=source.get("applicationAreas", ""),
            mainContentHTML=source.get("mainContentHTML", ""),
            targetUsers=target_users,
            basicProductInfo=basic_product_info,
            productDependencies=product_dependencies,
            pricingInfo=pricing_info,
            productInnovation=product_innovation,
            durabilityInfo=durability_info,
            marketInfo=market_info,
            supplyChainInfo=supply_chain_info,
            userFeedbackInfo=user_feedback_info
        )

    def get_all_designs(self, tag: Optional[str] = None, limit: int = 20, page: int = 1) -> List[Design]:
        """获取所有设计，可选择按标签过滤"""
        try:
            client = self._create_client()
            if not client:
                logger.warning("Using mock data due to client creation failure")
                return []

            query = {
                "_source": {
                    "excludes": ["content_vector"]
                },
                "size": 100,
                "query": {
                    "bool": {
                      "must_not": [{
                        "term": {
                          "title.keyword": "unknown"
                        }
                      },
                      {
                        "term": {
                          "summary.keyword": ""
                        }
                      }
                      ]
                    }
                }
            }

            try:
                response = client.search(body=query, index=self.index_name)

                if response:
                    return [self._transform_opensearch_data(hit) for hit in response["hits"]["hits"]]
                else:
                    logger.warning("OpenSearch response is empty or invalid")
                    return []

            except Exception as search_error:
                logger.error(f"OpenSearch search error: {str(search_error)}")
                return []

        except Exception as e:
            logger.error(f"Error in get_all_designs service: {str(e)}")
            raise

    def get_design_by_id(self, design_id: str) -> Optional[DesignDetail]:
        """Get design by id"""
        try:
            logger.info("design_id is %s", design_id)
            client = self._create_client()
            if not client:
                logger.warning("Using mock data due to client creation failure")
                return None

            try:
                response = client.get(index=self.index_name, id=design_id)
                if response:
                    if response["found"]:
                        design = self._transform_opensearch_data(response)
                        source = response.get("_source", {})
                        images = source.get("images", [])
                        related_images = [img.get("original_url", "") for img in images if
                                          img.get("original_url") and img.get("in_main_content") is False]
                        logger.info(f"related_images : {related_images}")
                        return DesignDetail(
                            **design.model_dump(),
                            relatedImages=related_images,
                            originalUrl=source.get("original_url", ""),
                            timeUpdated=source.get("time_updated", ""),
                        )
                    else:
                        logger.warning(f"No design found with ID: {design_id}")
                        return None
                else:
                    logger.warning("OpenSearch response is empty or invalid")
                    return None

            except Exception as search_error:
                logger.error(f"OpenSearch search error: {str(search_error)}")
                return None

        except Exception as e:
            logger.error(f"Error in get_design_by_id service: {str(e)}")
            raise

    def search_designs(self, query: str) -> List[Design]:
        """通过查询字符串搜索设计"""
        try:
            client = self._create_client()
            if not client:
                logger.warning("Using mock data due to client creation failure")
                return []

            embedding = get_embedding_from_text(query)

            search_query = {
                "query": {
                    "bool": {
                        "must": {
                            "knn": {
                                "content_vector": {
                                    "vector": embedding,
                                    "k": 5
                                }
                            }
                        },
                        "filter": [
                            {
                                "exists": {
                                    "field": "summary"
                                }
                            },
                            {
                                "bool": {
                                    "must_not": [{
                                        "term": {
                                        "title.keyword": "unknown"
                                        }
                                    },
                                    {
                                        "term": {
                                        "summary.keyword": ""
                                        }
                                    }
                                    ]
                                }
                            }
                        ]
                    }
                },
                "_source": {
                    "excludes": ["content_vector"]
                }
            }


            try:
                response = client.search(body=search_query, index=self.index_name)

                if response:
                    return [self._transform_opensearch_data(hit) for hit in response["hits"]["hits"]]
                else:
                    logger.warning("OpenSearch response is empty or invalid")
                    return []

            except Exception as search_error:
                logger.error(f"OpenSearch search error: {str(search_error)}")
                return []

        except Exception as e:
            logger.error(f"Error in search_designs: {str(e)}")
            raise

    def favorite_designs(self, design_id: str, user_name: str) -> str:
        """通过查询字符串搜索设计"""
        try:
            client = self._create_client()
            if not client:
                logger.warning("Using mock data due to client creation failure")
                return "Using mock data due to client creation failure"
            try:
                # Add time_updated timestamp for updates
                search_response = client.get(index=self.index_name, id=design_id)
                source = search_response.get("_source", {})

                favoriteUsers = source.get("favoriteUsers", "")
                if not favoriteUsers:
                    source["favoriteUsers"] = user_name
                else:
                    if user_name in favoriteUsers:
                        return "Already favorite this design."
                    source["favoriteUsers"] = favoriteUsers + "," + user_name
                source["time_updated"] = datetime.datetime.now().isoformat()

                # Update the existing document
                response = client.update(
                    index=self.index_name, id=design_id, body={"doc": source}
                )

                if response:
                    logger.info(f"OpenSearch favorite design was updated! favoriteUsers = {source['favoriteUsers']}")
                    return "Favorite design successfully."
                else:
                    logger.warning("OpenSearch response is empty or invalid")
                    return "OpenSearch response is empty or invalid"

            except Exception as search_error:
                logger.error(f"OpenSearch search error: {str(search_error)}")
                return str(search_error)

        except Exception as e:
            logger.error(f"Error in favorite_designs: {str(e)}")
            raise

    def search_favorite_designs(self, user_name: str) -> List[Design]:
        try:
            client = self._create_client()
            if not client:
                logger.warning("Using mock data due to client creation failure")
                return []

            query = {
                "query": {
                    "wildcard": {
                        "favoriteUsers": f"*{user_name}*"
                    }
                },
                "_source": {
                    "excludes": ["content_vector"]
                }
            }

            try:
                response = client.search(body=query, index=self.index_name)

                if response:
                    return [self._transform_opensearch_data(hit) for hit in response["hits"]["hits"]]
                else:
                    logger.warning("OpenSearch response is empty or invalid")
                    return []

            except Exception as search_error:
                logger.error(f"OpenSearch search error: {str(search_error)}")
                return []

        except Exception as e:
            logger.error(f"Error in search_favorite_designs: {str(e)}")
            raise

    def simple_search_designs(self, query: str, limit: int = 3, min_score: float = 1.35) -> List[Dict[str, str]]:
        """
        简化的设计搜索函数，只返回 title 和 summary 字段，并过滤低相关性结果

        Args:
            query: 搜索查询字符串
            limit: 返回结果数量限制，默认5条
            min_score: 最小相关性分数阈值，默认0.5（保守设置，确保有足够结果）
            
        Returns:
            List[Dict[str, str]]: 包含 title、summary 和 score 的字典列表
        """
        try:
            client = self._create_client()
            if not client:
                logger.warning("OpenSearch client creation failed")
                return []

            # 获取查询的向量嵌入
            embedding = get_embedding_from_text(query)

            search_query = {
                "size": limit,  # 获取更多结果用于过滤
                "min_score": min_score,  # 设置最小分数阈值
                "query": {
                    "bool": {
                        "must": {
                            "knn": {
                                "content_vector": {
                                    "vector": embedding,
                                    "k": limit * 2
                                }
                            }
                        },
                        "filter": [
                            {
                                "exists": {
                                    "field": "summary"
                                }
                            },
                            {
                                "bool": {
                                    "must_not": [
                                        {
                                            "term": {
                                                "summary.keyword": ""
                                            }
                                        },
                                        {
                                            "term": {
                                                "title.keyword": "unknown"
                                            }
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                },
                "_source": ["title", "summary"]  # 只返回这两个字段
            }

            try:
                response = client.search(body=search_query, index=self.index_name)

                if response and "hits" in response:
                    results = []
                    for hit in response["hits"]["hits"]:
                        # 检查分数阈值
                        score = hit.get("_score", 0)
                        logger.info(f"_score === {score}")
                        if score >= min_score:
                            source = hit.get("_source", {})
                            results.append({
                                "title": source.get("title", ""),
                                "summary": source.get("summary", ""),
                                "score": score  # 添加分数用于调试
                            })
                    
                    # 限制返回结果数量
                    results = results[:limit]
                    
                    logger.info(f"Found {len(results)} results with score >= {min_score} for query: {query}")
                    return results
                else:
                    logger.warning("OpenSearch response is empty or invalid")
                    return []

            except Exception as search_error:
                logger.error(f"OpenSearch search error: {str(search_error)}")
                return []

        except Exception as e:
            logger.error(f"Error in simple_search_designs: {str(e)}")
            return []
