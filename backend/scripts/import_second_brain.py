"""一次性迁移 SQLBrain 知识库与违禁词到私域运营中台。

来源：/Users/zhaoxinyuan/Desktop/美丽田园cod/SQLBrain/data.db
- knowledge(101) -> knowledge_docs（按分类分册入库，保留标题/标签/原文）
- prohibited_words(23) -> guardrail_rules 品牌违禁词规则合并
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.knowledge.service import KnowledgeService  # noqa: E402
from app.models import GuardrailRule, Industry, KnowledgeDoc  # noqa: E402

SQLBRAIN_DB = Path("/Users/zhaoxinyuan/Desktop/美丽田园cod/SQLBrain/data.db")


def load_source(db_path: Path) -> tuple[list[dict], list[dict], list[str]]:
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    categories = [dict(row) for row in conn.execute("SELECT * FROM categories ORDER BY sort_order, id")]
    knowledge = [dict(row) for row in conn.execute("SELECT * FROM knowledge ORDER BY category_id, id")]
    words = [row["word"] for row in conn.execute("SELECT word FROM prohibited_words ORDER BY id")]
    conn.close()
    return categories, knowledge, words


def build_category_text(category_id: int | None, rows: list[dict]) -> str:
    blocks: list[str] = []
    for row in rows:
        title = row["title"] or "未命名知识"
        tags = (row["tags"] or "").strip()
        content = (row["content"] or "").strip()
        head = f"## {title}"
        if tags:
            head += f"\n标签：{tags}"
        blocks.append(f"{head}\n{content}")
    return "\n\n".join(blocks)


def import_knowledge(
    db: Session,
    tenant_id: str,
    industry_id: str,
    categories: list[dict],
    knowledge: list[dict],
) -> int:
    service = KnowledgeService(db)
    existing = {
        row.name
        for row in db.query(KnowledgeDoc)
        .filter(KnowledgeDoc.tenant_id == tenant_id, KnowledgeDoc.industry_id == industry_id)
        .all()
    }
    imported = 0

    for category in categories:
        rows = [row for row in knowledge if row["category_id"] == category["id"]]
        if not rows:
            continue
        name = f"SecondBrain-{category['name']}"[:200]
        if name in existing:
            print(f"[跳过-已存在] {name}")
            continue
        text = build_category_text(category["id"], rows)
        doc = service.ingest(
            tenant_id,
            name,
            text,
            "md",
            len(text.encode("utf-8")),
            industry_id=industry_id,
        )
        imported += 1
        print(f"[导入] {name} -> {doc.chunk_count} 切片 / {len(rows)} 条")

    uncategorized = [row for row in knowledge if row["category_id"] is None]
    if uncategorized:
        name = "SecondBrain-未分类知识"
        if name not in existing:
            text = build_category_text(None, uncategorized)
            doc = service.ingest(
                tenant_id,
                name,
                text,
                "md",
                len(text.encode("utf-8")),
                industry_id=industry_id,
            )
            imported += 1
            print(f"[导入] {name} -> {doc.chunk_count} 切片 / {len(uncategorized)} 条")
    return imported


def import_prohibited_words(db: Session, tenant_id: str, industry_id: str, words: list[str]) -> int:
    rule = (
        db.query(GuardrailRule)
        .filter(
            GuardrailRule.tenant_id == tenant_id,
            GuardrailRule.industry_id == industry_id,
            GuardrailRule.rule_type == "content_safety",
            GuardrailRule.name.like("%违禁词%"),
        )
        .order_by(GuardrailRule.created_at.asc())
        .first()
    )
    if rule is None:
        rule = GuardrailRule(
            tenant_id=tenant_id,
            industry_id=industry_id,
            rule_type="content_safety",
            name="品牌违禁词（SecondBrain）",
            pattern_json={"keywords": []},
            action="block",
            enabled=True,
        )
        db.add(rule)

    existing_words = set(rule.pattern_json.get("keywords", []))
    added = [word for word in words if word and word not in existing_words]
    existing_words.update(added)
    rule.pattern_json = {"keywords": sorted(existing_words)}
    db.commit()
    print(f"[护栏] {rule.name}: 原有 {len(existing_words) - len(added)} 条，新增 {len(added)} 条")
    return len(added)


def main() -> None:
    if not SQLBRAIN_DB.exists():
        print(f"来源数据库不存在: {SQLBRAIN_DB}")
        raise SystemExit(1)
    settings = get_settings()
    categories, knowledge, words = load_source(SQLBRAIN_DB)
    print(f"来源: {len(categories)} 个分类 / {len(knowledge)} 条知识 / {len(words)} 条违禁词")

    with SessionLocal() as db:
        beauty = db.query(Industry).filter(Industry.code == "beauty").first()
        industry_id = beauty.id if beauty else None
        if not industry_id:
            print("[错误] 未找到美业行业，请先启动后端完成初始化")
            raise SystemExit(1)

        imported = import_knowledge(db, settings.default_tenant_id, industry_id, categories, knowledge)
        added = import_prohibited_words(db, settings.default_tenant_id, industry_id, words)
        print("\n===== SQLBrain 迁移汇总 =====")
        print(f"知识分册导入: {imported}")
        print(f"违禁词新增: {added}")


if __name__ == "__main__":
    main()
