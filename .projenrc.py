import os

from projen.awscdk import AwsCdkPythonApp


setting = {
    "project_name": "insights-test",
    "stage": "dev",
    "model_extraction": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    "model_embedding": "cohere.embed-multilingual-v3",
    "model_embedding_dimensions": "1024",
    "log_level": "DEBUG",
}

project = AwsCdkPythonApp(
    author_email="dmhong@amazon.com,jiatin@amazon.com",
    author_name="Michelle Hong,Ting Jia",
    cdk_version="2.1.0",
    module_name="src",
    name="sample-intelligent-insights-extraction",
    version="0.1.0",
    venv=True,
    python_exec="python3",  # Specify python3 as the Python executable,
    deps=["black", "projen"],
    dev_deps=[
        "boto3",
        "requests",
        "jsonschema",
        "tenacity",
        "Pillow",
        "mcp",
        "pydantic>=2.0",
        "opensearch-py",
        "json-repair",
        "beautifulsoup4",
    ],
    context=setting,
    pytest=False,
)

# Create lambda_layer task that uses the updated create_layer.sh script
create_lambda_layer = project.add_task("create_lambda_layer")
create_lambda_layer.exec("./create_layer.sh")

create_lambda_agentcore_layer = project.add_task("create_lambda_layer_agentcore")
create_lambda_agentcore_layer.exec("./create_layer_agent_browser.sh")

# Create install readability task
install_readability = project.add_task("install_readability")
install_readability.exec("./src/lambdas/html_readability/install_deps.sh")

# Find the deploy task and make it depend on the create_lambda_layer task
post_compile_task = project.tasks.try_find("post-compile")
if post_compile_task:
    post_compile_task.prepend_spawn(create_lambda_layer)
    post_compile_task.prepend_spawn(create_lambda_agentcore_layer)
    post_compile_task.prepend_spawn(install_readability)

project.add_git_ignore("src/lambda_layers/*/python")
project.add_git_ignore("src/lambda_layers/*/*.zip")

project.add_git_ignore("data")
project.synth()
