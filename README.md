# 消费者运营中台

面向代运营公司的消费者运营中台：多行业适配、指令驱动、方案生成、整月排期、到点自动下发、人工验收的完整闭环。

## 已实现能力

- 指令中心：12 维结构化指令，生成 7 板块策略资产包（活动、货盘、目标人群、销售执行包、内容排期、KPI、合规约束）。
- 执行中心：按活动 / 货盘 / 1v1 / 朋友圈 / 社群 / 短信 / 跟进分类展示具体内容，每个模块带行业模板配置区。
- 整月排期：审批后自动生成 30 天可编辑待办，后台每分钟调度，到点自动护栏校验并下发，支持补发窗口、时间窗、频道限频、整月暂停。
- 护栏：品牌违禁词 + 语境放行（如“最近/最后/第一时间”），命中自动拦截并告警。
- 知识库：多行业知识 + 美丽田园品牌资料 + Second Brain 话术/卡项迁移，资产包自动检索真实素材。
- 多行业模板：美业、餐饮、零售、教育、宠物、大健康各一套货盘/活动/销售/内容/KPI 默认模板。
- 角色权限：admin / operator / viewer，viewer 只读，写操作前后端双重控制。
- 验收：验收时回填 KPI 实际值，报告自动生成“目标 / 实际 / 达成率”对比。
- 渠道：Mock 已接通，企业微信适配器预留；智能客服不自研，通过外部桥接层接入。

## 快速开始

### 后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

API 文档：<http://localhost:8000/docs>

默认管理员：`admin` / `admin123`（登录后在“配置”中修改密码）。

### 前端

```bash
cd web
npm install
npm run dev
```

开发地址：<http://localhost:5173>；生产构建由后端托管于 <http://localhost:8000>。

### 测试

```bash
cd backend
.venv/bin/python -m pytest tests -q
```

## 部署与开机自启

```bash
bash scripts/sync-deploy.sh
```

脚本会把代码同步到 `~/pdp-platform/backend`，回拉运行时数据库，再重启 macOS LaunchAgent `com.pdp.platform`。数据库文件默认 `backend/pdp.db`。

## 本地模型

默认优先使用本地 Ollama（`nomic-embed-text` 做向量、本地 Qwen 做生成），也可在 LLM 网关配置混元 / DeepSeek / GPT 等 OpenAI 兼容模型。

## 技术栈

- 后端：Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic + SQLite/PostgreSQL
- 前端：React + Vite + TypeScript
- LLM：OpenAI 兼容协议，支持 Ollama / 混元 / DeepSeek / GPT

完整方案见 [docs/开发方案.md](docs/开发方案.md)。
