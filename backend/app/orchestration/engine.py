from typing import Any

from sqlalchemy.orm import Session

from app.agents.registry import agent_registry
from app.knowledge.service import KnowledgeService
from app.llm_gateway.router import LLMRouter
from app.memory.service import MemoryService
from app.models import AgentDef, AgentRun, Conversation, PromptTemplate


class OrchestrationEngine:
    def __init__(self, db: Session, llm_router: LLMRouter, memory: MemoryService) -> None:
        self.db = db
        self.llm_router = llm_router
        self.memory = memory

    def run(
        self,
        tenant_id: str,
        agent_key: str,
        conversation_id: str | None = None,
        input_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        spec = agent_registry.get(agent_key)
        template = (
            self.db.query(PromptTemplate)
            .filter(
                PromptTemplate.tenant_id == tenant_id,
                PromptTemplate.key == spec.prompt_key,
                PromptTemplate.enabled.is_(True),
            )
            .order_by(PromptTemplate.version.desc())
            .first()
        )
        user_text = (input_data or {}).get("text", "")
        context = self.memory.build_context(conversation_id) if conversation_id else []
        profile_summary = ""
        if conversation_id:
            conversation = self.db.get(Conversation, conversation_id)
            if conversation:
                profile_summary = self.memory.build_profile_summary(conversation.customer_id)
        base_prompt = template.content if template else "你是一个私域运营助手，请简洁、专业地回复。"
        if profile_summary:
            base_prompt = f"{profile_summary}\n\n{base_prompt}"
        if user_text:
            knowledge_hits = KnowledgeService(self.db).search(tenant_id, user_text, top_k=3)
            if knowledge_hits:
                knowledge_block = "\n".join(f"- {hit['content']}" for hit in knowledge_hits)
                base_prompt = f"{base_prompt}\n\n知识库参考：\n{knowledge_block}"
        prompt = base_prompt + (
            f"\n\n用户输入：{user_text}" if user_text else ""
        )
        messages = context + [{"role": "user", "content": prompt}]
        result = self.llm_router.complete(
            tenant_id,
            messages,
            conversation_id=conversation_id,
            complexity="lite",
        )
        agent_def = (
            self.db.query(AgentDef)
            .filter(AgentDef.tenant_id == tenant_id, AgentDef.key == agent_key)
            .first()
        )
        self.db.add(
            AgentRun(
                tenant_id=tenant_id,
                agent_def_id=agent_def.id if agent_def else None,
                conversation_id=conversation_id,
                input_json={"text": user_text},
                output_json={"reply": result.content, "model": result.model, "provider": result.provider},
                status="done",
            )
        )
        self.db.commit()
        return {
            "agent": agent_key,
            "reply": result.content,
            "model": result.model,
            "provider": result.provider,
        }
