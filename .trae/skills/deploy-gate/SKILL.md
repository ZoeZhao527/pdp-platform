---
name: "deploy-gate"
description: "Deployment and rollback gate for AI-driven releases: pre-deploy checks (git clean, quality gate passed), use deploy.sh not ad-hoc commands, backup+log+healthcheck, rollback on failure. Invoke when deploying code, pushing to production, or recovering from failed deploy."
---

# 发布闸门（AI 部署前必跑）

本规范适用于无 CI/CD、由 AI 协作部署的项目。核心目标：**每次部署可追溯、可回滚、失败不污染线上**。

AI 部署代码前，**必须按顺序完成下列流程**，禁止临时手搓部署命令、禁止带未提交改动部署、禁止部署失败不回滚。

---

## 前置：基础设施必须就位

部署依赖下列脚本，若缺失必须先建：
- `scripts/deploy.sh` —— 部署脚本（备份→同步→重启→健康检查→记录）
- `scripts/rollback.sh` —— 回滚脚本（选备份还原→重启→健康检查）
- `deploy/deploy.log` —— 部署记录（自动生成）
- `deploy/backups/deploy_YYYYmmdd_HHMMSS/` —— 备份目录（自动生成）

若项目缺这些脚本，AI 必须提示用户："发布闸门依赖 deploy.sh/rollback.sh，当前项目未配置，需先建脚本，否则无法安全部署。"

---

## 部署前检查（必跑）

### 1. 确认工作区干净
```bash
git status --short    # 必须空输出（nothing to commit）
```
- 有未提交改动 → 先 commit 或问用户，**禁止带未提交改动部署**
- 改后端代码的 commit 必须先过 `code-quality-gate` 四道闸门

### 2. 记下当前 commit
```bash
git log -1 --oneline
```
- 部署脚本会把 commit hash 写进 `deploy/deploy.log`，作为回滚锚点
- 没 commit = 没回滚锚点，禁止部署

### 3. 确认是最新代码
```bash
git pull --rebase    # 有远程时
```
- 不是最新就先 pull，冲突停下问用户

---

## 部署执行（必用脚本，禁手搓）

**禁止** AI 临时拼 `rsync` / `ssh` / `launchctl` 命令。必须用 `scripts/deploy.sh`：

```bash
# 本机部署（本机即运行机）
bash scripts/deploy.sh --local

# 远程部署（本机开发 → 远程 mac 运行）
bash scripts/deploy.sh --host user@host --dest ~/pdp-platform
```

脚本自动完成五步：
1. **备份**当前运行版本到 `deploy/backups/deploy_时间戳/`（代码 + 数据库 + .env）
2. **同步**新代码到运行目录
3. **重启**LaunchAgent 服务
4. **健康检查**调用 `/api/v1/health` 确认服务存活
5. **记录**到 `deploy/deploy.log`：时间戳 + git commit + 模式 + 成功/失败

任一步骤失败，脚本自动回滚到上一个备份并标记失败。

---

## 部署后验证

部署脚本返回成功后，AI 再确认：

```bash
# 1. 查部署记录最新一条
tail -5 deploy/deploy.log

# 2. 健康检查（脚本已跑，再确认一次）
curl -fsS http://localhost:8000/api/v1/health

# 3. 查备份目录（应该有新备份）
ls -1t deploy/backups/ | head -3
```

三个都正常，部署才算成功。

---

## 失败回滚（必跑）

部署失败（脚本退出非 0、健康检查不通、服务起不来）时：

```bash
# 回滚到最近一次成功备份
bash scripts/rollback.sh --local
bash scripts/rollback.sh --host user@host --dest ~/pdp-platform

# 回滚到指定备份
bash scripts/rollback.sh --to deploy_20260831_103000
```

回滚脚本自动：选备份还原（代码+数据库+.env）→ 重启 → 健康检查。

**铁律**：部署失败**必须回滚**，禁止"线上挂着我等会再修"。回滚后报告用户：失败原因、回滚到哪个备份、当前线上状态。

---

## 部署纪律

| 禁止 | 应该 |
|------|------|
| 手搓 rsync/ssh/launchctl 命令 | 用 `scripts/deploy.sh` |
| 带未提交改动部署 | 先 commit 或问用户 |
| 跳过质量闸门直接部署 | commit 必须先过 `code-quality-gate` |
| 部署失败不回滚 | 失败立刻 `rollback.sh` |
| 自动 `git push` 部署 | 用户明确说"部署/push"才执行 |
| force push 到 main | 永远不用 `--force` |

---

## 备份管理

- 每次部署自动备份到 `deploy/backups/deploy_YYYYmmdd_HHMMSS/`
- 默认保留最近 10 份，超出自动清理
- 备份内容：`backend/app` 代码 + `pdp.db` 数据库 + `.env`
- 备份不入库（`.gitignore` 已排除）

---

## AI 自检清单（部署前逐项核对）

- [ ] `git status --short` 空输出（工作区干净）
- [ ] `git log -1 --oneline` 已记下 commit hash
- [ ] 改后端的 commit 已过 `code-quality-gate` 四道闸门
- [ ] 用 `scripts/deploy.sh` 部署，不是手搓命令
- [ ] 部署后查 `deploy/deploy.log` 最新记录
- [ ] 健康检查通过（`/api/v1/health` 返回 200）
- [ ] 备份目录有新备份
- [ ] 失败时已用 `rollback.sh` 回滚并报告用户
