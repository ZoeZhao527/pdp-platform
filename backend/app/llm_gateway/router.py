from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.llm_gateway.client import LLMProviderError, LLMResult, OpenAICompatibleClient
from app.models import LLMBudget, LLMCallLog, LLMModelConfig


class LLMRouter:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._clients: dict[str, OpenAICompatibleClient] = {}

    def _client(self, cfg: LLMModelConfig) -> OpenAICompatibleClient:
        key = f"{cfg.provider}:{cfg.model}:{cfg.base_url}"
        if key not in self._clients:
            self._clients[key] = OpenAICompatibleClient(
                base_url=cfg.base_url,
                api_key=cfg.api_key,
                model=cfg.model,
                provider=cfg.provider,
            )
        return self._clients[key]

    def _log(
        self,
        tenant_id: str,
        result: LLMResult | None,
        conversation_id: str | None,
        status: str = "ok",
        error: str | None = None,
    ) -> None:
        self.db.add(
            LLMCallLog(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                model=result.model if result else "unknown",
                provider=result.provider if result else "unknown",
                prompt_tokens=result.prompt_tokens if result else 0,
                completion_tokens=result.completion_tokens if result else 0,
                latency_ms=result.latency_ms if result else 0,
                cost=result.cost if result else 0.0,
                status=status,
                error=error,
            )
        )

    def _budget(self, tenant_id: str, period_type: str, period_key: str) -> LLMBudget:
        budget = (
            self.db.query(LLMBudget)
            .filter(
                LLMBudget.tenant_id == tenant_id,
                LLMBudget.period_type == period_type,
                LLMBudget.period_key == period_key,
            )
            .first()
        )
        if budget is None:
            budget = LLMBudget(
                tenant_id=tenant_id,
                period_type=period_type,
                period_key=period_key,
                token_limit=1_000_000,
            )
            self.db.add(budget)
            self.db.flush()
        return budget

    def _budget_exceeded(self, tenant_id: str) -> bool:
        today = date.today()
        for period_type, key in (("daily", today.isoformat()), ("monthly", today.strftime("%Y-%m"))):
            budget = self._budget(tenant_id, period_type, key)
            if budget.token_limit > 0 and budget.tokens_used >= budget.token_limit:
                return True
            if budget.cost_limit > 0 and budget.cost_used >= budget.cost_limit:
                return True
        return False

    def _record_usage(self, tenant_id: str, result: LLMResult) -> None:
        today = date.today()
        for period_type, key in (("daily", today.isoformat()), ("monthly", today.strftime("%Y-%m"))):
            budget = self._budget(tenant_id, period_type, key)
            budget.tokens_used += result.prompt_tokens + result.completion_tokens
            budget.cost_used += result.cost

    def complete(
        self,
        tenant_id: str,
        messages: list[dict[str, str]],
        conversation_id: str | None = None,
        complexity: str = "complex",
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> LLMResult:
        if self._budget_exceeded(tenant_id):
            result = LLMResult(
                content="[预算保护] 当前 Token 预算已达上限，请运营人员在管理后台调整预算后重试。",
                model="budget-guard",
                provider="budget",
            )
            self._log(tenant_id, result, conversation_id, status="budget_exceeded")
            self.db.commit()
            return result

        configs = (
            self.db.query(LLMModelConfig)
            .filter(
                LLMModelConfig.tenant_id == tenant_id,
                LLMModelConfig.enabled.is_(True),
                LLMModelConfig.complexity == complexity,
            )
            .order_by(LLMModelConfig.priority.asc())
            .all()
        )
        if not configs:
            fallback = OpenAICompatibleClient(
                base_url="",
                api_key="",
                model="local-echo",
                provider="local-echo",
            )
            result = fallback.complete(messages)
            self._log(tenant_id, result, conversation_id)
            self.db.commit()
            return result

        errors: list[str] = []
        for cfg in configs:
            try:
                kw: dict[str, Any] = {}
                if max_tokens:
                    kw["max_tokens"] = max_tokens
                if response_format:
                    kw["response_format"] = response_format
                result = self._client(cfg).complete(messages, **kw)
                result.cost = round(cfg.cost_per_million * (result.prompt_tokens + result.completion_tokens) / 1_000_000, 6)
                self._record_usage(tenant_id, result)
                self._log(tenant_id, result, conversation_id)
                self.db.commit()
                return result
            except LLMProviderError as exc:
                errors.append(f"{cfg.provider}:{cfg.model} -> {exc}")
                self._log(tenant_id, None, conversation_id, status="error", error=str(exc))
                self.db.commit()

        raise LLMProviderError("; ".join(errors))
