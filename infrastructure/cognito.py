from aws_cdk import Stack, aws_cognito as cognito, CfnOutput, RemovalPolicy
from constructs import Construct


class CognitoPool(Construct):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id)

        # Create Cognito User Pool
        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name=f"{construct_id}User",
            self_sign_up_enabled=False,  # Disable self-registration
            sign_in_aliases=cognito.SignInAliases(username=True, email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            # advanced_security_mode=cognito.AdvancedSecurityMode.ENFORCED,
            removal_policy=RemovalPolicy.DESTROY,  # Use with caution in production
        )

        # Add email as a required standard attribute
        self.pool_client = self.user_pool.add_client(
            "AppClient",
            user_pool_client_name=f"{construct_id}Client",
            auth_flows=cognito.AuthFlow(user_password=True, user_srp=True),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(implicit_code_grant=True),
                scopes=[cognito.OAuthScope.EMAIL],
            ),
        )

        # Output the User Pool ID and Client ID
        CfnOutput(
            self,
            "UserPoolId",
            value=self.user_pool.user_pool_id,
            description="Cognito Pool ID",
        )
        CfnOutput(
            self,
            "UserPoolClientId",
            value=self.pool_client.user_pool_client_id,
            description="Cognito Pool Client ID",
        )

    def get_user_pool_id(self):
        return self.user_pool.user_pool_id

    def get_user_pool_client_id(self):
        return self.pool_client.user_pool_client_id
