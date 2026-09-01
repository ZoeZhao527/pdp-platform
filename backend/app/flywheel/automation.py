"""需求飞轮自动化：热点信号采集 + 待处理信号自动闭环。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.flywheel.collectors import collect_all
from app.flywheel.pipeline import FlywheelService
from app.flywheel.relevance import score_relevance
from app.flywheel.worker import enqueue_signal
from app.models import DemandSignal, Industry, Strategy, StrategyTask, Tenant
from app.orchestration.executor import dispatch_due_plan_todos, materialize_strategy_plan_todos

logger = logging.getLogger(__name__)
last_run_state: dict[str, Any] = {"time": None, "sources": []}


class FlywheelAutomation:
    def __init__(self, db: Session, flywheel: FlywheelService) -> None:
        self.db = db
        self.flywheel = flywheel

    def collect_topics(self, tenant_id: str) -> dict[str, Any]:
        rows, results = collect_all()
        tenant = self.db.get(Tenant, tenant_id)
        industry_id = tenant.industry_id if tenant else None
        industry_code = None
        if industry_id:
            industry = self.db.get(Industry, industry_id)
            industry_code = industry.code if industry else None
        removed_irrelevant = 0
        if industry_code:
            existing_topics = (
                self.db.query(DemandSignal)
                .filter(
                    DemandSignal.tenant_id == tenant_id,
                    DemandSignal.industry_id == industry_id,
                    DemandSignal.source_type == "topic",
                )
                .all()
            )
            for signal in existing_topics:
                if score_relevance(signal.raw_content, industry_code) < 0.3:
                    self.db.delete(signal)
                    removed_irrelevant += 1
        added = 0
        skipped = 0
        filtered = 0
        added_ids: list[str] = []
        seen: set[tuple[str, str]] = set()
        for source_key, platform, keyword, heat, trend in rows:
            relevance = score_relevance(keyword, industry_code)
            if relevance < 0.3:
                filtered += 1
                continue
            key = (source_key, keyword)
            if key in seen:
                continue
            seen.add(key)
            duplicate = (
                self.db.query(DemandSignal)
                .filter(
                    DemandSignal.tenant_id == tenant_id,
                    DemandSignal.source_type == "topic",
                    DemandSignal.raw_content == keyword,
                )
                .first()
            )
            if duplicate:
                skipped += 1
                continue
            signal = DemandSignal(
                tenant_id=tenant_id,
                industry_id=industry_id,
                source_type="topic",
                raw_content=keyword,
                status="new",
            )
            self.db.add(signal)
            self.db.flush()
            added_ids.append(signal.id)
            added += 1
        self.db.commit()
        for signal_id in added_ids:
            enqueue_signal(signal_id)
        last_run_state["time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        last_run_state["sources"] = results
        return {
            "fetched": len(rows),
            "filtered_irrelevant": filtered,
            "removed_irrelevant": removed_irrelevant,
            "added": added,
            "skipped_duplicate": skipped,
            "sources": results,
        }

    def process_pending(self, tenant_id: str, limit: int = 5) -> dict[str, Any]:
        signals = (
            self.db.query(DemandSignal)
            .filter(
                DemandSignal.tenant_id == tenant_id,
                DemandSignal.status == "new",
                DemandSignal.source_type == "topic",
            )
            .order_by(DemandSignal.created_at.asc())
            .limit(limit)
            .all()
        )
        results = []
        for signal in signals:
            try:
                results.append(self.flywheel.process_signal(tenant_id, signal))
            except Exception as exc:  # noqa: BLE001
                logger.warning("信号处理失败 %s: %s", signal.id, exc)
        return {"processed": len(results), "limit": limit}

    def dispatch_managed_strategies(self, tenant_id: str) -> dict[str, Any]:
        now = datetime.now()
        now_text = now.strftime("%Y-%m-%d %H:%M:%S")
        strategies = (
            self.db.query(Strategy)
            .filter(
                Strategy.tenant_id == tenant_id,
                Strategy.managed.is_(True),
                Strategy.enabled.is_(True),
            )
            .all()
        )
        dispatched = 0
        for strategy in strategies:
            if strategy.next_run_at and strategy.next_run_at > now_text:
                continue
            dispatched += materialize_strategy_plan_todos(self.db, strategy)
            cycle = strategy.run_cycle or 1440
            strategy.last_run_at = now_text
            strategy.next_run_at = (
                now.replace(second=0, microsecond=0) + timedelta(minutes=cycle)
            ).strftime("%Y-%m-%d %H:%M:%S")
        self.db.commit()
        if dispatched:
            dispatch_due_plan_todos(self.db, tenant_id)
        return {"dispatched": dispatched}

    def run(
        self,
        tenant_id: str,
        pending_limit: int = 5,
        collect_topics: bool = True,
    ) -> dict[str, Any]:
        topics = self.collect_topics(tenant_id) if collect_topics else {"skipped": True}
        pending = self.process_pending(tenant_id, limit=pending_limit)
        managed = self.dispatch_managed_strategies(tenant_id)
        return {"topics": topics, "pending": pending, "managed": managed}
