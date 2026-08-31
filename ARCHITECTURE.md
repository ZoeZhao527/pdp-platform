# 消费者运营中台 - 代码包说明

## 目录结构

```
backend/               后端 (Python 3.12 + FastAPI)
  app/                  主应用代码
    api/               API 路由层
      platform.py       主 API 路由 (包装器, 补丁生成逻辑)
      __pycache__/
        platform_orig.cpython-312.pyc  ★ 原始字节码, 不可删除
      feishu.py         飞书集成路由
    integrations/
      feishu.py         飞书客户端 (消息发送/卡片/webhook)
    knowledge/          知识库服务 (向量检索)
    llm_gateway/        LLM 网关 (DeepSeek/GLM 多租户路由)
    guardrails/         内容合规护栏
    models.py           数据模型 (SQLAlchemy ORM)
    config.py           系统配置
    db.py               数据库连接
  alembic/              数据库迁移
  scripts/              运维脚本
  requirements.txt      Python 依赖
  Dockerfile            后端容器构建

web-src/                前端源码 (React + TypeScript + Vite)
  src/
    pages/              页面组件
    components/         通用组件
  package.json         Node 依赖
  tsconfig.json

web-dist/               前端构建产物 (可直接部署到 Nginx)

deploy/                 部署配置
  com.pdp.platform.plist  macOS LaunchAgent 配置

docs/                   文档
  cloud-deployment-plan.html  云端部署方案

docker-compose.yml     Docker 编排配置
```

## 关键说明

### platform.py 与 platform_orig.pyc

`platform.py` 是一个包装器，它从 `platform_orig.cpython-312.pyc`（字节码文件）加载原始 API 逻辑，
然后在运行时补丁/增强以下功能：
- 品牌卡项 key 标准化（中文 -> 英文）
- 从品牌卡项提取价格，匹配知识库护理项目
- 为 LLM 注入匹配的护理项目详情
- 生成后清理货盘（只保留品牌卡 + 匹配的护理项目）
- 对话发指令的交互式澄清逻辑
- 飞书卡片结构化下发

**绝不可删除 `platform_orig.cpython-312.pyc` 文件**，否则后端无法启动。

### 数据库

当前使用 SQLite (pdp.db)，云端部署需迁移至 PostgreSQL + pgvector。
迁移脚本和 docker-compose.yml 中已包含 PostgreSQL 配置。

### LLM 配置

多租户 LLM 路由：
- 美丽田园: DeepSeek V4 Pro (阿里云 MaaS)
- 华润怡宝: GLM 4.5 (容联代理)

API Key 通过环境变量 (.env) 注入，不包含在此代码包中。

### 环境变量 (.env)

部署时需要创建 .env 文件，包含：
- AI_API_KEY: LLM API 密钥
- AI_API_HOST: LLM API 地址
- FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_CHAT_ID: 飞书配置
- DATABASE_URL: PostgreSQL 连接串
- REDIS_URL: Redis 连接串

## 启动方式

### 本地开发
```bash
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

cd web-src && npm install && npm run dev
```

### Docker 部署
```bash
docker compose up -d
```
