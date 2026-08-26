from typing import Any

from sqlalchemy.orm import Session

from app.flywheel.stages import match_capabilities, pick_strategy, structure_signal, upsert_demand_graph
from app.llm_gateway.router import LLMRouter
from app.models import DemandSignal, FlywheelMetric, StrategyExecution
from app.orchestration.engine import OrchestrationEngine


class FlywheelService:
    def __init__(
        self,
        db: Session,
        llm_router: LLMRouter,
        engine: OrchestrationEngine | None = None,
    ) -> None:
        self.db = db
        self.llm_router = llm_router
        self.engine = engine

    def trigger(
        self,
        tenant_id: str,
        signal_text: str,
        customer_id: str | None = None,
        conversation_id: str | None = None,
        source_type: str = "message",
        industry_id: str | None = None,
    ) -> dict[str, Any]:
        signal = DemandSignal(
            tenant_id=tenant_id,
            industry_id=industry_id,
            customer_id=customer_id,
            conversation_id=conversation_id,
            source_type=source_type,
            raw_content=signal_text,
        )
        self.db.add(signal)
        self.db.commit()
        self.db.refresh(signal)
        return self.process_signal(tenant_id, signal, conversation_id=conversation_id)

    def process_signal(
        self,
        tenant_id: str,
        signal: DemandSignal,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        profile = structure_signal(self.db, signal)
        upsert_demand_graph(self.db, profile)
        matched = match_capabilities(self.db, tenant_id, profile)
        strategy = pick_strategy(self.db, tenant_id, profile)

        execution = StrategyExecution(
            tenant_id=tenant_id,
            industry_id=signal.industry_id,
            strategy_id=strategy.id,
            demand_profile_id=profile.id,
            conversation_id=conversation_id or signal.conversation_id,
            status="running",
        )
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)

        capability_text = "；".join(f"{c.product}: {c.capability}" for c in matched) or "暂无匹配能力"
        if signal.source_type == "topic":
            reply = (
                f"热点信号“{signal.raw_content}”已进入需求飞轮，"
                f"匹配能力：{capability_text}。建议按现有策略执行并回收效果。"
            )
            model = "rule-based"
        elif self.engine is not None:
            agent_result = self.engine.run(
                tenant_id,
                strategy.agent_key,
                conversation_id=conversation_id or signal.conversation_id,
                input_data={"text": signal.raw_content, "capabilities": capability_text},
            )
            reply = agent_result["reply"]
            model = agent_result.get("model", "local")
        else:
            prompt = (
                f"你是私域运营策略引擎。客户需求信号：{signal.raw_content}\n"
                f"需求画像：{profile.tags_json}\n"
                f"可匹配能力：{capability_text}\n"
                "请输出一条可执行的私域运营策略，包含目标、动作、话术要点和效果指标。"
            )
            result = self.llm_router.complete(
                tenant_id,
                [{"role": "user", "content": prompt}],
                conversation_id=conversation_id or signal.conversation_id,
                complexity="lite",
            )
            reply = result.content
            model = result.model

        execution.status = "done"
        execution.result_json = {
            "reply": reply,
            "matched_capabilities": [c.capability for c in matched],
            "model": model,
        }
        execution.metrics_json = {
            "closed_loop_days": 1.0,
            "hit_count": len(matched),
            "adopted_count": 0,
            "roi": 0.0,
        }
        metric = FlywheelMetric(
            tenant_id=tenant_id,
            industry_id=signal.industry_id,
            cycle_id=execution.id,
            closed_loop_days=1.0,
            hit_count=len(matched),
            adopted_count=0,
            roi=0.0,
            snapshot_json={
                "signal": signal.raw_content,
                "scenario": profile.scenario,
                "tags": profile.tags_json,
                "strategy": strategy.name,
                "reply": reply,
            },
        )
        self.db.add(metric)
        signal.status = "processed"
        self.db.commit()

        return {
            "cycle_id": execution.id,
            "signal_id": signal.id,
            "profile_id": profile.id,
            "scenario": profile.scenario,
            "tags": profile.tags_json,
            "matched_capabilities": [c.capability for c in matched],
            "strategy": strategy.name,
            "reply": reply,
            "metrics": execution.metrics_json,
        }

    def adopt(self, tenant_id: str, cycle_id: str) -> dict:
        execution = self.db.get(StrategyExecution, cycle_id)
        if execution is None or execution.tenant_id != tenant_id:
            raise ValueError("闭环不存在")
        metrics = dict(execution.metrics_json or {})
        metrics["adopted_count"] = 1
        execution.metrics_json = metrics
        metric = (
            self.db.query(FlywheelMetric)
            .filter(
                FlywheelMetric.tenant_id == tenant_id,
                FlywheelMetric.cycle_id == cycle_id,
            )
            .first()
        )
        if metric:
            metric.adopted_count = 1
        self.db.commit()
        return {"cycle_id": cycle_id, "adopted": True}
