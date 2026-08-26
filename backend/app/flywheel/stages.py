from sqlalchemy.orm import Session

from app.flywheel.labels import label_signal
from app.models import Capability, DemandGraph, DemandProfile, DemandSignal, Strategy


def profile_tags(profile: DemandProfile) -> list[str]:
    data = profile.tags_json or {}
    if isinstance(data, list):
        return list(data)
    return list(data.get("tags", []))


def structure_signal(db: Session, signal: DemandSignal) -> DemandProfile:
    category, tags, confidence = label_signal(signal.raw_content, getattr(signal, "segment", None))
    profile = DemandProfile(
        tenant_id=signal.tenant_id,
        industry_id=signal.industry_id,
        customer_id=signal.customer_id,
        signal_id=signal.id,
        tags_json={"tags": tags},
        scenario=category,
        intensity=min(5, 1 + len(tags)),
    )
    signal.status = "structured"
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def upsert_demand_graph(db: Session, profile: DemandProfile) -> DemandGraph:
    graph = (
        db.query(DemandGraph)
        .filter(
            DemandGraph.tenant_id == profile.tenant_id,
            DemandGraph.customer_id == profile.customer_id,
            DemandGraph.demand_key == profile.scenario,
        )
        .first()
    )
    tags = profile_tags(profile)
    if graph is None:
        graph = DemandGraph(
            tenant_id=profile.tenant_id,
            industry_id=profile.industry_id,
            customer_id=profile.customer_id,
            demand_key=profile.scenario or "待补充",
            scenario=profile.scenario,
            related_json={"tags": tags, "intensity": profile.intensity},
            source_profile_id=profile.id,
        )
        db.add(graph)
    else:
        related = dict(graph.related_json or {})
        existing = set(related.get("tags", []))
        existing.update(tags)
        related["tags"] = sorted(existing)
        related["intensity"] = max(related.get("intensity", 1), profile.intensity)
        graph.related_json = related
    db.commit()
    db.refresh(graph)
    return graph


def match_capabilities(db: Session, tenant_id: str, profile: DemandProfile) -> list[Capability]:
    capabilities = (
        db.query(Capability)
        .filter(Capability.tenant_id == tenant_id)
        .order_by(Capability.created_at.desc())
        .limit(20)
        .all()
    )
    scored: list[tuple[int, Capability]] = []
    scenario = profile.scenario or ""
    tags = profile_tags(profile)
    for cap in capabilities:
        rules = cap.match_rules_json or {}
        keywords = rules.get("keywords", [])
        hits = sum(1 for kw in keywords if kw in scenario or kw in tags)
        tag_hits = sum(1 for tag in tags if tag in f"{cap.product}{cap.capability}")
        score = hits * 2 + tag_hits
        if score > 0:
            scored.append((score, cap))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [cap for _, cap in scored]


def score_match_profile(profile: DemandProfile, capability: Capability) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.0
    tags = profile_tags(profile)
    evidence = profile.evidence or ""

    efficacy = capability.efficacy_json or []
    hits = sum(1 for item in efficacy if item in evidence or any(item in tag for tag in tags))
    score += min(42, hits * 7)
    if hits:
        reasons.append(f"功效命中 {hits} 项：{','.join(str(x) for x in efficacy[:2])}")

    demand_seg = ""
    for tag in tags:
        if tag.startswith("人群:"):
            demand_seg = tag.split(":", 1)[1]
    segments = capability.segments_json or []
    if demand_seg and demand_seg in segments:
        score += 20
        reasons.append(f"人群匹配：{demand_seg}")
    elif demand_seg:
        score += 8
        reasons.append(f"人群部分匹配：{demand_seg}")

    seasons = capability.seasons_json or []
    if any(season in evidence or season in ",".join(tags) for season in seasons):
        score += 15
        reasons.append(f"场景契合：{','.join(str(x) for x in seasons[:2])}")
    else:
        score += 6

    price = capability.price or 0
    price_sensitive = "价格敏感" in tags
    if price_sensitive and price <= 600:
        score += 12
        reasons.append("价格带适配价格敏感人群")
    elif not price_sensitive and price >= 600:
        score += 12
        reasons.append("价格带匹配更高预算人群")
    else:
        score += 6

    if capability.is_focus:
        score += 6
        reasons.append("本月主推")
    if profile.verified:
        score += 4
        reasons.append("已验证需求")
    return min(100.0, score), reasons


def pick_strategy(db: Session, tenant_id: str, profile: DemandProfile) -> Strategy:
    strategies = (
        db.query(Strategy)
        .filter(Strategy.tenant_id == tenant_id, Strategy.enabled.is_(True))
        .all()
    )
    if not strategies:
        raise ValueError("租户下未配置任何策略")
    scenario = profile.scenario or ""
    for strategy in strategies:
        params = strategy.params_json or {}
        if any(kw in scenario for kw in params.get("keywords", [])):
            return strategy
    return strategies[0]
