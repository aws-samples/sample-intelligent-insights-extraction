# Insights Hub

一个用于展示产品设计理念和图片的应用，包含React前端和Node.js后端，部署在AWS ECS上，使用OpenSearch Serverless和S3存储数据。

## 项目结构

```
insights-hub/
├── frontend/                # React前端应用
│   ├── public/              # 静态资源
│   ├── src/                 # 源代码
│   │   ├── components/      # 组件
│   │   ├── pages/           # 页面
│   │   ├── services/        # API服务
│   │   └── assets/          # 资源文件
│   ├── package.json         # 依赖配置
│   └── nginx.conf           # Nginx配置
├── backend/                 # Node.js后端应用
│   ├── src/                 # 源代码
│   │   ├── controllers/     # 控制器
│   │   ├── models/          # 数据模型
│   │   ├── routes/          # 路由
│   │   ├── services/        # 服务
│   │   └── utils/           # 工具函数
│   ├── config/              # 配置文件
│   └── package.json         # 依赖配置
├── aws/                     # AWS部署配置
│   ├── ecs-task-definition.json  # ECS任务定义
│   ├── iam-policy.json      # IAM策略
│   └── deploy.sh            # 部署脚本
├── Dockerfile.frontend      # 前端Docker配置
├── Dockerfile.backend       # 后端Docker配置
└── docker-compose.yml       # Docker Compose配置
```

## 功能特点

- 展示从其他产品设计网站爬取的设计理念和图片
- 精简的UI设计，易于使用
- 支持按类别筛选设计
- 支持搜索功能
- 详细的设计展示页面
- 从AWS OpenSearch Serverless获取数据
- 从S3获取图片

## 本地开发

### 前提条件

- Node.js (v14+)
- Docker 和 Docker Compose
- AWS CLI (已配置)

### 启动前端

```bash
cd frontend
npm install
npm start
```

前端将在 http://localhost:3000 运行。

### 启动后端

```bash
cd backend
npm install
npm run dev
```

后端将在 http://localhost:3001 运行。

### 使用Docker Compose

```bash
docker-compose up
```

应用将在 http://localhost 运行。

## AWS部署

### 配置AWS凭证

确保已配置AWS CLI：

```bash
aws configure
```

### 部署到ECS

```bash
cd aws
chmod +x deploy.sh
./deploy.sh
```

## 数据存储

- **OpenSearch Serverless**: 存储设计数据和元信息
- **S3**: 存储设计图片

## 注意事项

- 本地开发时使用模拟数据
- 部署到AWS前需要创建OpenSearch Serverless集合和S3存储桶
- 需要配置适当的IAM权限
