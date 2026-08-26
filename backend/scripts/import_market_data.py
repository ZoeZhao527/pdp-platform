"""从 Linkstrate-Z data.db 迁移市场情报：达人、热门视频、行业报告板块。"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import HotVideo, Influencer, ReportBlock  # noqa: E402

LINKSTRATE_DB = Path("/Users/zhaoxinyuan/Desktop/Linkstrate联策/app/data.db")


def main() -> None:
    settings = get_settings()
    tenant_id = settings.default_tenant_id

    conn = sqlite3.connect(f"file:{LINKSTRATE_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    influencers = conn.execute("SELECT * FROM influencers").fetchall()
    hot_videos = conn.execute("SELECT * FROM hot_videos").fetchall()
    report_blocks = conn.execute("SELECT * FROM report_blocks").fetchall()
    conn.close()

    with SessionLocal() as db:
        inf_added = 0
        for row in influencers:
            name = (row["name"] or "").strip()
            if not name:
                continue
            exists = db.query(Influencer).filter(
                Influencer.tenant_id == tenant_id, Influencer.name == name
            ).first()
            if exists:
                continue
            db.add(
                Influencer(
                    tenant_id=tenant_id,
                    name=name,
                    platform=row["platform"] or "抖音",
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
                    grade=row["grade"] or "C",
                    suggestion=row["suggestion"] or "观察",
                    source=row["source"] or "demo",
                    level_label=row["level_label"],
                    fit_projects=row["fit_projects"],
                    budget=row["budget"],
                    competitors=row["competitors"],
                    notes=row["notes"],
                )
            )
            inf_added += 1

        video_added = 0
        for row in hot_videos:
            title = (row["title"] or "").strip()
            if not title:
                continue
            exists = db.query(HotVideo).filter(
                HotVideo.tenant_id == tenant_id, HotVideo.title == title
            ).first()
            if exists:
                continue
            db.add(
                HotVideo(
                    tenant_id=tenant_id,
                    title=title,
                    influencer_name=row["influencer_name"],
                    category=row["category"] or "短视频种草",
                    plays=row["plays"] or 0,
                    likes=row["likes"] or 0,
                    comments=row["comments"] or 0,
                    shares=row["shares"] or 0,
                    heat=row["heat"] or 0,
                    tags=row["tags"],
                    related_demand=row["related_demand"],
                    source=row["source"] or "demo",
                )
            )
            video_added += 1

        block_added = 0
        for row in report_blocks:
            block = (row["block"] or "").strip()
            if not block:
                continue
            exists = db.query(ReportBlock).filter(
                ReportBlock.tenant_id == tenant_id, ReportBlock.block == block
            ).first()
            if exists:
                continue
            data = row["data"]
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except Exception:  # noqa: BLE001
                    data = {"raw": data}
            db.add(
                ReportBlock(
                    tenant_id=tenant_id,
                    block=block,
                    title=row["title"],
                    data_json=data,
                )
            )
            block_added += 1

        db.commit()
        print("===== 市场情报迁移汇总 =====")
        print(f"达人: {inf_added}")
        print(f"热门视频: {video_added}")
        print(f"报告板块: {block_added}")


if __name__ == "__main__":
    main()

