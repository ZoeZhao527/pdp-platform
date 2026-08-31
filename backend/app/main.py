import os
import threading
import time
import re
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from logging import getLogger

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.api import admin, agents, auth, channels, conversations, cs_bridge, customers, dev_console, flywheel, guardrails, knowledge, market, platform, strategies
from app.auth import require_auth
from app.api import feishu as feishu_api
from app.config import get_settings
from app.db import SessionLocal, init_db
from app.flywheel.automation import FlywheelAutomation
from app.flywheel.pipeline import FlywheelService
from app.flywheel.worker import start_worker, stop_worker
from app.llm_gateway.router import LLMRouter
from app.memory.service import MemoryService
from app.orchestration.executor import dispatch_due_plan_todos, load_send_policy
from app.orchestration.engine import OrchestrationEngine
from app.seed import seed_default_data
from app.models import Tenant

settings = get_settings()
logger = getLogger(__name__)


# ---------------------------------------------------------------------------
# Beijing-time middleware: converts naive UTC ISO datetimes in JSON to +08:00
# SQLite func.now() stores UTC; this adds 8h so the frontend sees Beijing time.
# ---------------------------------------------------------------------------
_BJ_TZ = timezone(timedelta(hours=8))
# Match ISO datetime with optional microseconds and optional timezone suffix
_DT_RE = re.compile(
    r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?(Z|[+-]\d{2}:?\d{2})?'
)


def _utc_to_bj(match: re.Match) -> str:
    dt_str = match.group(1)
    micro = match.group(2) or ''
    tz = match.group(3)
    if tz:  # already has timezone — leave untouched
        return match.group(0)
    try:
        dt = datetime.fromisoformat(dt_str)
        dt_bj = dt + timedelta(hours=8)
        return dt_bj.strftime('%Y-%m-%dT%H:%M:%S') + '+08:00'
    except Exception:
        return match.group(0)


class BeijingTimeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        ct = response.headers.get('content-type', '')
        if 'application/json' not in ct:
            return response
        try:
            body = b''
            async for chunk in response.body_iterator:
                body += chunk
            text = body.decode('utf-8')
            converted = _DT_RE.sub(_utc_to_bj, text)
            headers = dict(response.headers)
            headers['content-length'] = str(len(converted.encode('utf-8')))
            return Response(
                content=converted.encode('utf-8'),
                status_code=response.status_code,
                headers=headers,
                media_type='application/json',
            )
        except Exception:
            return response


def _all_active_tenant_ids(db) -> list[str]:
    """获取所有 active 状态的租户 ID，保证多品牌调度覆盖。"""
    rows = db.query(Tenant.id).filter(Tenant.status == "active").all()
    return [r[0] for r in rows]


def _daily_brief_loop(stop_event: threading.Event) -> None:
    """早九晚六定时简报调度：9:00 晨间任务清单 / 18:00 晚间运营日报，每天各一次。

    接收消息全程静默（webhook 已禁用回复）；仅在两个固定时点主动发群。
    用「当天已发」标记防重复，后端中途启动也能补发当日未发的简报。
    """
    from app.services.daily_brief import run_morning_dispatch, run_evening_summary

    sent_dates: dict[str, dict[str, str]] = {}
    while not stop_event.is_set():
        try:
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            with SessionLocal() as db:
                from app.integrations.feishu import get_feishu_client
                for tid in _all_active_tenant_ids(db):
                    tenant_state = sent_dates.setdefault(tid, {})
                    client = get_feishu_client(tid)
                    if now.hour >= 9 and tenant_state.get("morning") != today:
                        res = run_morning_dispatch(db, tid, client)
                        logger.info("晨间简报[%s]: %s", tid, res)
                        if res.get("sent") or res.get("error"):
                            tenant_state["morning"] = today
                    if now.hour >= 18 and tenant_state.get("evening") != today:
                        res = run_evening_summary(db, tid, client)
                        logger.info("晚间日报[%s]: %s", tid, res)
                        if res.get("sent") or res.get("error"):
                            tenant_state["evening"] = today
        except Exception:  # noqa: BLE001
            logger.exception("定时简报调度失败")
        stop_event.wait(60)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with SessionLocal() as db:
        seed_default_data(db)

    stop_event = threading.Event()
    scheduler = None
    plan_scheduler = None
    if settings.flywheel_auto_enabled:
        def scheduler_loop() -> None:
            while not stop_event.is_set():
                try:
                    with SessionLocal() as db:
                        for tid in _all_active_tenant_ids(db):
                            llm_router = LLMRouter(db)
                            memory = MemoryService(db)
                            engine = OrchestrationEngine(db, llm_router, memory)
                            flywheel = FlywheelService(db, llm_router, engine)
                            result = FlywheelAutomation(db, flywheel).run(
                                tid,
                                pending_limit=5,
                            )
                            logger.info("需求飞轮自动运行[%s]: %s", tid, result)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("需求飞轮自动运行失败: %s", exc)
                stop_event.wait(settings.flywheel_interval_minutes * 60)

        scheduler = threading.Thread(target=scheduler_loop, daemon=True)
        scheduler.start()
        logger.info("需求飞轮自动化已启动，间隔 %s 分钟", settings.flywheel_interval_minutes)

    def plan_scheduler_loop() -> None:
        while not stop_event.is_set():
            try:
                with SessionLocal() as db:
                    for tid in _all_active_tenant_ids(db):
                        policy = load_send_policy(db, tid)
                        result = dispatch_due_plan_todos(
                            db,
                            tid,
                            policy=policy,
                        )
                        if result["dispatched"] or result["missed"]:
                            logger.info("排期自动下发[%s]: %s", tid, result)
            except Exception:  # noqa: BLE001
                logger.exception("排期自动下发失败")
            stop_event.wait(60)

    plan_scheduler = threading.Thread(target=plan_scheduler_loop, daemon=True)
    plan_scheduler.start()
    logger.info("排期自动下发调度已启动，每 60 秒检查一次")

    brief_thread = threading.Thread(target=_daily_brief_loop, args=(stop_event,), daemon=True)
    brief_thread.start()
    logger.info("定时简报调度已启动（9:00 晨间任务清单 / 18:00 晚间运营日报）")

    start_worker()

    yield
    stop_event.set()
    if scheduler is not None:
        scheduler.join(timeout=2)
    if plan_scheduler is not None:
        plan_scheduler.join(timeout=2)
    if brief_thread is not None:
        brief_thread.join(timeout=2)
    stop_worker()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="消费者运营中台 P0 骨架",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(BeijingTimeMiddleware)

app.include_router(auth.router)
app.include_router(feishu_api.router)
for router in [
    channels.router,
    cs_bridge.router,
    conversations.router,
    customers.router,
    flywheel.router,
    agents.router,
    strategies.router,
    guardrails.router,
    knowledge.router,
    market.router,
    platform.router,
    admin.router,
    dev_console.router,
]:
    app.include_router(router, dependencies=[Depends(require_auth)])


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


class NoCacheStaticFiles(StaticFiles):
    """StaticFiles that sends no-cache headers so browsers always revalidate."""
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response

static_dir = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(__file__)), settings.admin_static_dir)
)
if os.path.isdir(static_dir):
    from fastapi.responses import FileResponse

    @app.get("/", include_in_schema=False)
    def _serve_index():
        return FileResponse(
            os.path.join(static_dir, "index.html"),
            media_type="text/html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )

    app.mount("/", NoCacheStaticFiles(directory=static_dir, html=True), name="admin")
