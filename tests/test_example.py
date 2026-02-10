import pytest
from aws_cdk import App
from aws_cdk.assertions import Template
from infrastructure.main import MyStack


@pytest.fixture(scope="module")
def template():
    app = App()
    # Add context values that the stack expects
    app.node.set_context("model_embedding", "cohere.embed-multilingual-v3")
    app.node.set_context("model_embedding_dimensions", "1024")
    app.node.set_context("stage", "test")
    app.node.set_context("project_name", "test")

    stack = MyStack(app, "my-stack-test")
    template = Template.from_stack(stack)
    yield template


def test_no_buckets_found(template):
    template.resource_count_is("AWS::S3::Bucket", 5)