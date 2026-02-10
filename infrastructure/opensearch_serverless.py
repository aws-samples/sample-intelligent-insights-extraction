import json
from typing import Optional

from aws_cdk import (
    aws_opensearchserverless as opensearchserverless,
    aws_ec2 as ec2,
    aws_iam as iam,
    CfnOutput,
    Aws,
    Stack,
    aws_lambda as lambda_,
    RemovalPolicy,
)
from constructs import Construct


class OpenSearchServerless(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.Vpc,
        index_name: str = "news",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id)

        self._stack = Stack.of(self)

        # Get private subnets
        private_subnets = vpc.select_subnets(
            subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
        ).subnets

        # Create security group for OpenSearch
        security_group = ec2.SecurityGroup(
            self,
            "OpenSearchSG",
            vpc=vpc,
            description="Security group for OpenSearch Serverless",
            allow_all_outbound=True,
        )

        # Allow HTTPS traffic on port 443
        security_group.add_ingress_rule(
            ec2.Peer.ipv4(vpc.vpc_cidr_block), ec2.Port.tcp(443), "Allow HTTPS from VPC"
        )

        # Create OpenSearch Serverless Collection
        collection_name = f"{Stack.of(self).stack_name}-collection"
        self.collection = opensearchserverless.CfnCollection(
            self,
            "OpenSearchCollection",
            name=collection_name,
            type="VECTORSEARCH",
            description="OpenSearch Serverless Collection for content with vector search",
        )
        self.collection.apply_removal_policy(RemovalPolicy.DESTROY)

        # Create VPC Endpoint for OpenSearch
        vpc_endpoint = opensearchserverless.CfnVpcEndpoint(
            self,
            "OpenSearchVpcEndpoint",
            name=f"{self._stack.stack_name}-aoss",
            vpc_id=vpc.vpc_id,
            subnet_ids=[subnet.subnet_id for subnet in private_subnets],
            security_group_ids=[security_group.security_group_id],
        )

        vpc_endpoint.apply_removal_policy(RemovalPolicy.DESTROY)

        # Instead of creating a direct circular dependency, we'll ensure proper deletion
        # order by making network_policy depend on both resources

        # Create network policy to allow access from the VPC
        network_policy = opensearchserverless.CfnSecurityPolicy(
            self,
            "NetworkPolicy",
            name=f"{self._stack.stack_name}-network",
            type="network",
            description="network policy for news database",
            policy=json.dumps(
                [
                    {
                        "Rules": [
                            {
                                "ResourceType": "collection",
                                "Resource": [f"collection/{self.collection.name}"],
                            },
                        ],
                        "AllowFromPublic": True,
                    },
                    {
                        "Rules": [
                            {
                                "ResourceType": "dashboard",
                                "Resource": [f"collection/{self.collection.name}"],
                            }
                        ],
                        "AllowFromPublic": True,
                    },
                ]
            ),
        )

        # Create encryption policy
        encryption_policy = opensearchserverless.CfnSecurityPolicy(
            self,
            "EncryptionPolicy",
            name=f"{self._stack.stack_name}-enc",
            type="encryption",
            policy=json.dumps(
                {
                    "Rules": [
                        {
                            "ResourceType": "collection",
                            "Resource": [f"collection/{self.collection.name}"],
                        }
                    ],
                    "AWSOwnedKey": True,
                }
            ),
        )

        # Create data access policy
        self.data_access_policy = opensearchserverless.CfnAccessPolicy(
            self,
            "DataAccessPolicy",
            name=f"{self._stack.stack_name}-data",
            type="data",
            policy=json.dumps(
                [
                    {
                        "Rules": [
                            {
                                "Resource": [f"collection/{self.collection.name}"],
                                "Permission": ["aoss:*"],
                                "ResourceType": "collection",
                            },
                            {
                                "Resource": [f"index/{self.collection.name}/*"],
                                "Permission": ["aoss:*"],
                                "ResourceType": "index",
                            },
                        ],
                        "Principal": [
                            f"arn:aws:iam::{Aws.ACCOUNT_ID}:role/Admin",
                            f"arn:aws:iam::{Aws.ACCOUNT_ID}:role/cdk-hnb659fds-cfn-exec-role-{Aws.ACCOUNT_ID}-{Aws.REGION}",
                        ],
                        "Description": "Allow all access to collection and indexes",
                    }
                ]
            ),
        )

        # Create index using CfnIndex

        # Set dependencies
        self.collection.node.add_dependency(encryption_policy)
        network_policy.node.add_dependency(self.collection)
        # Add dependencies to ensure proper deletion order
        network_policy.node.add_dependency(vpc_endpoint)
        network_policy.node.add_dependency(security_group)
        dimension = self._stack.node.try_get_context("model_embedding_dimensions")

        content_index = opensearchserverless.CfnIndex(
            self,
            "ContentIndex",
            collection_endpoint=self.collection.attr_collection_endpoint,
            index_name=index_name,
            # Use the proper MappingsProperty structure
            mappings=opensearchserverless.CfnIndex.MappingsProperty(
                properties={
                    "content_vector": opensearchserverless.CfnIndex.PropertyMappingProperty(
                        type="knn_vector",
                        dimension=int(dimension),
                        method=opensearchserverless.CfnIndex.MethodProperty(
                            name="hnsw",
                            space_type="innerproduct",
                            engine="faiss",
                            parameters=opensearchserverless.CfnIndex.ParametersProperty(
                                ef_construction=512, m=16
                            ),
                        ),
                    )
                }
            ),
            # Use the proper IndexSettingsProperty structure
            settings=opensearchserverless.CfnIndex.IndexSettingsProperty(
                index=opensearchserverless.CfnIndex.IndexProperty(knn=True)
            ),
        )
        content_index.node.add_dependency(self.collection)
        content_index.node.add_dependency(self.data_access_policy)
        content_index.node.add_dependency(vpc_endpoint)

        # Outputs
        CfnOutput(self, "CollectionName", value=self.collection.name)
        CfnOutput(
            self, "CollectionEndpoint", value=self.collection.attr_collection_endpoint
        )
        CfnOutput(
            self, "DashboardEndpoint", value=self.collection.attr_dashboard_endpoint
        )

    def grant_connection(self, role: Optional[iam.Role] = None) -> None:
        """
        Grants access to a resource by adding an IAM role to the Principal list in the access policy.

        Args:

             fn: A Lambda function to grant permissions to
        Returns:
            None

        Example:
            my_resource.grant_connection(my_iam_role)
        """

        role.add_to_principal_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW, actions=["aoss:APIAccessAll"], resources=["*"]
            )
        )
        # Parse the current policy JSON string into a Python dictionary
        current_access_json = json.loads(self.data_access_policy.policy)

        # Add the role's ARN to the Principal list in the first policy statement
        # Assumes the policy has at least one statement and contains a Principal key
        current_access_json[0]["Principal"].append(role.role_arn)

        # Convert the modified policy back to a JSON string and update the policy
        self.data_access_policy.policy = json.dumps(current_access_json)
