"""平台级资产分层解析器

is_platform=True  -> 平台级默认资产，所有品牌继承
is_platform=False -> 品牌级资产，platform_ref 指向被覆盖的平台资产 ID

resolve_assets() 返回合并后的资产列表：
  1. 取平台级资产
  2. 取品牌级资产
  3. 品牌级中 platform_ref 非空的 -> 覆盖对应平台资产
  4. 品牌级中 platform_ref 为空的 -> 品牌私有追加
"""
from __future__ import annotations

from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GuardrailRule, KnowledgeDoc, Strategy

T = TypeVar("T", Strategy, GuardrailRule, KnowledgeDoc)

PLATFORM_TENANT_ID = "platform"


def resolve_assets(
    db: Session,
    model: type[T],
    tenant_id: str,
    industry_id: str | None = None,
) -> list[T]:
    """合并平台级 + 品牌级资产，品牌覆盖平台。"""
    # 1. 平台级资产
    platform_q = select(model).where(model.is_platform == True)  # noqa: E712
    if hasattr(model, "industry_id") and industry_id:
        platform_q = platform_q.where(
            (model.industry_id == industry_id) | (model.industry_id.is_(None))
        )
    platform_rows = db.execute(platform_q).scalars().all()

    # 2. 品牌级资产
    brand_q = select(model).where(
        model.is_platform == False,  # noqa: E712
        model.tenant_id == tenant_id,
    )
    if hasattr(model, "industry_id") and industry_id:
        brand_q = brand_q.where(
            (model.industry_id == industry_id) | (model.industry_id.is_(None))
        )
    brand_rows = db.execute(brand_q).scalars().all()

    # 3. 合并：品牌覆盖平台
    override_refs = {r.platform_ref for r in brand_rows if r.platform_ref}
    merged: list[T] = []

    # 平台级中未被覆盖的保留
    for row in platform_rows:
        if row.id not in override_refs:
            merged.append(row)

    # 品牌级全部加入（覆盖的 + 私有的）
    merged.extend(brand_rows)

    # 按 score / created_at 排序（如果有 score 字段）
    if hasattr(model, "score"):
        merged.sort(key=lambda r: (getattr(r, "score", 0) or 0, r.created_at.isoformat() if r.created_at else ""), reverse=True)
    else:
        merged.sort(key=lambda r: r.created_at.isoformat() if r.created_at else "", reverse=True)

    return merged


def promote_to_platform(db: Session, model: type[T], asset_id: str) -> T | None:
    """把品牌级资产提升为平台级。"""
    asset = db.get(model, asset_id)
    if asset is None or asset.is_platform:
        return asset
    asset.is_platform = True
    asset.platform_ref = None
    asset.tenant_id = PLATFORM_TENANT_ID
    db.commit()
    return asset


def create_brand_override(
    db: Session,
    model: type[T],
    platform_asset_id: str,
    tenant_id: str,
    overrides: dict,
) -> T | None:
    """基于平台资产创建品牌级覆盖副本。"""
    platform_asset = db.get(model, platform_asset_id)
    if platform_asset is None or not platform_asset.is_platform:
        return None

    # 创建副本
    data = {
        "tenant_id": tenant_id,
        "is_platform": False,
        "platform_ref": platform_asset_id,
    }
    if hasattr(platform_asset, "industry_id"):
        data["industry_id"] = platform_asset.industry_id

    # 复制基本字段
    for col in model.__table__.columns:
        if col.name in ("id", "tenant_id", "is_platform", "platform_ref", "industry_id", "created_at", "updated_at"):
            continue
        val = getattr(platform_asset, col.name, None)
        if val is not None:
            data[col.name] = val

    # 应用覆盖
    data.update(overrides)

    new_asset = model(**data)
    db.add(new_asset)
    db.commit()
    db.refresh(new_asset)
    return new_asset
