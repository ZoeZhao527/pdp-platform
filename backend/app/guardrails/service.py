from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import GuardrailHit, GuardrailRule


DEFAULT_SAFE_CONTEXTS: dict[str, list[str]] = {
    # 单字/短违禁词在安全语境中不拦截，例如时间词、序数场景
    "最": ["最近", "最后", "最初", "最终"],
    "第一": [
        "第一时间",
        "第一站",
        "第一印象",
        "第一次",
        "第一天",
        "第一轮",
        "第一期",
        "第一季度",
        "第一页",
        "第一眼",
        "第一杯",
    ],
}


@dataclass
class GuardrailResult:
    passed: bool
    action: str | None = None
    matched_rule: str | None = None
    note: str | None = None


class GuardrailService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _all_occurrences_safe(text: str, keyword: str, safe_phrases: list[str]) -> bool:
        """关键字每个出现位置都必须被某个安全短语覆盖，否则视为真实违禁用法。"""
        start = 0
        while True:
            index = text.find(keyword, start)
            if index == -1:
                return True
            covered = False
            for phrase in safe_phrases:
                pos = text.find(phrase)
                while pos != -1:
                    if pos <= index < pos + len(phrase):
                        covered = True
                        break
                    pos = text.find(phrase, pos + 1)
                if covered:
                    break
            if not covered:
                return False
            start = index + len(keyword)

    def check(self, tenant_id: str, text: str, message_id: str | None = None) -> GuardrailResult:
        rules = (
            self.db.query(GuardrailRule)
            .filter(GuardrailRule.tenant_id == tenant_id, GuardrailRule.enabled.is_(True))
            .all()
        )
        for rule in rules:
            keywords = rule.pattern_json.get("keywords", [])
            safe_contexts = rule.pattern_json.get("safe_phrases") or DEFAULT_SAFE_CONTEXTS
            for keyword in keywords:
                if keyword not in text:
                    continue
                if keyword in safe_contexts and self._all_occurrences_safe(
                    text, keyword, safe_contexts[keyword]
                ):
                    continue
                self.db.add(
                    GuardrailHit(
                        tenant_id=tenant_id,
                        message_id=message_id,
                        rule_id=rule.id,
                        content=text[:500],
                        action=rule.action,
                        note=f"命中规则: {rule.name} / 关键词: {keyword}",
                    )
                )
                self.db.commit()
                return GuardrailResult(
                    passed=False,
                    action=rule.action,
                    matched_rule=rule.name,
                    note=f"命中关键词: {keyword}",
                )
        return GuardrailResult(passed=True)
