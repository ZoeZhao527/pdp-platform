---
name: "fastapi-logging-standards"
description: "Enforces FastAPI logging conventions: structured JSON logs, trace_id propagation, request/response logging, log levels, and sensitive field masking. Invoke when setting up logging, adding loggers to services, or when user asks to follow project logging standards."
---

# FastAPI 日志规范

本规范适用于 FastAPI + Python 3.10+ 项目。生成或修改后端代码涉及日志时**必须遵循**，确保结构化输出、调用链可追踪、级别规范、敏感字段脱敏四项核心一致。

核心口诀：**统一配置一次，结构化输出 JSON，trace_id 贯穿全程，入参出参必记，敏感字段必脱敏，级别用对**。

---

## 一、统一日志配置

### 1. 单点配置
日志只能在 **入口处配置一次**（`app/core/logging.py`），禁止在业务模块里调用 `logging.basicConfig` 或自定义 `Handler`。所有业务模块只用 `logger = logging.getLogger(__name__)` 获取 logger。

```python
# app/core/logging.py
import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from typing import Any

from app.core.context import get_trace_id  # 见第二节


class JsonFormatter(logging.Formatter):
    """结构化 JSON 日志，便于 ELK/Loki 采集与检索。"""

    # 敏感字段名（小写匹配），命中即脱敏
    SENSITIVE_KEYS = {
        "password", "passwd", "pwd", "secret", "token", "accesstoken",
        "refreshtoken", "apikey", "api_key", "appsecret", "app_secret",
        "authorization", "cookie", "session", "idcard", "id_card",
        "bankcard", "bank_card", "cvv",
    }

    def format(self, record: logging.LogRecord) -> str:
        log = {
            "ts": self.formatTime(record, "%Y-%m-%d %H:%M:%S.%f")[:-3],
            "level": record.levelname,
            "logger": record.name,
            "trace_id": get_trace_id(),
            "msg": record.getMessage(),
        }
        # extra 字段（如 user_id/tenant_id/latency）合并进顶层
        for k, v in record.__dict__.items():
            if k in log or k.startswith("_"):
                continue
            if k in {"args", "msecs", "levelname", "name", "msg",
                     "filename", "module", "exc_info", "exc_text",
                     "stack_info", "lineno", "funcName", "created",
                     "thread", "threadName", "process", "processName",
                     "relativeCreated", "levelno", "pathname", "message"}:
                continue
            log[k] = _safe(v)
        if record.exc_info:
            log["exc"] = self.formatException(record.exc_info)
        return json.dumps(log, ensure_ascii=False)


def _safe(v: Any) -> Any:
    if isinstance(v, dict):
        return {k: ("***" if str(k).lower() in JsonFormatter.SENSITIVE_KEYS else _safe(val)) for k, val in v.items()}
    if isinstance(v, list):
        return [_safe(x) for x in v]
    return v


def setup_logging(
    level: str = "INFO",
    log_file: str | None = None,
    max_bytes: int = 100 * 1024 * 1024,   # 100MB，按大小滚动的单文件上限
    backup_count: int = 10,               # 按大小滚动保留的旧文件数
    rotate_when: str | None = None,       # 非空则按时间滚动，如 "midnight"=每天
    backup_days: int = 30,                # 按时间滚动保留的天数/份数
) -> None:
    """在 FastAPI lifespan 启动阶段调用一次。

    - log_file 为空：仅 stdout（容器部署推荐，由采集系统轮转）
    - log_file 非空 + rotate_when 为空：按大小滚动（RotatingFileHandler）
    - log_file 非空 + rotate_when 非空：按时间滚动（TimedRotatingFileHandler）
    stdout 始终保留，便于 `docker logs` 查看实时日志。
    """
    formatter = JsonFormatter()
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    # stdout handler（始终启用）
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    root.addHandler(stdout_handler)

    # 文件 handler（可选，裸机部署用）
    if log_file:
        os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
        if rotate_when:
            file_handler = TimedRotatingFileHandler(
                log_file, when=rotate_when, interval=1,
                backupCount=backup_days, encoding="utf-8",
            )
        else:
            file_handler = RotatingFileHandler(
                log_file, maxBytes=max_bytes, backupCount=backup_count,
                encoding="utf-8",
            )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    # 抑制过吵的第三方库日志
    for noisy in ("uvicorn.access", "httpx", "httpcore", "openai._base_client"):
        logging.getLogger(noisy).setLevel("WARNING")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
```

### 2. 启动接入
```python
# app/main.py
from app.core.logging import setup_logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(
        level=settings.log_level,
        log_file=settings.log_file,          # None=不落盘；"logs/app.log"=落盘
        max_bytes=settings.log_max_bytes,    # 按大小滚动的单文件上限
        backup_count=settings.log_backup_count,
        rotate_when=settings.log_rotate_when,  # "midnight"=按天滚动；None=按大小
        backup_days=settings.log_backup_days,
    )  # 先初始化日志，再启动其他
    ...
```

对应 Settings 配置项：
```python
# app/config.py
log_level: str = "INFO"
log_file: str | None = None              # 容器部署留空；裸机部署填 "logs/app.log"
log_max_bytes: int = 104857600           # 100MB
log_backup_count: int = 10               # 按大小滚动保留 10 个旧文件
log_rotate_when: str | None = None       # "midnight"=按天；"H"=按小时；None=按大小
log_backup_days: int = 30                # 按时间滚动保留 30 天/份
```

### 3. 模块内取 logger
```python
# 任何业务模块
import logging
logger = logging.getLogger(__name__)
```
禁止 `print()`、禁止 `logging.warning("...")` 裸调（必须经 logger 实例）、禁止每个文件自己 `basicConfig`。

### 4. 文件日志与滚动删除（可选）

**何时落盘**：容器/Docker 部署 → **不落盘**（stdout 由 Docker logging driver / Loki 轮转）；裸机部署（systemd / macOS LaunchAgent / 直接跑进程）→ **落盘 + 滚动删除**，否则日志文件无限增长。

**两种滚动策略二选一**（按时间和按大小可同时配置 `rotate_when` 优先）：

| 策略 | 适用 | 配置 | 效果 |
|------|------|------|------|
| 按大小滚动 | 流量不均、磁盘紧张 | `rotate_when=None`, `max_bytes=100MB`, `backup_count=10` | 单文件超 100MB 切割，保留最近 10 个旧文件，总上限约 1.1GB |
| 按时间滚动 | 按日排查、归档清晰 | `rotate_when="midnight"`, `backup_days=30` | 每天午夜切割一个 `app.log.YYYY-MM-DD`，保留 30 天 |

`rotate_when` 取值（Python 标准库 `TimedRotatingFileHandler`）：
- `"S"` 秒 / `"M"` 分 / `"H"` 小时 / `"D"` 天
- `"midnight"` 每天午夜（最常用）/ `"W0"`-`"W6"` 每周（W0=周一）

**禁止行为**：
- 禁止业务代码直接 `open("xxx.log","a")` 写日志，必须经统一 handler。
- 禁止只落盘不滚动（文件会无限增长撑爆磁盘）。
- 禁止把日志文件写进代码目录（写到运行目录 `logs/` 或 `/var/log/<app>/`，避免污染源码）。
- 容器部署禁止同时落盘（容器内文件系统非持久，且与采集系统重复）。

**生成文件名规则**（标准库自动）：
- 按大小：`app.log`（当前）→ 滚动时改名 `app.log.1`、`app.log.2`...，新日志继续写 `app.log`
- 按时间：`app.log`（当前）→ 滚动时改名 `app.log.2026-08-31`，新日志继续写 `app.log`

---

## 二、trace_id 调用链

### 1. ContextVar 存取
```python
# app/core/context.py
import contextvars
import uuid

_trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="-")


def get_trace_id() -> str:
    return _trace_id_var.get()


def set_trace_id(trace_id: str | None = None) -> str:
    tid = trace_id or uuid.uuid4().hex[:16]
    _trace_id_var.set(tid)
    return tid


def clear_trace_id() -> None:
    _trace_id_var.set("-")
```

### 2. 中间件注入
每个请求生成/透传 `trace_id`，写入响应头 `X-Trace-Id`，并放入 ContextVar 供全链路日志读取。

```python
# app/middleware/trace.py
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.context import set_trace_id, get_trace_id


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 支持上游透传（网关/网关链路追踪）
        tid = request.headers.get("X-Trace-Id") or None
        set_trace_id(tid)
        response = await call_next(request)
        response.headers["X-Trace-Id"] = get_trace_id()
        return response
```

注册：`app.add_middleware(TraceIdMiddleware)`，且**必须早于**业务中间件注册（trace_id 要先就位）。

### 3. 后台任务/线程
后台线程、定时任务、消息消费者**不共享请求上下文**，必须在任务入口显式 `set_trace_id()`，结束时 `clear_trace_id()`：

```python
def scheduler_loop():
    while running:
        set_trace_id(uuid.uuid4().hex[:16])
        try:
            do_work()
        finally:
            clear_trace_id()
```

### 4. 跨服务透传
调用第三方/下游服务时，把 `trace_id` 带进请求头：
```python
headers = {"X-Trace-Id": get_trace_id(), ...}
```

---

## 三、请求/响应日志（入参出参）

### 1. 统一中间件
记录每个请求的方法、路径、耗时、状态码，自动带上 `trace_id`。**禁止**在每个路由里手写 `logger.info("收到请求...")`。

```python
# app/middleware/access_log.py
import time
import json
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("app.access")

# 入参出参记录上限，防止大 body 撑爆日志
MAX_BODY_LOG = 2048


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        # 读取请求 body（需回放，否则下游读不到）
        body_bytes = await request.body()

        async def receive():
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        request = Request(request.scope, receive)
        response = await call_next(request)

        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        resp_body = b""
        async for chunk in response.body_iterator:
            resp_body += chunk

        logger.info(
            "req %s %s status=%s latency=%sms",
            request.method, request.url.path, response.status_code, latency_ms,
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "latency_ms": latency_ms,
                "client": request.client.host if request.client else "-",
                "req_body": _clip(body_bytes.decode("utf-8", "ignore")),
                "resp_body": _clip(resp_body.decode("utf-8", "ignore")),
            },
        )
        # 回放响应 body
        from starlette.responses import Response as StarResponse
        return StarResponse(
            content=resp_body, status_code=response.status_code,
            headers=dict(response.headers), media_type=response.media_type,
        )


def _clip(s: str) -> str:
    return s if len(s) <= MAX_BODY_LOG else s[:MAX_BODY_LOG] + f"...(truncated {len(s)}b)"
```

注册：`app.add_middleware(AccessLogMiddleware)`。

### 2. 级别策略
- 正常请求 INFO，慢请求（如 `latency > 2000ms`）WARN。
- 4xx 客户端错误 INFO（不算异常），5xx 服务端错误 ERROR。

### 3. 跳过噪音路径
健康检查、静态资源、`/docs`、`/openapi.json` 等路径不打 access log，避免日志洪泛：

```python
SKIP_PATHS = {"/api/v1/health", "/docs", "/openapi.json", "/redoc"}
if request.url.path in SKIP_PATHS:
    return await call_next(request)
```

---

## 四、日志级别规范

| 级别 | 使用场景 | 示例 |
|------|----------|------|
| DEBUG | 调试细节，生产默认关闭 | `logger.debug("SQL: %s", sql)` |
| INFO | 关键业务节点、正常流程 | `logger.info("订单创建成功 order_id=%s", oid)` |
| WARNING | 可恢复异常、降级、兜底 | `logger.warning("LLM 调用超时，降级返回缓存")` |
| ERROR | 业务异常、第三方失败、需关注 | `logger.exception("飞书下发失败")` |
| CRITICAL | 系统不可用、数据损坏 | `logger.critical("数据库连接丢失")` |

规则：
- 异常分支用 `logger.exception()`（自带堆栈），不用 `logger.error(str(e))` 丢堆栈。
- 循环/高频路径用 DEBUG，避免 INFO 洪泛。
- 第三方调用前后成对日志：调用前 INFO（带参数）、失败 ERROR（带异常和响应）。
- 不要在 `except` 里既 `logger.error` 又 `raise` 再让上层 `logger.error`——只在**最终处理层**记录一次完整异常。

---

## 五、敏感字段脱敏

### 1. 自动脱敏
`JsonFormatter` 已对 `extra` 里的 dict/list 做敏感字段脱敏（见第一节 `_safe`）。

### 2. 手动脱敏
直接拼字符串日志无法被 formatter 拦截，必须手动脱敏：

```python
logger.info(
    "用户登录 mobile=%s pwd=***",
    mask_mobile(user.mobile),
)

def mask_mobile(m: str) -> str:
    return m[:3] + "****" + m[-4:] if len(m) >= 11 else "***"

def mask_idcard(idc: str) -> str:
    return idc[:6] + "********" + idc[-4:] if len(idc) >= 14 else "***"
```

### 3. 禁止打印
- 完整密码、密钥、token、secret、cookie、session
- 完整身份证号、银行卡号、CVV
- 完整 ORM 实体（用关键字段代替：`user_id=%s name=%s`）
- 大 body（用 `_clip` 截断）

---

## 六、业务日志埋点规范

### 1. 关键节点必记
- 接口入口/出口（由 AccessLogMiddleware 兜底，路由内不必再记）
- 业务关键节点：订单创建、支付成功、状态流转、飞书下发等
- 第三方调用：调用前（参数）+ 调用后（结果/异常）
- 后台任务：每次循环开始/结束、单租户处理结果

### 2. 结构化 extra
日志正文写人话（便于 grep），结构化字段用 `extra`（便于检索）：

```python
logger.info(
    "订单支付成功",
    extra={"order_id": oid, "amount_yuan": amount, "user_id": uid, "tenant_id": tid},
)
```

避免 `logger.info(f"订单支付成功 order_id={oid} amount={amount}")`，f-string 串无法被检索结构化字段。

### 3. 多租户/多用户
所有业务日志必须带 `tenant_id` / `user_id`（放入 `extra`），便于按租户/用户排查。

---

## 七、生成代码自检清单
生成/修改日志代码时逐项核对：
- [ ] 是否用 `logging.getLogger(__name__)`，未在模块内 `basicConfig`
- [ ] 是否走统一 `JsonFormatter`，输出结构化 JSON
- [ ] 是否每个请求自动注入 `trace_id` 且响应头回写
- [ ] 后台任务/线程是否入口 `set_trace_id()`、出口 `clear_trace_id()`
- [ ] 入参出参是否由 `AccessLogMiddleware` 统一记录，未在路由内手写
- [ ] 健康检查/静态资源是否跳过 access log
- [ ] 异常分支是否用 `logger.exception` 带堆栈
- [ ] 敏感字段是否脱敏（手机号/身份证/密码/token/cookie）
- [ ] 业务日志是否带 `tenant_id`/`user_id` 等 `extra` 结构化字段
- [ ] 级别是否用对（INFO 正常/WARN 降级/ERROR 异常）
- [ ] 高频路径是否用 DEBUG 避免洪泛
- [ ] 第三方调用是否前后成对日志
- [ ] 裸机部署是否落盘 + 滚动删除（`log_file` 非空 + `max_bytes/rotate_when` 任一配置）
- [ ] 落盘是否只写运行目录 `logs/`，未写进源码目录
- [ ] 容器部署是否 `log_file=None`（不落盘，交给采集系统）
