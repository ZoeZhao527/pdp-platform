"""迁移 Linkstrate运营中台 data.db 全部业务数据到私域运营中台。"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Alert,
    ApiLog,
    Campaign,
    Capability,
    DemandProfile,
    DemandSignal,
    FeedbackEvent,
    FissionTemplate,
    HotVideo,
    Influencer,
    Integration,
    KpiMetric,
    MatchResult,
    OpsChannel,
    ReportDoc,
    Strategy,
    StrategyTask,
)

SOURCE = Path("/Users/zhaoxinyuan/Desktop/Linkstrate-Z/linkstrate-z/data.db")


def _loads(value, fallback=None):
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:  # noqa: BLE001
        return fallback


def _str(value) -> str:
    return "" if value is None else str(value).strip()


def main() -> None:
    settings = get_settings()
    tenant_id = settings.default_tenant_id
    conn = sqlite3.connect(f"file:{SOURCE}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    signal_map: dict[int, str] = {}
    profile_map: dict[int, str] = {}
    product_map: dict[int, str] = {}
    strategy_map: dict[int, str] = {}

    with SessionLocal() as db:
        # 信号
        signal_added = 0
        for row in conn.execute("SELECT * FROM signals").fetchall():
            raw = _str(row["raw_text"])
            source_type = _str(row["source"]) or "legacy"
            dup = (
                db.query(DemandSignal)
                .filter(
                    DemandSignal.tenant_id == tenant_id,
                    DemandSignal.raw_content == raw,
                    DemandSignal.source_type == source_type,
                )
                .first()
            )
            if dup:
                signal_map[row["id"]] = dup.id
                continue
            signal = DemandSignal(
                tenant_id=tenant_id,
                source_type=source_type,
                segment=_str(row["segment"]) or None,
                raw_content=raw,
                status=_str(row["status"]) or "new",
            )
            db.add(signal)
            db.flush()
            signal_map[row["id"]] = signal.id
            signal_added += 1

        # 需求
        demand_added = 0
        for row in conn.execute("SELECT * FROM demands").fetchall():
            old_signal_id = row["signal_id"]
            signal_id = signal_map.get(old_signal_id)
            if signal_id is None:
                signal = DemandSignal(
                    tenant_id=tenant_id,
                    source_type="legacy",
                    raw_content=_str(row["summary"]),
                    status="labeled",
                )
                db.add(signal)
                db.flush()
                signal_id = signal.id
            profile = DemandProfile(
                tenant_id=tenant_id,
                signal_id=signal_id,
                tags_json=_loads(row["tags"], {"tags": []}),
                scenario=_str(row["category"]) or "待分类",
                intensity=1,
                confidence=row["confidence"] or 0,
                evidence=_str(row["evidence"]) or None,
                verified=bool(row["verified"]),
            )
            db.add(profile)
            db.flush()
            profile_map[row["id"]] = profile.id
            demand_added += 1

        # 品项 -> 能力
        product_added = 0
        for row in conn.execute("SELECT * FROM products").fetchall():
            name = _str(row["name"])
            dup = (
                db.query(Capability)
                .filter(Capability.tenant_id == tenant_id, Capability.product == name)
                .first()
            )
            if dup:
                product_map[row["id"]] = dup.id
                continue
            capability = Capability(
                tenant_id=tenant_id,
                category=_str(row["category"]) or None,
                industry="美业",
                product=name,
                capability=_str(row["description"]) or name,
                price=row["price"] or 0,
                price_band=_str(row["price_band"]) or None,
                efficacy_json=_loads(row["efficacy"], []),
                segments_json=_loads(row["segments"], []),
                seasons_json=_loads(row["seasons"], []),
                description=_str(row["description"]) or None,
                is_focus=bool(row["is_focus"]),
                match_rules_json={"keywords": _loads(row["efficacy"], [])},
            )
            db.add(capability)
            db.flush()
            product_map[row["id"]] = capability.id
            product_added += 1

        # 匹配
        match_added = 0
        for row in conn.execute("SELECT * FROM matches").fetchall():
            demand_id = profile_map.get(row["demand_id"])
            product_id = product_map.get(row["product_id"])
            if not demand_id or not product_id:
                continue
            db.add(
                MatchResult(
                    tenant_id=tenant_id,
                    demand_id=demand_id,
                    product_id=product_id,
                    score=row["score"] or 0,
                    reasons_json=_loads(row["reasons"], []),
                )
            )
            match_added += 1

        # 策略
        strategy_added = 0
        for row in conn.execute("SELECT * FROM strategies").fetchall():
            title = _str(row["title"])
            dup = (
                db.query(Strategy)
                .filter(Strategy.tenant_id == tenant_id, Strategy.name == title)
                .first()
            )
            if dup:
                strategy_map[row["id"]] = dup.id
                continue
            strategy = Strategy(
                tenant_id=tenant_id,
                name=title,
                strategy_type="campaign",
                agent_key="content_writer",
                params_json={
                    "card_ids": _loads(row["card_ids"], []),
                    "audience": _str(row["audience"]),
                    "hook": _str(row["hook"]),
                    "script": _str(row["script"]),
                    "task": _str(row["task"]),
                    "acceptance": _str(row["acceptance"]),
                    "week": _str(row["week"]),
                },
                status=_str(row["status"]) or "草稿",
                managed=bool(row["managed"]),
                enabled=True,
            )
            db.add(strategy)
            db.flush()
            strategy_map[row["id"]] = strategy.id
            strategy_added += 1

        # 热点
        topic_added = 0
        for row in conn.execute("SELECT * FROM topics").fetchall():
            keyword = _str(row["keyword"])
            dup = (
                db.query(DemandSignal)
                .filter(
                    DemandSignal.tenant_id == tenant_id,
                    DemandSignal.source_type == "topic",
                    DemandSignal.raw_content == keyword,
                )
                .first()
            )
            if dup:
                continue
            db.add(
                DemandSignal(
                    tenant_id=tenant_id,
                    source_type="topic",
                    raw_content=keyword,
                    status="new",
                )
            )
            topic_added += 1

        # KPI
        kpi_added = 0
        for row in conn.execute("SELECT * FROM kpi").fetchall():
            metric = _str(row["metric"])
            if db.query(KpiMetric).filter(
                KpiMetric.tenant_id == tenant_id, KpiMetric.metric == metric
            ).first():
                continue
            db.add(
                KpiMetric(
                    tenant_id=tenant_id,
                    week=_str(row["week"]),
                    metric=metric,
                    target=row["target"] or 0,
                    actual=row["actual"] or 0,
                    lower_better=bool(row["lower_better"]),
                    note=_str(row["note"]) or None,
                )
            )
            kpi_added += 1

        # 集成
        integration_map: dict[int, str] = {}
        for row in conn.execute("SELECT * FROM integrations").fetchall():
            name = _str(row["name"])
            integration = Integration(
                tenant_id=tenant_id,
                name=name,
                kind=_str(row["kind"]),
                api_key=_str(row["api_key"]),
                enabled=bool(row["enabled"]),
            )
            db.add(integration)
            db.flush()
            integration_map[row["id"]] = integration.id

        # 任务
        task_map: dict[int, str] = {}
        for row in conn.execute("SELECT * FROM strategy_tasks").fetchall():
            task = StrategyTask(
                tenant_id=tenant_id,
                strategy_id=strategy_map.get(row["strategy_id"]),
                title=_str(row["title"]),
                channel=_str(row["channel"]) or None,
                audience=_str(row["audience"]) or None,
                script=_str(row["script"]) or None,
                acceptance=_str(row["acceptance"]) or None,
                status=_str(row["status"]) or "待执行",
                external_ref=_str(row["external_ref"]) or None,
                due_at=_str(row["due_at"]) or None,
            )
            db.add(task)
            db.flush()
            task_map[row["id"]] = task.id

        # 反馈、告警、接口日志、渠道、活动、裂变、汇报、达人、视频
        for row in conn.execute("SELECT * FROM feedback_events").fetchall():
            db.add(
                FeedbackEvent(
                    tenant_id=tenant_id,
                    task_id=task_map.get(row["task_id"]),
                    action=_str(row["action"]),
                    amount=row["amount"] or 0,
                    note=_str(row["note"]) or None,
                    occurred_at=_str(row["occurred_at"]) or None,
                )
            )
        for row in conn.execute("SELECT * FROM alerts").fetchall():
            db.add(
                Alert(
                    tenant_id=tenant_id,
                    task_id=task_map.get(row["task_id"]),
                    alert_type=_str(row["type"]),
                    message=_str(row["message"]),
                    resolved=bool(row["resolved"]),
                )
            )
        for row in conn.execute("SELECT * FROM api_logs").fetchall():
            db.add(
                ApiLog(
                    tenant_id=tenant_id,
                    integration_id=integration_map.get(row["integration_id"]),
                    path=_str(row["path"]),
                    method=_str(row["method"]),
                    status=row["status"] or 200,
                )
            )
        for row in conn.execute("SELECT * FROM channels").fetchall():
            name = _str(row["name"])
            if db.query(OpsChannel).filter(OpsChannel.tenant_id == tenant_id, OpsChannel.name == name).first():
                continue
            db.add(
                OpsChannel(
                    tenant_id=tenant_id,
                    name=name,
                    kind=_str(row["kind"]),
                    enabled=bool(row["enabled"]),
                    timeout_seconds=row["timeout_seconds"] or 3600,
                    follow_up_hours=row["follow_up_hours"] or 24,
                    sensitive_words=_str(row["sensitive_words"]) or None,
                )
            )
        for row in conn.execute("SELECT * FROM campaigns").fetchall():
            db.add(
                Campaign(
                    tenant_id=tenant_id,
                    name=_str(row["name"]),
                    channel=_str(row["channel"]) or None,
                    budget=row["budget"] or 0,
                    target_leads=row["target_leads"] or 0,
                    status=_str(row["status"]) or "草稿",
                    start_at=_str(row["start_at"]) or None,
                    end_at=_str(row["end_at"]) or None,
                )
            )
        for row in conn.execute("SELECT * FROM fission_templates").fetchall():
            db.add(
                FissionTemplate(
                    tenant_id=tenant_id,
                    name=_str(row["name"]),
                    description=_str(row["description"]) or None,
                    channel=_str(row["channel"]) or None,
                    reward=_str(row["reward"]) or None,
                    rule=_str(row["rule"]) or None,
                )
            )
        for row in conn.execute("SELECT * FROM reports").fetchall():
            db.add(
                ReportDoc(
                    tenant_id=tenant_id,
                    kind=_str(row["kind"]) or "周报",
                    title=_str(row["title"]),
                    content=_str(row["content"]),
                )
            )
        for row in conn.execute("SELECT * FROM influencers").fetchall():
            name = _str(row["name"])
            dup = (
                db.query(Influencer)
                .filter(Influencer.tenant_id == tenant_id, Influencer.name == name, Influencer.source == "Linkstrate运营中台")
                .first()
            )
            if dup:
                continue
            db.add(
                Influencer(
                    tenant_id=tenant_id,
                    name=name,
                    platform=_str(row["platform"]) or "抖音",
                    fans=row["fans"] or 0,
                    avg_plays=row["avg_plays"] or 0,
                    likes=row["likes"] or 0,
                    comments=row["comments"] or 0,
                    shares=row["shares"] or 0,
                    interaction_rate=row["interaction_rate"] or 0,
                    verticality=row["verticality"] or 0,
                    gmv=row["gmv"] or 0,
                    conversion_rate=row["conversion_rate"] or 0,
                    risk=row["risk"] or 0,
                    score=row["score"] or 0,
                    grade=_str(row["grade"]) or "C",
                    suggestion=_str(row["suggestion"]) or "观察",
                    source="Linkstrate运营中台",
                    level_label=_str(row["level_label"]) or None,
                    fit_projects=_str(row["fit_projects"]) or None,
                    budget=_str(row["budget"]) or None,
                    competitors=_str(row["competitors"]) or None,
                    notes=_str(row["notes"]) or None,
                )
            )
        for row in conn.execute("SELECT * FROM hot_videos").fetchall():
            title = _str(row["title"])
            if db.query(HotVideo).filter(HotVideo.tenant_id == tenant_id, HotVideo.title == title).first():
                continue
            db.add(
                HotVideo(
                    tenant_id=tenant_id,
                    title=title,
                    influencer_name=_str(row["influencer_name"]) or None,
                    category=_str(row["category"]) or "短视频种草",
                    plays=row["plays"] or 0,
                    likes=row["likes"] or 0,
                    comments=row["comments"] or 0,
                    shares=row["shares"] or 0,
                    heat=row["heat"] or 0,
                    tags=_str(row["tags"]) or None,
                    related_demand=_str(row["related_demand"]) or None,
                    source="Linkstrate运营中台",
                )
            )

        db.commit()
        conn.close()
        print("===== Linkstrate运营中台 数据迁移汇总 =====")
        print(f"信号新增: {signal_added}")
        print(f"需求新增: {demand_added}")
        print(f"品项新增: {product_added}")
        print(f"匹配新增: {match_added}")
        print(f"策略新增: {strategy_added}")
        print(f"热点新增: {topic_added}")
        print(f"KPI新增: {kpi_added}")


if __name__ == "__main__":
    main()
