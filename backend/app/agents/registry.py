from dataclasses import dataclass


@dataclass(frozen=True)
class AgentSpec:
    key: str
    name: str
    description: str
    prompt_key: str


AGENT_CATALOG: list[AgentSpec] = [
    AgentSpec("ops_assistant", "消费者运营助手", "处理日常运营咨询与消费者运营动作", "ops_assistant"),
    AgentSpec("sop_planner", "社群 SOP 规划", "基于客户需求生成社群运营计划", "sop_planner"),
    AgentSpec("content_writer", "内容生成", "生成私域内容文案", "content_writer"),
    AgentSpec("sales_assistant", "导购助手", "给出个性化推荐与销售建议", "sales_assistant"),
    AgentSpec("insight_analyst", "数据洞察", "解读运营数据并给出建议", "insight_analyst"),
]


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentSpec] = {spec.key: spec for spec in AGENT_CATALOG}

    def get(self, key: str) -> AgentSpec:
        if key not in self._agents:
            raise KeyError(f"Agent 未注册: {key}")
        return self._agents[key]

    def all(self) -> list[AgentSpec]:
        return list(AGENT_CATALOG)


agent_registry = AgentRegistry()

