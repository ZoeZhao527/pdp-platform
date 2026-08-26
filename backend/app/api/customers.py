from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import Runtime, get_runtime
from app.customers.service import CustomerService
from app.models import Customer

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


class ProfileUpdate(BaseModel):
    tags: list[str] | None = None
    note: str | None = None


@router.get("")
def list_customers(runtime: Runtime = Depends(get_runtime)) -> list[dict]:
    rows = (
        runtime.db.query(Customer)
        .filter(
            Customer.tenant_id == runtime.tenant_id,
            Customer.industry_id == runtime.industry_id,
        )
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


@router.get("/{customer_id}/profile")
def get_profile(customer_id: str, runtime: Runtime = Depends(get_runtime)) -> dict:
    profile = CustomerService(runtime.db).profile(runtime.tenant_id, customer_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="客户不存在")
    return profile


@router.put("/{customer_id}/profile")
def update_profile(
    customer_id: str,
    payload: ProfileUpdate,
    runtime: Runtime = Depends(get_runtime),
) -> dict:
    service = CustomerService(runtime.db)
    customer = runtime.db.get(Customer, customer_id)
    if customer is None or customer.tenant_id != runtime.tenant_id:
        raise HTTPException(status_code=404, detail="客户不存在")
    profile = dict(customer.profile_json or {})
    if payload.tags is not None:
        profile["tags"] = payload.tags
    if payload.note is not None:
        profile["note"] = payload.note
    customer.profile_json = profile
    runtime.db.commit()
    return {"id": customer.id, "profile": profile}
