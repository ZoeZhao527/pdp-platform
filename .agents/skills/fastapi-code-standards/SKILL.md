---
name: "fastapi-code-standards"
description: "FastAPI code conventions: unified Response[T] wrapper, BizException + global exception_handler, Pydantic v2 Annotated validation, routers→services→repositories layering. Invoke when creating or modifying any backend/app/*.py, FastAPI router, service, schema, or repository. Trigger words: 新增接口/改后端/FastAPI/router/service/schema/DTO/VO. Do not invoke for frontend, scripts, docs, or non-Python files."
---

# FastAPI 代码规范

本规范适用于 FastAPI + Pydantic v2 + SQLAlchemy 2.x 项目。生成或修改后端代码时**必须遵循**，确保统一返回体、统一异常处理、参数校验、分层命名四项核心规范一致。

核心口诀：**入参用 SchemaIn，出参用 SchemaOut，数据库用 ORM Model，路由薄、服务厚，返回统一 Response，异常统一拦截**。

---

## 一、统一返回体（Response）

### 1. 全局返回结构
所有接口强制共用一套返回包装类，前端/网关统一解析，禁止自定义返回结构。

```python
# app/schemas/response.py
from typing import Any, Generic, TypeVar
from time import time
from pydantic import BaseModel

T = TypeVar("T")


class Response(BaseModel, Generic[T]):
    code: int = 200
    msg: str = "操作成功"
    data: T | None = None
    timestamp: int = int(time() * 1000)


class PageItem(BaseModel, Generic[T]):
    items: list[T] = []
    total: int = 0
    pages: int = 0
    size: int = 10
    current: int = 1


class PageResponse(BaseModel, Generic[T]):
    code: int = 200
    msg: str = "操作成功"
    data: PageItem[T]
    timestamp: int = int(time() * 1000)
```

### 2. 响应码规范
| 段位 | 含义 | 示例 |
|------|------|------|
| 200 | 成功 | 200 |
| 1001 | 参数校验失败 | 1001 |
| 1002 | 数据不存在 | 1002 |
| 1003 | 权限不足 | 1003 |
| 1004 | 业务状态非法 | 1004 |
| 5000 | 服务器内部错误 | 5000 |
| 5001 | 数据库异常 | 5001 |
| 5002 | 第三方接口调用失败 | 5002 |

业务异常统一用 `1xxx`，系统异常统一用 `5xxx`，禁止散落。

### 3. 自动包装
通过自定义 `APIRoute` 或中间件，让路由返回裸数据时自动包成 `Response`；路由显式返回 `Response[T]` 时不再二次包装。避免每个手写 `Response(data=...)`。

```python
# app/core/route.py
import json
from fastapi import Request, Response as FastAPIResponse
from fastapi.routing import APIRoute
from starlette.responses import JSONResponse
from app.schemas.response import Response as ApiResponse


class AutoWrapRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def custom_handler(request: Request):
            raw = await original(request)
            # 已经是标准 Response 结构则直通
            payload = getattr(raw, "body", b"")
            try:
                parsed = json.loads(payload)
                if isinstance(parsed, dict) and {"code", "msg", "data"}.issubset(parsed.keys()):
                    return raw
            except Exception:
                pass
            # 否则包装
            data = json.loads(payload) if payload else None
            wrapped = ApiResponse(code=200, msg="操作成功", data=data).model_dump()
            return JSONResponse(wrapped, status_code=raw.status_code, headers=dict(raw.headers))

        return custom_handler
```

应用：`app.router.route_class = AutoWrapRoute`，或每个 `APIRouter(route_class=AutoWrapRoute)`。

---

## 二、统一异常处理

### 1. 业务异常
```python
# app/core/exceptions.py
class BizException(Exception):
    """业务异常，带标准化 code + msg。"""
    def __init__(self, code: int = 5000, msg: str = "服务器内部错误"):
        self.code = code
        self.msg = msg
        super().__init__(msg)


class ValidationError(BizException):
    def __init__(self, msg: str = "参数校验失败"):
        super().__init__(code=1001, msg=msg)


class NotFoundError(BizException):
    def __init__(self, msg: str = "数据不存在"):
        super().__init__(code=1002, msg=msg)


class ForbiddenError(BizException):
    def __init__(self, msg: str = "权限不足"):
        super().__init__(code=1003, msg=msg)
```

### 2. 全局异常处理器
统一拦截，统一返回 `Response` 结构，统一记录日志。

```python
# app/main.py
import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.core.exceptions import BizException
from app.schemas.response import Response

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BizException)
    async def on_biz(_: Request, exc: BizException):
        logger.warning("业务异常 code=%s msg=%s", exc.code, exc.msg)
        return JSONResponse(Response(code=exc.code, msg=exc.msg).model_dump(), status_code=200)

    @app.exception_handler(RequestValidationError)
    async def on_validation(_: Request, exc: RequestValidationError):
        # 把 Pydantic 校验错误格式化成中文提示
        msgs = []
        for err in exc.errors():
            loc = ".".join(str(x) for x in err.get("loc", []))
            msgs.append(f"{loc}: {err.get('msg','')}")
        text = "；".join(msgs) or "参数校验失败"
        logger.info("参数校验失败: %s", text)
        return JSONResponse(Response(code=1001, msg=text).model_dump(), status_code=200)

    @app.exception_handler(Exception)
    async def on_unknown(_: Request, exc: Exception):
        logger.exception("系统异常")
        return JSONResponse(Response(code=5000, msg="服务器内部错误").model_dump(), status_code=500)
```

### 3. 使用边界
- 路由层：**禁止** `raise HTTPException`，改用 `raise BizException / NotFoundError / ForbiddenError`。
- 服务层：业务校验失败 `raise BizException(code=1004, msg="订单状态不允许取消")`。
- 第三方调用失败：`raise BizException(code=5002, msg="LLM 调用失败")`，并在 `except` 中记录 ERROR 日志。
- 已知不可恢复错误才抛异常；可预期的空结果用空集合/None，不抛异常。

---

## 三、参数校验规范

### 1. Schema 命名
| 用途 | 命名 | 示例 |
|------|------|------|
| 创建入参 | `XxxCreateIn` | `OrderCreateIn` |
| 更新入参 | `XxxUpdateIn` | `OrderUpdateIn` |
| 查询/分页入参 | `XxxQueryIn` | `OrderQueryIn` |
| 单条出参 | `XxxOut` | `OrderOut` |
| 列表出参 | `XxxListOut` | `OrderListOut` |
| 分页出参 | 用 `PageResponse[XxxOut]` | — |

**禁用**：`XxxBean` / `XxxModel` / `XxxDTO`（Pydantic 项目统一用 `In/Out` 后缀，避免与 Java 体系混淆）、单独用 `id` 模糊命名（必须 `userId`/`orderId` 语义化）。

### 2. Pydantic v2 校验（推荐 Annotated + Field 风格）
```python
from typing import Annotated
from pydantic import BaseModel, Field, field_validator

class OrderCreateIn(BaseModel):
    userId: Annotated[str, Field(min_length=1, description="用户ID")]
    title: Annotated[str, Field(min_length=1, max_length=64, description="订单标题")]
    amountYuan: Annotated[float, Field(ge=0, description="金额(元)")]
    mobile: Annotated[str, Field(pattern=r"^1[3-9]\d{9}$", description="手机号")]
    remark: Annotated[str | None, Field(default=None, max_length=200)] = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("订单标题不能为空")
        return v.strip()
```

规则：
- 必填字段必须配约束（`min_length`/`ge`/`pattern` 等），并用 `description` 说明。
- 所有字段用 **Optional/`| None`** 表达可空，可空字段必须给 `default=None`。
- 类型用包装类型语义：`str | None`、`int | None`，避免 `Optional` 混用。
- 布尔字段禁用 `isXxx` 命名（防序列化异常），用 `deleted` / `enabled`。
- 日期统一 `datetime`，禁用 `date` 字符串裸传；金额用 `Decimal`（元），禁用 `float` 做金额（除非仅展示）。
- 复杂校验（手机号、日期范围、依赖字段）用 `@field_validator` / `@model_validator`，不在路由层写 `if`。

### 3. 路径/查询参数校验
```python
from fastapi import Path, Query

@router.get("/{order_id}")
def get_order(order_id: Annotated[str, Path(description="订单ID")]):
    ...

@router.get("")
def list_orders(
    page: Annotated[int, Query(ge=1, default=1, description="页码")],
    size: Annotated[int, Query(ge=1, le=100, default=10, description="页大小")],
    keyword: Annotated[str | None, Query(default=None, max_length=64)] = None,
):
    ...
```

---

## 四、分层与命名规范

### 1. 目录结构
```
app/
  api/routers/        路由层：接收参数、校验、调用 service、返回 Out
  services/           业务层：业务逻辑，组合多个 repository
  repositories/       数据访问层：纯 CRUD，基于 ORM Model
  models.py           ORM 模型（SQLAlchemy），与表一一对应
  schemas/            Pydantic Schema：In/Out/Query/Response
  core/               基础设施：exceptions、route、logging、deps
```

### 2. 层职责与禁令
| 层 | 职责 | 禁止 |
|----|------|------|
| routers | 解析参数、调 service、组装 `XxxOut`、返回 | 直接操作 ORM/数据库；写业务逻辑；`raise HTTPException` |
| services | 业务逻辑、跨 repository 编排、对象转换 | 直接返回 HTTP 状态；注入 `Request`；跨 service 互相循环调用 |
| repositories | 纯 CRUD、通用查询、分页 | 写业务逻辑；抛业务异常 |
| models | 表映射，仅字段+关系 | 暴露到路由层返回；写业务方法 |

### 3. 命名约定
- 路由文件：`routers/order.py`，`router = APIRouter(prefix="/api/v1/orders", tags=["orders"])`
- 服务：`services/order_service.py`，`class OrderService`
- 数据访问：`repositories/order_repository.py`，`class OrderRepository`
- ORM 模型：`class Order(Base)`，`__tablename__ = "t_order"`
- 路由函数动词：`list_/get/create/update/delete`（与 REST 对齐）
- 服务函数动词：业务动作 `create_order/pay_order/cancel_order`
- 仓储函数：`get/list/save/update/delete`

### 4. 依赖注入
```python
# app/core/deps.py
from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

def get_db(): ...
DbSession = Annotated[Session, Depends(get_db)]

# routers/order.py
@router.post("", response_model=Response[OrderOut])
def create_order(payload: OrderCreateIn, db: DbSession):
    out = OrderService(db).create(payload)
    return out
```

### 5. 对象转换
- 禁止手动大量 `get/set` 拷贝。
- ORM → Out：`OrderOut.model_validate(orm_obj)` 或 `OrderOut.model_validate(orm_obj, from_attributes=True)`。
- In → ORM：显式构造 `Order(**payload.model_dump())`，避免直接透传（过滤无关字段）。
- 敏感字段（密码、盐值、token）**不得**出现在任何 `XxxOut`。

---

## 五、空值与集合约定
- 集合返回统一空集合 `[]`，禁止返回 `null`。
- 字符串空值统一 `""`，禁止 `null`。
- 数值默认：`int|None = None`；金额 `Decimal` 默认 `Decimal("0")`。
- 分页结果用 `PageResponse[T]`，禁止裸 `list` 直接返回。

---

## 六、生成代码自检清单
生成新接口/服务时逐项核对：
- [ ] 返回是否走统一 `Response`（自动包装或显式 `response_model=Response[...]`）
- [ ] 异常是否用 `BizException` 体系，无散落 `HTTPException`
- [ ] 入参是否用 `XxxIn` Schema + `Field` 约束 + `description`
- [ ] 必填字段是否有校验，提示语是否中文且明确
- [ ] 是否分层：路由不写业务、服务不返回 HTTP、仓储不抛业务异常
- [ ] ORM 是否未直接暴露到路由返回
- [ ] 敏感字段是否未出现在 `XxxOut`
- [ ] 金额是否用 `Decimal`、日期是否用 `datetime`、布尔是否避开 `isXxx`
- [ ] 集合是否返回空集合而非 `null`
- [ ] 命名是否符合 `In/Out/Query`、`router/service/repository` 约定
