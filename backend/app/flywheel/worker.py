"""进程内自动化 worker：实时信号闭环 + 托管任务自动执行。"""

from __future__ import annotations

import logging
import queue
import threading

from app.channels.gateway import channel_gateway
from app.db import SessionLocal
from app.flywheel.pipeline import FlywheelService
from app.llm_gateway.router import LLMRouter
from app.memory.service import MemoryService
from app.models import DemandSignal, Strategy, StrategyTask
from app.orchestration.executor import execute_channel_task
from app.orchestration.engine import OrchestrationEngine

logger = logging.getLogger(__name__)

_queue: queue.Queue = queue.Queue()
_stop = threading.Event()
_thread: threading.Thread | None = None


def enqueue_signal(signal_id: str) -> None:
    _queue.put(("signal", signal_id))


def enqueue_task(task_id: str) -> None:
    _queue.put(("task", task_id))


def _handle_signal(signal_id: str) -> None:
    with SessionLocal() as db:
        signal = db.get(DemandSignal, signal_id)
        if signal is None or signal.status != "new":
            return
        # 后台 worker 只自动处理热点信号；消息/指令信号走人工触发的生成流程，避免抢占 LLM。
        if signal.source_type != "topic":
            return
        signal.status = "processing"
        db.commit()
        try:
            llm_router = LLMRouter(db)
            memory = MemoryService(db)
            engine = OrchestrationEngine(db, llm_router, memory)
            flywheel = FlywheelService(db, llm_router, engine)
            flywheel.process_signal(signal.tenant_id, signal)
            logger.info("信号实时闭环完成: %s", signal_id)
        except Exception:  # noqa: BLE001
            signal.status = "new"
            db.commit()
            logger.exception("信号实时闭环失败: %s", signal_id)


def _handle_task(task_id: str) -> None:
    with SessionLocal() as db:
        task = db.get(StrategyTask, task_id)
        if task is None or task.status != "待执行":
            return
        if (task.result_json or {}).get("child"):
            try:
                execute_channel_task(db, task)
                logger.info("渠道任务自动执行完成: %s", task_id)
            except Exception:  # noqa: BLE001
                db.rollback()
                fresh = db.get(StrategyTask, task_id)
                if fresh is not None:
                    fresh.status = "已失败"
                    db.commit()
                logger.exception("渠道任务自动执行失败: %s", task_id)
            return
        task.status = "执行中"
        db.commit()
        try:
            strategy = db.get(Strategy, task.strategy_id) if task.strategy_id else None
            agent_key = strategy.agent_key if strategy else "ops_assistant"
            llm_router = LLMRouter(db)
            memory = MemoryService(db)
            engine = OrchestrationEngine(db, llm_router, memory)
            params = (strategy.params_json or {}) if strategy else {}
            text = params.get("script") or task.script or task.title
            result = engine.run(task.tenant_id, agent_key, input_data={"text": text})
            task.result_json = {"reply": result["reply"], "model": result.get("model", "local")}
            task.status = "已完成"
            channel_gateway.send("mock", task.id, task.id, result["reply"], {})
            db.commit()
            logger.info("任务自动执行完成: %s", task_id)
        except Exception:  # noqa: BLE001
            task.status = "已失败"
            db.commit()
            logger.exception("任务自动执行失败: %s", task_id)


def _loop() -> None:
    while not _stop.is_set():
        try:
            kind, obj_id = _queue.get(timeout=1)
        except queue.Empty:
            continue
        try:
            if kind == "signal":
                _handle_signal(obj_id)
            elif kind == "task":
                _handle_task(obj_id)
        except Exception:  # noqa: BLE001
            logger.exception("worker 处理失败: %s %s", kind, obj_id)


def start_worker() -> None:
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, daemon=True)
    _thread.start()
    logger.info("自动化 worker 已启动")


def stop_worker() -> None:
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=2)
