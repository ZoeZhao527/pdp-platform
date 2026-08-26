"""策略效果回流服务（自生长策略神经元 v1）

验收 KPI -> 策略卡效果权重；飞书 FeedbackEvent -> 策略卡效果信号。
score = 0.5 * kpi_achievement + 0.3 * win_rate + 0.2 * feedback_signal
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import FeedbackEvent, Instruction, Strategy, StrategyTask

WIN_THRESHOLD = 0.60
POSITIVE_ACTIONS = {"成单", "转化", "复购", "到店", "预约", "核销", "好评", "裂变", "充值"}
NEGATIVE_ACTIONS = {"投诉", "退款", "差评", "流失", "退卡"}


def _parse_number(text):
    if text is None:
        return None
    value = str(text).strip().replace(",", "").replace(",", "").replace("%", "")
    if not value:
        return None
    multiplier = 1.0
    if value.endswith("万"):
        multiplier = 10000.0
        value = value[:-1]
    try:
        return float(value) * multiplier
    except ValueError:
        return None


def _compute_kpi_achievement(kpi_results, instruction=None):
    """从 kpi_results dict 计算平均达成率（0~1）。"""
    if not kpi_results:
        return None
    params = (instruction.params_json if instruction else {}) or {}
    asset = (instruction.asset_json if instruction else {}) or {}
    goal_value_text = params.get("goal_value") or (asset.get("activity_plan") or {}).get("goal") or ""
    goal_num = _parse_number(goal_value_text)
    rates = []
    gmv_metrics = {"GMV", "销售额", "业绩", "营收", "储值额"}
    for metric, actual_text in kpi_results.items():
        actual_num = _parse_number(actual_text)
        if actual_num is None:
            continue
        if metric in gmv_metrics and goal_num and goal_num > 0:
            rates.append(min(actual_num / goal_num, 1.5))
        elif "%" in str(actual_text) or "率" in metric:
            rates.append(0.6)
        else:
            rates.append(0.5)
    if not rates:
        return None
    return sum(rates) / len(rates)


def _feedback_signal_score(db, strategy_id):
    """从 feedback_events 计算策略的反馈信号分（0~1）。"""
    events = db.query(FeedbackEvent).filter(FeedbackEvent.strategy_id == strategy_id).all()
    if not events:
        return 0.5
    pos = sum(1 for e in events if (e.action or "").strip() in POSITIVE_ACTIONS)
    neg = sum(1 for e in events if (e.action or "").strip() in NEGATIVE_ACTIONS)
    total = len(events)
    if total == 0:
        return 0.5
    raw = 0.5 + (pos - neg) / total * 0.5
    return max(0.0, min(1.0, raw))


def recalc_strategy_effect(db, strategy_id):
    """全量重算单个策略的效果分。"""
    strategy = db.get(Strategy, strategy_id)
    if strategy is None:
        return {}
    tasks = db.query(StrategyTask).filter(StrategyTask.strategy_id == strategy_id).all()
    instruction_ids = {t.instruction_id for t in tasks if t.instruction_id}
    runs = 0
    wins = 0
    last_kpi = {}
    for instr_id in instruction_ids:
        instr = db.get(Instruction, instr_id)
        if instr is None or instr.status != "已验收":
            continue
        runs += 1
        kpi_results = (instr.strategy_ids_json or {}).get("kpi_results")
        achievement = _compute_kpi_achievement(kpi_results, instr)
        if achievement is not None and achievement >= WIN_THRESHOLD:
            wins += 1
        if kpi_results:
            last_kpi = {
                "kpi_results": kpi_results,
                "achievement": round(achievement, 4) if achievement is not None else None,
                "instruction_id": instr_id,
                "instruction_title": instr.title,
                "accepted_at": instr.updated_at.isoformat() if instr.updated_at else None,
            }
    strategy.runs = runs
    strategy.wins = wins
    if last_kpi:
        strategy.last_kpi_json = last_kpi
    kpi_score = (last_kpi.get("achievement") or 0.0) if last_kpi else 0.0
    win_rate = (wins / runs) if runs > 0 else 0.0
    fb_signal = _feedback_signal_score(db, strategy_id)
    strategy.score = round(0.5 * kpi_score + 0.3 * win_rate + 0.2 * fb_signal, 4)
    strategy.feedback_count = db.query(FeedbackEvent).filter(
        FeedbackEvent.strategy_id == strategy_id
    ).count()
    db.commit()
    return _effect_out(strategy)


def update_on_acceptance(db, instruction_id, kpi_results):
    """指令验收后调用：找到关联策略，更新效果分。"""
    instruction = db.get(Instruction, instruction_id)
    if instruction is None:
        return []
    tasks = db.query(StrategyTask).filter(StrategyTask.instruction_id == instruction_id).all()
    strategy_ids = {t.strategy_id for t in tasks if t.strategy_id}
    sids_json = instruction.strategy_ids_json or {}
    if isinstance(sids_json, dict):
        sid = sids_json.get("strategy_id")
        if sid:
            strategy_ids.add(sid)
    if kpi_results:
        sids_json["kpi_results"] = kpi_results
        instruction.strategy_ids_json = sids_json
    results = []
    for sid in strategy_ids:
        results.append(recalc_strategy_effect(db, sid))
    db.commit()
    return results


def update_on_feedback(db, strategy_id, action, amount=0.0):
    """飞书反馈事件入库后调用：微调策略效果分。"""
    strategy = db.get(Strategy, strategy_id)
    if strategy is None:
        return {}
    strategy.feedback_count = (strategy.feedback_count or 0) + 1
    fb_signal = _feedback_signal_score(db, strategy_id)
    kpi_score = ((strategy.last_kpi_json or {}).get("achievement") or 0.0)
    win_rate = (strategy.wins / strategy.runs) if (strategy.runs or 0) > 0 else 0.0
    strategy.score = round(0.5 * kpi_score + 0.3 * win_rate + 0.2 * fb_signal, 4)
    db.commit()
    return _effect_out(strategy)


def get_effect_summary(db, strategy_id):
    """获取单个策略的效果摘要。"""
    strategy = db.get(Strategy, strategy_id)
    if strategy is None:
        return {}
    return _effect_out(strategy)


def get_effect_breakdown(db, strategy_id):
    """获取策略效果分的三个组成部分明细。"""
    strategy = db.get(Strategy, strategy_id)
    if strategy is None:
        return {}
    kpi_score = ((strategy.last_kpi_json or {}).get("achievement") or 0.0)
    win_rate = (strategy.wins / strategy.runs) if (strategy.runs or 0) > 0 else 0.0
    fb_signal = _feedback_signal_score(db, strategy_id)
    return {
        "id": strategy.id,
        "name": strategy.name,
        "score": round(strategy.score or 0.0, 4),
        "components": {
            "kpi_achievement": round(kpi_score, 4),
            "win_rate": round(win_rate, 4),
            "feedback_signal": round(fb_signal, 4),
        },
        "weights": {"kpi": 0.5, "win_rate": 0.3, "feedback": 0.2},
        "runs": strategy.runs or 0,
        "wins": strategy.wins or 0,
        "feedback_count": strategy.feedback_count or 0,
        "last_kpi": strategy.last_kpi_json,
    }


def get_effect_leaderboard(db, tenant_id, industry_id=None, limit=20):
    """效果排行榜：按 score 降序。"""
    q = db.query(Strategy).filter(Strategy.tenant_id == tenant_id)
    if industry_id:
        q = q.filter(Strategy.industry_id == industry_id)
    rows = q.order_by(Strategy.score.desc(), Strategy.created_at.desc()).limit(limit).all()
    return [_effect_out(s) for s in rows]


def _effect_out(s):
    return {
        "id": s.id,
        "name": s.name,
        "strategy_type": s.strategy_type,
        "runs": s.runs or 0,
        "wins": s.wins or 0,
        "score": round(s.score or 0.0, 4),
        "feedback_count": s.feedback_count or 0,
        "win_rate": round((s.wins or 0) / s.runs, 4) if (s.runs or 0) > 0 else 0.0,
        "last_kpi": s.last_kpi_json,
        "status": s.status,
    }
