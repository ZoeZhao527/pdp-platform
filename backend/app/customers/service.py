from sqlalchemy.orm import Session

from app.models import Customer


PROFILE_KEYWORDS = {
    "皮肤敏感": ["敏感", "泛红", "过敏"],
    "抗衰需求": ["抗衰", "细纹", "紧致", "胶原"],
    "补水需求": ["干", "缺水", "保湿"],
    "营销偏好": ["活动", "优惠", "折扣", "福利"],
    "社群偏好": ["群", "活动方案", "运营计划"],
    "复购意向": ["回购", "再买", "续费", "复购"],
}


class CustomerService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_or_create(
        self,
        tenant_id: str,
        one_id: str,
        name: str | None = None,
        industry_id: str | None = None,
    ) -> Customer:
        customer = (
            self.db.query(Customer)
            .filter(Customer.tenant_id == tenant_id, Customer.one_id == one_id)
            .first()
        )
        if customer is None:
            customer = Customer(
                tenant_id=tenant_id,
                industry_id=industry_id,
                one_id=one_id,
                name=name,
                profile_json={"tags": []},
            )
            self.db.add(customer)
            self.db.flush()
        return customer

    def profile(self, tenant_id: str, customer_id: str) -> dict | None:
        customer = self.db.get(Customer, customer_id)
        if customer is None or customer.tenant_id != tenant_id:
            return None
        return {
            "id": customer.id,
            "one_id": customer.one_id,
            "name": customer.name,
            "profile": customer.profile_json or {},
            "created_at": customer.created_at.isoformat() if customer.created_at else None,
        }

    def update_profile_from_text(self, tenant_id: str, customer_id: str, text: str) -> dict:
        customer = self.db.get(Customer, customer_id)
        if customer is None:
            return {}
        profile = dict(customer.profile_json or {})
        tags = list(profile.get("tags", []))
        for tag, keywords in PROFILE_KEYWORDS.items():
            if any(kw in text for kw in keywords) and tag not in tags:
                tags.append(tag)
        profile["tags"] = tags
        profile["last_signal"] = text[:200]
        customer.profile_json = profile
        self.db.commit()
        return profile

    def list(self, tenant_id: str) -> list[dict]:
        rows = (
            self.db.query(Customer)
            .filter(Customer.tenant_id == tenant_id)
            .order_by(Customer.created_at.desc())
            .limit(100)
            .all()
        )
        return [
            {
                "id": row.id,
                "one_id": row.one_id,
                "name": row.name,
                "profile": row.profile_json or {},
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
