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

## Git 工作流规范

本项目单人开发 + AI 协作，不搞 feature 分支 / PR / code review 那套，主分支（main/master）直接开发。但以下纪律必须守：

### 1. 改代码前先更新
开始任何修改前，先拉取最新，避免和远端或本地其他会话的改动冲突：
```bash
git pull --rebase    # 有远程时；没远程就跳过
git status           # 确认工作区干净再动手
```
工作区有未提交改动时，先问用户：提交、stash、还是丢弃，**不要**自作主张覆盖。

### 2. 小步提交
AI 每完成一个独立功能/修复就提交一次，**禁止**攒一大坨改动一次提交。一个 commit 只做一件事，便于回滚定位。

### 3. 提交信息规范
- 中文，动宾结构，一句话说清改了啥
- 格式：`<类型>: <说明>`，类型用 `feat/fix/refactor/docs/chore/test`
- 示例：`feat: 订单列表加分页` / `fix: 飞书卡片下发空指针` / `refactor: 抽取 LLM 调用重试逻辑`
- 禁止：`update` / `修改` / `改动` 这种看不出内容的信息

### 4. 禁止自动 push
单人本地开发，push 到远程是可选项。AI **不得**自动 `git push`，必须用户明确说"推送/push"才执行。

### 5. 冲突必须停下问
`pull --rebase` 或 `merge` 遇到冲突，AI **禁止**自行选择一边覆盖。必须停下来告诉用户：哪几个文件冲突、冲突点是什么、请用户定夺。

### 6. 危险操作必须先问
以下操作 AI **不得**自作主张执行，必须先问用户并说明后果：
- `git reset --hard` / `git checkout .` / `git restore .` —— 丢弃未提交改动
- `git clean -fd` —— 删除未跟踪文件
- `git push --force` / `--force-with-lease` —— 强推覆盖远端
- `git branch -D` —— 删分支
- 任何 `git rebase` 已提交的 commit

### 7. 敏感文件绝不手动 add
`.env` / `pdp.db` / `logs/` / `backups/` 已在 `.gitignore`。AI **禁止**用 `git add -f` 强加这些文件，也**禁止** `git add .env` 这类显式添加。统一用 `git add -A`（会自动遵守 .gitignore）或 `git add <具体源码文件>`。

### 8. 部署前的 git 检查
部署前 AI 必须确认：
```bash
git status --short    # 必须是 clean（nothing to commit）
git log -1 --oneline  # 记下 commit hash，部署脚本会写进 deploy.log
```
工作区不干净就先提交或问用户，**不要**带未提交改动部署。

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
