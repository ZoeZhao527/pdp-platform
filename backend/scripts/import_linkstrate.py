"""从 Linkstrate-Z data.db 迁移热搜信号与策略到需求飞轮。"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import DemandSignal, Strategy  # noqa: E402

LINKSTRATE_DB = Path("/Users/zhaoxinyuan/Desktop/Linkstrate联策/app/data.db")


def main() -> None:
    settings = get_settings()
    tenant_id = settings.default_tenant_id

    conn = sqlite3.connect(f"file:{LINKSTRATE_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    topic_rows = conn.execute(
        "SELECT platform, keyword, heat, trend, mapped_demand, week, fetched_at FROM topics"
    ).fetchall()
    strategy_rows = conn.execute(
        "SELECT title, card_ids, audience, hook, script, task, acceptance, status, week FROM strategies"
    ).fetchall()
    conn.close()

    with SessionLocal() as db:
        topic_added = 0
        topic_skipped = 0
        for row in topic_rows:
            keyword = (row["keyword"] or "").strip()
            if not keyword:
                continue
            exists = (
                db.query(DemandSignal)
                .filter(
                    DemandSignal.tenant_id == tenant_id,
                    DemandSignal.source_type == "topic",
                    DemandSignal.raw_content == keyword,
                )
                .first()
            )
            if exists:
                topic_skipped += 1
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

        strategy_added = 0
        strategy_skipped = 0
        for row in strategy_rows:
            title = (row["title"] or "").strip()
            if not title:
                continue
            exists = (
                db.query(Strategy)
                .filter(Strategy.tenant_id == tenant_id, Strategy.name == title)
                .first()
            )
            if exists:
                strategy_skipped += 1
                continue
            db.add(
                Strategy(
                    tenant_id=tenant_id,
                    name=title,
                    strategy_type="campaign",
                    agent_key="content_writer",
                    params_json={
                        "audience": row["audience"],
                        "hook": row["hook"],
                        "script": row["script"],
                        "task": row["task"],
                        "acceptance": row["acceptance"],
                        "status": row["status"],
                        "week": row["week"],
                        "card_ids": row["card_ids"],
                    },
                    enabled=True,
                )
            )
            strategy_added += 1

        db.commit()
        print("===== Linkstrate-Z 迁移汇总 =====")
        print(f"热搜信号新增: {topic_added}，跳过重复: {topic_skipped}")
        print(f"策略新增: {strategy_added}，跳过重复: {strategy_skipped}")


if __name__ == "__main__":
    main()

