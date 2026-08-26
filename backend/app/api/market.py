from fastapi import APIRouter, Depends

from app.api.deps import Runtime, get_runtime
from app.models import HotVideo, Influencer, ReportBlock

router = APIRouter(prefix="/api/v1/market", tags=["market"])


@router.get("/overview")
def market_overview(runtime: Runtime = Depends(get_runtime)) -> dict:
    tenant = runtime.tenant_id
    industry = runtime.industry_id
    influencers = runtime.db.query(Influencer).filter(Influencer.tenant_id == tenant, Influencer.industry_id == industry).all()
    videos = runtime.db.query(HotVideo).filter(HotVideo.tenant_id == tenant, HotVideo.industry_id == industry).all()
    blocks = runtime.db.query(ReportBlock).filter(ReportBlock.tenant_id == tenant, ReportBlock.industry_id == industry).all()
    douyin = sum(1 for x in influencers if x.platform == "抖音")
    xhs = sum(1 for x in influencers if x.platform == "小红书")
    top = sum(1 for x in influencers if x.score >= 80)
    return {
        "influencers": len(influencers),
        "hot_videos": len(videos),
        "report_blocks": len(blocks),
        "platforms": {"抖音": douyin, "小红书": xhs},
        "top_influencers": top,
    }


@router.get("/influencers")
def list_influencers(runtime: Runtime = Depends(get_runtime)) -> list[dict]:
    rows = (
        runtime.db.query(Influencer)
        .filter(Influencer.tenant_id == runtime.tenant_id)
        .filter(Influencer.industry_id == runtime.industry_id)
        .order_by(Influencer.score.desc())
        .all()
    )
    return [
        {
            "id": row.id,
            "name": row.name,
            "platform": row.platform,
            "fans": row.fans,
            "avg_plays": row.avg_plays,
            "interaction_rate": row.interaction_rate,
            "verticality": row.verticality,
            "gmv": row.gmv,
            "conversion_rate": row.conversion_rate,
            "risk": row.risk,
            "score": row.score,
            "grade": row.grade,
            "level_label": row.level_label,
            "fit_projects": row.fit_projects,
            "budget": row.budget,
            "competitors": row.competitors,
            "suggestion": row.suggestion,
            "notes": row.notes,
        }
        for row in rows
    ]


@router.get("/hot-videos")
def list_hot_videos(runtime: Runtime = Depends(get_runtime)) -> list[dict]:
    rows = (
        runtime.db.query(HotVideo)
        .filter(HotVideo.tenant_id == runtime.tenant_id)
        .filter(HotVideo.industry_id == runtime.industry_id)
        .order_by(HotVideo.heat.desc())
        .all()
    )
    return [
        {
            "id": row.id,
            "title": row.title,
            "influencer_name": row.influencer_name,
            "category": row.category,
            "plays": row.plays,
            "likes": row.likes,
            "comments": row.comments,
            "shares": row.shares,
            "heat": row.heat,
            "tags": row.tags,
            "related_demand": row.related_demand,
        }
        for row in rows
    ]


@router.get("/report-blocks")
def list_report_blocks(runtime: Runtime = Depends(get_runtime)) -> list[dict]:
    rows = (
        runtime.db.query(ReportBlock)
        .filter(ReportBlock.tenant_id == runtime.tenant_id)
        .filter(ReportBlock.industry_id == runtime.industry_id)
        .order_by(ReportBlock.block.asc())
        .all()
    )
    return [
        {"block": row.block, "title": row.title, "data": row.data_json}
        for row in rows
    ]
