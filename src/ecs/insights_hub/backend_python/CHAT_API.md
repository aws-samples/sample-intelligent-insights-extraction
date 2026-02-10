# Chat API 使用说明

## 概述

Chat API 为 Insights Hub 提供了基于 AWS Bedrock Anthropic Claude 的智能聊天功能。

## API 端点

### 1. 流式聊天 (推荐)
```
POST /api/chat/stream
```

**请求体:**
```json
{
  "message": "你好，请介绍一下你自己",
  "conversation_history": [
    {
      "role": "user",
      "content": "之前的用户消息"
    },
    {
      "role": "assistant", 
      "content": "之前的助手回复"
    }
  ],
  "model": "claude-3-5-sonnet-20241022"
}
```

**响应:** Server-Sent Events (SSE) 流
```
data: {"chunk": "你好"}
data: {"chunk": "！我是"}
data: {"chunk": " Claude"}
data: {"done": true}
```

### 2. 简单聊天
```
POST /api/chat
```

**请求体:** 同上

**响应:**
```json
{
  "response": "完整的回复内容",
  "model": "claude-3-5-sonnet-20241022"
}
```

### 3. 获取可用模型
```
GET /api/chat/models
```

**响应:**
```json
{
  "models": [
    {
      "value": "claude-3-5-sonnet-20241022",
      "label": "Claude 3.5 Sonnet",
      "description": "最新版本，平衡性能与速度"
    }
  ]
}
```

## 环境配置

1. 复制环境变量模板:
```bash
cp .env.example .env
```

2. 确保AWS凭证配置正确，ECS任务角色需要以下权限:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:*::foundation-model/*",
        "arn:aws:bedrock:*:*:inference-profile/*"
      ]
    }
  ]
}
```

## 支持的模型

- `claude-3-5-sonnet-20241022` - 最新版本，平衡性能与速度
- `claude-3-opus-20240229` - 最强性能，适合复杂任务  
- `claude-3-sonnet-20240229` - 平衡选择，性价比高
- `claude-3-haiku-20240307` - 快速响应，适合简单任务

## 错误处理

API 会返回适当的 HTTP 状态码和错误信息：

- `400` - 请求参数错误
- `500` - 服务器内部错误（如 Bedrock 客户端未配置或权限不足）

流式响应中的错误：
```
data: {"error": "错误描述"}
```

常见错误：
- `"Bedrock client not configured"` - AWS 凭证或区域配置问题
- `"Bedrock service error"` - 权限不足或模型访问问题

## 前端集成

前端 ChatBot 组件已经集成了流式聊天功能，会自动调用 `/api/chat/stream` 端点。

## AWS Bedrock 模型映射

前端模型名称会自动映射到对应的 Bedrock inference profile ID：

- `claude-3-5-sonnet-20241022` → `us.anthropic.claude-3-5-sonnet-20241022-v2:0`
- `claude-3-opus-20240229` → `us.anthropic.claude-3-opus-20240229-v1:0`
- `claude-3-sonnet-20240229` → `us.anthropic.claude-3-sonnet-20240229-v1:0`
- `claude-3-haiku-20240307` → `us.anthropic.claude-3-haiku-20240307-v1:0`