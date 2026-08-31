---
name: "code-quality-gate"
description: "Pre-commit quality gate for Python backend: ruff check, mypy type check, pytest smoke + snapshot tests. Snapshot tests detect AI regressions in old features. Invoke when preparing to commit or deploy after modifying backend/app/*.py. Trigger words: commit/提交/部署前/质量检查/regression/跑测试. Do not skip, do not use --no-verify, do not modify tests to pass."
---

# 代码质量闸门（AI 改完代码 commit 前必跑）

本规范适用于无 CI/CD、由 AI 协作迭代的 Python 项目。核心目标：**Python 没有编译期兜底，用静态检查 + 测试模拟出"编译期护栏"**，确保 AI 改对了知道对，改坏了当场拦截，旧功能不被偷偷篡改。

AI 改完后端代码、准备 `git commit` 前，**必须按顺序跑完下列四道闸门**，全部通过才能提交。任何一道失败都不许跳过、不许 `--no-verify`、不许"我看着没问题"。

---

## 前置：基础设施必须就位

下列工具若项目未配置，AI 在首次改代码时**必须先协助配置**，不能跳过：

- `pyproject.toml` 含 `[tool.ruff]` / `[tool.mypy]` / `[tool.pytest.ini_options]`
- `requirements.txt` 含 `ruff` / `mypy` / `pytest` / `pytest-snapshot`
- `tests/` 目录存在，至少有核心接口的冒烟 + 快照测试

如果业务方项目暂未落地这些，AI 应主动提示用户："质量闸门依赖 ruff/mypy/pytest，当前项目未配置，需要先建配置和测试用例，否则闸门无法生效。"

---

## 闸门 1：ruff lint（秒级，必跑）

抓 AI 最常犯的错：未用 import、未定义变量、语法错、可变默认参数、重复变量名、错误缩进。

```bash
cd backend
ruff check .
```

- **0 error 才能继续**；有 error 必须修复后重跑
- 禁止用 `# noqa` 注释绕过，除非该行确实有合理理由且注释说明原因
- 禁止改 `[tool.ruff]` 配置放松规则来"通过"

## 闸门 2：mypy 类型检查（分钟级，必跑）

抓 AI 改坏函数签名、传错参数类型、返回值类型不一致。

```bash
cd backend
mypy app/
```

- **0 error 才能继续**
- 第三方库无 stub 的报错已通过 `ignore_missing_imports = true` 屏蔽，剩余报错必须修
- 禁止滥用 `# type: ignore` 绕过；确需忽略必须注释原因，如 `# type: ignore[arg-type]  # FastAPI Depends 动态注入`
- 渐进式策略：当前 `strict = false`，AI 不许擅自调严或调松

## 闸门 3：核心冒烟测试（分钟级，必跑）

保核心功能不挂。`@pytest.mark.smoke` 标记的用例覆盖最关键的接口（健康检查、登录、核心业务 2-3 个）。

```bash
cd backend
pytest -m smoke -v
```

- **全绿才能继续**
- 禁止删用例、禁止改测试期望值来"通过"
- 用例失败必须修代码，不是改测试

## 闸门 4：快照测试（防篡改神器，必跑）

这是**专门防 AI 篡改旧功能**的武器。`@pytest.mark.snapshot` 用例把关键 API 的响应结构拍照固化，AI 改了字段名、删了字段、改了返回结构 → 快照 diff 立刻报警。

```bash
cd backend
pytest -m snapshot -v
```

- **快照全绿才能继续**
- 快照变了**必须人工确认**：
  - 是预期变更（如确实要改返回结构）→ 跑 `pytest --snapshot-update` 更新快照 → commit message 必须说明"更新 X 接口快照，原因：..."
  - 不是预期变更 → AI 改坏了，必须修回代码，**禁止盲目 update**
- 禁止一次性 `--snapshot-update` 全部快照，必须逐个确认

---

## 失败处理铁律

| 闸门 | 失败时 | 禁止 |
|------|--------|------|
| ruff | 修代码重跑 | `# noqa` 绕过、改配置放松 |
| mypy | 修代码/类型重跑 | `# type: ignore` 滥用、调松配置 |
| 冒烟 | 修代码重跑 | 删用例、改期望值 |
| 快照 | 确认是预期→update；否则修回代码 | 盲目 `--snapshot-update` |

**任何闸门失败，AI 不得自行跳过、不得建议用户跳过、不得用"应该没问题"敷衍。** 必须诚实报告失败点、原因、修复方案，修完重跑直到全绿。

---

## commit 前最终自检

四道闸门全绿后，commit 前再确认：

1. `git diff` 自己 review 一遍改动，确认没有意外波及无关文件
2. 确认没动 `AGENTS.md` 的"不可触碰"清单（如 `pdp.db` / `.pyc` / `.env`）
3. 确认 commit message 符合规范（`feat/fix/refactor: 说明`）
4. 确认是**小步提交**——一个 commit 只做一件事，禁止攒大堆

---

## 与部署的衔接

只有四道闸门全绿 + git commit 成功，才能进入 `deploy.sh` 部署。部署脚本会读取 git commit 写进 `deploy.log`，没通过闸门就没 commit，没 commit 就没回滚锚点。

**闸门是部署的前置条件，不是可选项。**

---

## AI 自检清单（生成/修改代码后逐项核对）

- [ ] 跑了 `ruff check .` 且 0 error
- [ ] 跑了 `mypy app/` 且 0 error
- [ ] 跑了 `pytest -m smoke -v` 且全绿
- [ ] 跑了 `pytest -m snapshot -v` 且全绿（或确认后更新快照并说明）
- [ ] `git diff` 已自 review，无意外波及
- [ ] 没动"不可触碰"文件
- [ ] commit message 符合 `类型: 说明` 规范
- [ ] 没有跳过任何一道闸门
