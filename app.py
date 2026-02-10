import os
from aws_cdk import App, Environment

from infrastructure.main import MyStack

# for development, use account/region from cdk cli
dev_env = Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("CDK_DEFAULT_REGION"),
)

app = App()
project_name = app.node.try_get_context("project_name")
MyStack(app, project_name, env=dev_env)
# MyStack(app, "intelligent-insights-collector-prod", env=prod_env)


app.synth()
