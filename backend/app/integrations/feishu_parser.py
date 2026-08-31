"""飞书群消息 LLM 解析器：自由文本 → 结构化运营数据。

链路：飞书群消息 → LLM 解析 → feedback_events + KPI 更新 + 策略关联。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from logging import getLogger
from typing import Any

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.llm_gateway.router import LLMRouter
from app.models import FeedbackEvent, KpiMetric, Strategy
from app.services.strategy_effect import update_on_feedback

logger = getLogger(__name__)


@dataclass
class ParsedMessage:
    """单条飞书消息解析结果。"""

    is_operational: bool = False
    action_type: str = ""        # 卖卡/发圈/群发/回访/活动执行/客户反馈/复购/拉新/其他
    quantity: float = 0.0
    quantity_unit: str = ""      # 单/人/条/次/元
    feedback_text: str = ""      # 效果反馈简述
    issues: list[str] = field(default_factory=list)  # 问题标签
    strategy_keyword: str = ""   # 可能关联的策略关键词
    summary: str = ""            # 一句话摘要


PARSE_PROMPT = """你是消费者运营中台的消息解析器。运营人员在飞书群里汇报工作进展或反馈情况。
请从以下消息中提取结构化信息，只返回 JSON，不要其他文字。

消息内容：{text}

返回格式：
{{
"is_operational": true/false,
"action_type": "卖卡|发圈|群发|回访|活动执行|客户反馈|复购|拉新|其他",
"quantity": 数字,
"quantity_unit": "单|人|条|次|元",
"feedback_text": "效果反馈简述",
"issues": ["问题1", "问题2"],
"strategy_keyword": "可能关联的策略关键词",
"summary": "一句话摘要"
}}

规则：
1. is_operational: 消息是否包含运营动作汇报或数据回传（非闲聊）。闲聊、表情、无意义内容设为 false。
2. action_type: 主要动作类型。如果消息包含多个动作，取最主要的一个。
3. quantity: 如果消息里有数字（如"卖了8单""发了3条朋友圈"），提取数字。没有填0。
4. quantity_unit: 数字对应的单位。
5. feedback_text: 客户或运营人员对效果的简短反馈。如"客户觉得效果好""复购率高"。没有填空字符串。
6. issues: 运营中遇到的问题，如"价格贵""库存不足""客户流失"。没有填空数组。
7. strategy_keyword: 如果消息提到了活动名、卡项名、策略名等，提取关键词。
8. summary: 用一句话概括这条消息的运营含义。"""


# 运营动作关键词字典：动作类型 → 触发词
ACTION_KEYWORDS: dict[str, list[str]] = {
    "卖卡": ["卖卡", "出卡", "办卡", "开卡", "售卡", "卡项", "套餐", "办了", "成交", "售出"],
    "发圈": ["发圈", "朋友圈", "发条", "种草", "晒单", "素材"],
    "群发": ["群发", "社群", "群内", "群消息", "群活动", "秒杀群", "群公告"],
    "回访": ["回访", "跟进", "邀约", "到店", "预约", "唤醒", "激活", "触达"],
    "活动执行": ["活动", "促销", "秒杀", "拼团", "裂变", "福利", "满减"],
    "客户反馈": ["反馈", "客户说", "客户觉得", "客户问", "投诉", "建议", "好评", "差评"],
    "复购": ["复购", "续费", "回购", "续卡", "二次到店"],
    "拉新": ["拉新", "新增", "新客", "引流", "获客", "转介绍"],
}

# 数量+单位信号：用于识别数据回传（如「卖了8单」「发3条」）
UNIT_PAT = re.compile(r"(\d+(?:\.\d+)?)\s*(单|人|条|次|元|万|个|位|组|笔)")


def _classify_action(text: str) -> tuple[str, float, str]:
    """关键词分类动作 + 正则提取数量与单位。"""
    action = "其他"
    for act, keywords in ACTION_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            action = act
            break
    m = UNIT_PAT.search(text)
    if m:
        return action, float(m.group(1)), m.group(2)
    return action, 0.0, ""


def _has_operational_signal(text: str) -> bool:
    """是否包含运营动作特征词或数据回传信号；闲聊/表情/无意义内容返回 False。"""
    for keywords in ACTION_KEYWORDS.values():
        if any(kw in text for kw in keywords):
            return True
    return bool(UNIT_PAT.search(text))


def _extract_strategy_kw(text: str) -> str:
    """从消息里抽取可能的策略/卡项关键词，取最长的一个触发词。"""
    best = ""
    for keywords in ACTION_KEYWORDS.values():
        for kw in keywords:
            if kw in text and len(kw) > len(best):
                best = kw
    return best


def parse_message(text: str, tenant_id: str = "tenant-default") -> ParsedMessage:
    """关键词解析单条飞书群消息（本地小模型不稳定，改用规则）。

    LLM 解析已停用：原方案依赖 qwen2.5:3b 输出 JSON，实际把闲聊也判为运营，
    导致 feedback_events 充斥「其他/0」垃圾数据。现改为关键词预过滤 + 规则分类。
    """
    text = (text or "").strip()
    if not text or not _has_operational_signal(text):
        return ParsedMessage()
    action, quantity, unit = _classify_action(text)
    return ParsedMessage(
        is_operational=True,
        action_type=action,
        quantity=quantity,
        quantity_unit=unit,
        summary=text[:60],
    )


def _extract_json(content: str, original_text: str) -> ParsedMessage:
    """从 LLM 返回中提取 JSON，容错处理。"""
    # 尝试直接解析
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        # 尝试提取花括号内的 JSON
        match = re.search(r"\{[\s\S]*\}", content)
        if match:
            try:
                data = json.loads(match.group(0))
            except (json.JSONDecodeError, TypeError):
                data = {}
        else:
            data = {}

    return ParsedMessage(
        is_operational=data.get("is_operational", False),
        action_type=data.get("action_type", ""),
        quantity=float(data.get("quantity", 0) or 0),
        quantity_unit=data.get("quantity_unit", ""),
        feedback_text=data.get("feedback_text", ""),
        issues=data.get("issues", []),
        strategy_keyword=data.get("strategy_keyword", ""),
        summary=data.get("summary", ""),
    )


def process_feishu_message(
    text: str,
    sender: str,
    tenant_id: str = "tenant-default",
    industry_id: str | None = None,
) -> str:
    """处理一条飞书群消息：解析 → 写库 → 更新KPI → 关联策略。返回回复文本。"""
    parsed = parse_message(text, tenant_id)

    if not parsed.is_operational:
        # 非运营消息，不回复（避免群内噪音）
        logger.info("飞书消息非运营内容，跳过: %s", text[:50])
        return ""

    with SessionLocal() as db:
        # 1. 写入 feedback_events
        event = FeedbackEvent(
            tenant_id=tenant_id,
            industry_id=industry_id,
            action=parsed.action_type,
            amount=parsed.quantity,
            note=f"[飞书] {text[:200]}",
            occurred_at=_now_str(),
        )
        db.add(event)

        # 2. 更新匹配的 KPI
        kpi_updated = _try_update_kpi(db, tenant_id, industry_id, parsed.action_type, parsed.quantity)

        # 3. 关联策略（按关键词匹配）
        strategy_obj = _try_match_strategy(db, tenant_id, industry_id, _extract_strategy_kw(text), parsed.action_type)
        strategy_name = ""
        if strategy_obj:
            event.strategy_id = strategy_obj.id
            strategy_name = strategy_obj.name

        db.commit()

        # 3.5 策略效果回流（飞书反馈 -> 神经元）
        if strategy_obj:
            update_on_feedback(db, strategy_obj.id, parsed.action_type, parsed.quantity)

    # 4. 生成回复
    parts = [f"已记录：{parsed.action_type}"]
    if parsed.quantity > 0:
        parts.append(f"{parsed.quantity}{parsed.quantity_unit}")
    if kpi_updated:
        parts.append(f"已更新「{kpi_updated}」KPI")
    if strategy_name:
        parts.append(f"关联策略「{strategy_name}」")

    return "，".join(parts) + "。"


def _try_update_kpi(db: Session, tenant_id: str, industry_id: str | None, action: str, amount: float) -> str:
    """找到指标名包含动作关键词的 KPI，累加 actual。"""
    if not action or amount == 0:
        return ""
    rows = (
        db.query(KpiMetric)
        .filter(KpiMetric.tenant_id == tenant_id)
        .filter(KpiMetric.industry_id == industry_id if industry_id else True)
        .order_by(KpiMetric.created_at.desc())
        .all()
    )
    for row in rows:
        if action in row.metric or row.metric in action:
            row.actual += amount
            return row.metric
    return ""


# 动作类型 → 策略参数匹配词映射
ACTION_STRATEGY_MAP: dict[str, list[str]] = {
    "卖卡": ["卡", "套餐", "储值", "办卡", "体验卡"],
    "发圈": ["朋友圈", "种草", "晒单", "素材", "发圈"],
    "群发": ["社群", "群发", "群活动", "秒杀群"],
    "回访": ["回访", "跟进", "邀约", "到店", "预约", "唤醒", "激活"],
    "活动执行": ["活动", "促销", "秒杀", "拼团", "裂变", "福利", "满减"],
    "客户反馈": ["反馈", "好评", "差评", "满意度"],
    "复购": ["复购", "续费", "回购", "续卡", "二次"],
    "拉新": ["拉新", "新客", "引流", "获客", "转介绍"],
}


def _try_match_strategy(db: Session, tenant_id: str, industry_id: str | None, keyword: str, action_type: str = "") -> object:
    """按关键词 + 动作类型匹配当前策略。改进版：多维度匹配。"""
    rows = (
        db.query(Strategy)
        .filter(Strategy.tenant_id == tenant_id)
        .filter(Strategy.industry_id == industry_id if industry_id else True)
        .order_by(Strategy.score.desc(), Strategy.created_at.desc())
        .limit(20)
        .all()
    )
    if not rows:
        return None

    # 1. 精确匹配策略名
    for row in rows:
        if keyword and keyword in (row.name or ""):
            return row

    # 2. 匹配策略类型
    for row in rows:
        if keyword and keyword in (row.strategy_type or ""):
            return row

    # 3. 按动作类型匹配策略参数
    match_words = ACTION_STRATEGY_MAP.get(action_type or "", [])
    if match_words:
        for row in rows:
            params = row.params_json or {}
            param_text = json.dumps(params, ensure_ascii=False)
            name_text = (row.name or "") + (row.strategy_type or "")
            combined = param_text + name_text
            for word in match_words:
                if word in combined:
                    return row

    # 4. 宽松匹配：策略名包含动作关键词的任意一个
    for row in rows:
        for words in ACTION_STRATEGY_MAP.values():
            if any(w in (row.name or "") for w in words):
                return row

    return None


def _now_str() -> str:
    import time
    return time.strftime("%Y-%m-%d %H:%M:%S")
