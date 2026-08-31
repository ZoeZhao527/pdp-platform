# AGENTS.md — 给 AI 助手的工作约定

本项目的代码与部署均由 AI 协助完成。所有 AI 助手（TRAE / Cursor / Claude Code 等）在本项目工作前，必须先读本文件并遵守以下约定。

## 红线（必先执行）

1. **改后端代码前，必须先调用项目内的两个 skill**，加载规范后再动手：
   - `fastapi-code-standards`（`.trae/skills/fastapi-code-standards/SKILL.md`）—— 统一返回体、异常处理、参数校验、分层命名
   - `fastapi-logging-standards`（`.trae/skills/fastapi-logging-standards/SKILL.md`）—— 结构化日志、trace_id、脱敏、滚动删除

   触发场景：新增/修改任何 `backend/app/` 下的 `.py`、配置日志、新增接口或服务。

2. **部署前必须用 `scripts/deploy.sh`，禁止 AI 临时手搓部署命令。**
   - 本机部署：`bash scripts/deploy.sh --local`
   - 远程部署：`bash scripts/deploy.sh --host user@host --dest ~/pdp-platform`
   - 失败回滚：`bash scripts/rollback.sh --to <备份名>` 或 `--local` 回滚到最近一次

3. **改完代码必须先提交 git 再部署。** 部署脚本会读取 git commit 写进 `deploy/deploy.log`，没提交就没有回滚锚点。
   ```bash
   git add -A && git commit -m "<改动说明>"
   ```

## 不可触碰

- `backend/pdp.db` —— 运行时数据库，绝不入库、绝不覆盖（部署脚本已自动备份）
- `backend/app/api/__pycache__/platform_orig.cpython-312.pyc` —— 字节码，删了后端起不来
- `.env` —— 密钥文件，不入库、不外传
- `deploy/backups/` / `deploy/deploy.log` —— 部署运行时产物，不入库

## 部署记录与回滚

- 每次部署写入 `deploy/deploy.log`：时间戳、git commit、模式、成功/失败
- 每次部署备份到 `deploy/backups/deploy_YYYYmmdd_HHMMSS/`，保留最近 10 份
- 备份内容：`backend/app` 代码 + `pdp.db` 数据库 + `.env`
- 回滚 = 选一个备份还原 + 重启 LaunchAgent + 健康检查

## 现状备忘

- 部署方式：macOS LaunchAgent（`deploy/com.pdp.platform.plist`），运行目录 `/Users/zhaoxinyuan/pdp-platform/backend`
- 日志当前写 `/tmp/pdp-backend.log`（系统重启会丢），如需持久化按 `fastapi-logging-standards` 落盘到 `logs/`
- 数据库：SQLite，迁移用 Alembic（`backend/alembic/`）
