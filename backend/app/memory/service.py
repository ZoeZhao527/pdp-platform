from sqlalchemy.orm import Session

from app.models import Customer, Message


class MemoryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def build_context(self, conversation_id: str, limit: int = 10) -> list[dict[str, str]]:
        rows = (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {"role": "user" if row.direction == "in" else "assistant", "content": row.content}
            for row in reversed(rows)
        ]

    def build_profile_summary(self, customer_id: str | None) -> str:
        if not customer_id:
            return ""
        customer = self.db.get(Customer, customer_id)
        if customer is None:
            return ""
        profile = customer.profile_json or {}
        tags = profile.get("tags", [])
        label = customer.name or customer.one_id
        return f"客户画像：{label}；标签：{'、'.join(tags) if tags else '暂无'}"
