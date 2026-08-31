from sqlalchemy.orm import Session

from app.auth import hash_password
from app.config import get_settings
from app.models import (
    AgentDef,
    Capability,
    Channel,
    GuardrailRule,
    Industry,
    IndustryTemplate,
    KnowledgeDoc,
    LLMModelConfig,
    PromptTemplate,
    Strategy,
    Tenant,
    ToolRegistry,
    User,
)


SENSITIVE_WORDS = ["封号", "代开发票", "私人转账", "加微信私下交易", "退款到私人账户"]
CONTENT_SAFETY_WORDS = ["赌博", "色情", "违法", "诈骗", "洗钱", "毒品"]

SAMPLE_KNOWLEDGE = (
    "敏感肌护理要点：1. 避免使用含酒精、香精和高浓度酸类成分的产品；"
    "2. 洁面选择温和氨基酸配方，水温控制在 30 度左右；"
    "3. 保湿优先于美白，先用修护类产品建立皮肤屏障；"
    "4. 出现泛红时暂停功效型产品，以舒缓修护为主；"
    "5. 建议回访周期：首次体验后第 3 天回访，第 7 天评估是否继续护理。"
    "抗衰项目介绍：胶原蛋白项目适合 28 岁以上初老人群，常见诉求是细纹、松弛、轮廓模糊；"
    "体验邀约建议话术：先表达共情，再给 1 个轻量体验方案，不强推套餐。"
)

INDUSTRIES = [
    {"code": "beauty", "name": "美业", "description": "美容、美发、美甲、医美等"},
    {"code": "catering", "name": "餐饮", "description": "正餐、快餐、茶饮、烘焙等"},
    {"code": "retail", "name": "零售", "description": "百货、服装、快消等"},
    {"code": "education", "name": "教育", "description": "素质教育、职业教育、培训等"},
    {"code": "pet", "name": "宠物", "description": "宠物用品、宠物服务等"},
    {"code": "health", "name": "大健康", "description": "健康管理、滋补、运动等"},
]

DEFAULT_TEMPLATES = {
    "activity": {
        "types": ["会员日", "裂变", "直播", "节庆", "新品", "周年庆", "复购召回", "拉新"],
    },
    "catalog": {
        "structure": ["引流款", "主推款", "利润款", "组合卡"],
        "fields": ["名称", "价格", "成本", "毛利", "库存"],
    },
    "sales": {
        "sections": ["开场话术", "需求挖掘", "异议处理", "成交逼单", "跟进节奏"],
        "layers": ["潜客", "新客", "复购", "流失"],
        "objections": [
            {
                "issue": "价格太贵",
                "response": "理解您在意价格，这个方案的价值在于长期效果和售后保障，我们可以先安排一次低门槛体验。",
                "tone": "共情 + 价值",
                "scenario": "报价后",
            },
            {
                "issue": "我再考虑一下",
                "response": "没问题，您先考虑。我把资料和几个客户案例发给您，有需要随时找我。",
                "tone": "轻松不施压",
                "scenario": "犹豫期",
            },
            {
                "issue": "之前体验不好",
                "response": "很抱歉上次没有给您好的体验，这次我们换了方案和服务流程，您可以先体验一次看看变化。",
                "tone": "诚恳道歉",
                "scenario": "老客回访",
            },
        ],
        "layer_plays": [
            {
                "layer": "潜客",
                "goal": "建立信任",
                "action": "1v1 破冰 + 内容种草",
                "script": "您好，我是您的专属顾问，先发您一份适合您的内容，有问题随时问我。",
                "follow_up": "T+0 欢迎语，T+3 内容触达",
            },
            {
                "layer": "新客",
                "goal": "首单转化",
                "action": "体验邀约 + 限时权益",
                "script": "这周我们有新客体验权益，帮您预留一个名额？",
                "follow_up": "体验后 3 天回访",
            },
            {
                "layer": "复购",
                "goal": "提升频次",
                "action": "会员权益 + 周期推荐",
                "script": "您上次体验的效果很好，这周会员日有专属权益，适合继续巩固。",
                "follow_up": "复购节点前 7 天提醒",
            },
            {
                "layer": "流失",
                "goal": "召回激活",
                "action": "福利召回 + 原因安抚",
                "script": "好久没见到您了，最近有到店福利，也想知道您之前对哪些地方不满意。",
                "follow_up": "召回后 7 天跟进",
            },
        ],
    },
    "content": {
        "channels": ["朋友圈", "社群", "1v1", "公众号", "短视频"],
        "fields": ["渠道", "素材", "发布时间"],
        "materials": [
            {
                "type": "破冰内容",
                "title": "新客欢迎语",
                "copy": "您好，我是您的专属顾问，先发您一份适合您的内容，有问题随时找我。",
                "channel": "1v1",
                "purpose": "加微首触",
            },
            {
                "type": "种草内容",
                "title": "场景化种草",
                "copy": "最近很多客户反馈这个方案很适合她们的生活节奏，感兴趣可以了解一下。",
                "channel": "朋友圈",
                "purpose": "日常种草",
            },
            {
                "type": "活动内容",
                "title": "活动预告",
                "copy": "本周会员日福利已上线，名额有限，需要的宝子私信我。",
                "channel": "社群",
                "purpose": "活动预热",
            },
            {
                "type": "转化内容",
                "title": "限时权益",
                "copy": "您关注的方案今天有专属权益，我先帮您锁一个名额？",
                "channel": "1v1",
                "purpose": "成交逼单",
            },
        ],
        "schedules": [
            {
                "channel": "朋友圈",
                "cadence": "每日 1 条",
                "time_slots": "12:00 / 20:00",
                "content_type": "种草 + 晒单",
                "goal": "日常触达",
            },
            {
                "channel": "社群",
                "cadence": "每周 3 次",
                "time_slots": "周一/三/五 19:30",
                "content_type": "话题 + 活动",
                "goal": "活跃与转化",
            },
            {
                "channel": "1v1",
                "cadence": "按节点",
                "time_slots": "T+0/T+3/T+7",
                "content_type": "欢迎语/跟进/邀约",
                "goal": "转化与复购",
            },
            {
                "channel": "公众号",
                "cadence": "每周 1 篇",
                "time_slots": "周日 10:00",
                "content_type": "干货 + 活动",
                "goal": "品牌沉淀",
            },
        ],
    },
    "kpi": {"metrics": ["触达率", "转化率", "GMV", "ROI", "复购率"]},
}


PROMPT_TEMPLATES = {
    "ops_assistant": "你是消费者运营助手，请用简洁、专业、温暖的中文回复客户。不要承诺无法兑现的效果，不涉及违规承诺。",
    "sop_planner": "你是社群运营专家，请基于客户需求输出 3 步社群 SOP，包含动作、话术和节奏。",
    "content_writer": "你是私域内容编辑，请输出一条适合私域发布的文案，语气自然，避免夸大。",
    "sales_assistant": "你是导购助手，请基于客户画像给出个性化推荐和跟进建议。",
    "insight_analyst": "你是数据洞察分析师，请解读运营数据并给出可执行建议。",
}


def seed_default_data(db: Session) -> None:
    settings = get_settings()
    tenant = db.query(Tenant).filter(Tenant.code == "default").first()
    if tenant is None:
        tenant = Tenant(id=settings.default_tenant_id, name="默认租户", code="default")
        db.add(tenant)
        db.flush()

    industry_map: dict[str, Industry] = {}
    for item in INDUSTRIES:
        industry = db.query(Industry).filter(Industry.code == item["code"]).first()
        if industry is None:
            industry = Industry(code=item["code"], name=item["name"], description=item["description"])
            db.add(industry)
            db.flush()
        industry_map[item["code"]] = industry
        for kind, data in DEFAULT_TEMPLATES.items():
            exists = (
                db.query(IndustryTemplate)
                .filter(
                    IndustryTemplate.industry_id == industry.id,
                    IndustryTemplate.kind == kind,
                )
                .first()
            )
            if exists is None:
                db.add(
                    IndustryTemplate(
                        industry_id=industry.id,
                        kind=kind,
                        name=f"{industry.name} {kind} 模板",
                        data_json=data,
                        enabled=True,
                    )
                )
    if tenant.industry_id is None and "beauty" in industry_map:
        tenant.industry_id = industry_map["beauty"].id

    if not db.query(User).filter(User.username == settings.admin_username).first():
        db.add(
            User(
                tenant_id=tenant.id,
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                display_name="系统管理员",
                role="admin",
                enabled=True,
            )
        )

    if not db.query(Channel).filter(Channel.tenant_id == tenant.id).first():
        db.add_all(
            [
                Channel(
                    tenant_id=tenant.id,
                    name="Mock 渠道",
                    channel_type="mock",
                    config_json={"route": "ops", "name": "本地演示渠道"},
                    enabled=True,
                ),
                Channel(
                    tenant_id=tenant.id,
                    name="企业微信",
                    channel_type="wecom",
                    config_json={
                        "route": "ops",
                        "corp_id": "",
                        "secret": "",
                        "cs_platform": {"platform": "echo", "webhook_url": "", "token": ""},
                    },
                    enabled=False,
                ),
            ]
        )

    if not db.query(GuardrailRule).filter(GuardrailRule.tenant_id == tenant.id).first():
        db.add_all(
            [
                GuardrailRule(
                    tenant_id=tenant.id,
                    rule_type="sensitive_word",
                    name="基础敏感词拦截",
                    pattern_json={"keywords": SENSITIVE_WORDS},
                    action="block",
                    enabled=True,
                ),
                GuardrailRule(
                    tenant_id=tenant.id,
                    rule_type="handoff",
                    name="投诉转人工",
                    pattern_json={"keywords": ["投诉", "举报", "差评"]},
                    action="handoff",
                    enabled=True,
                ),
                GuardrailRule(
                    tenant_id=tenant.id,
                    rule_type="content_safety",
                    name="违规内容拦截",
                    pattern_json={"keywords": CONTENT_SAFETY_WORDS},
                    action="block",
                    enabled=True,
                ),
            ]
        )

    if not db.query(LLMModelConfig).filter(LLMModelConfig.tenant_id == tenant.id).first():
        configs = [
                LLMModelConfig(
                    tenant_id=tenant.id,
                    name="混元 Pro",
                    provider="hunyuan",
                    model=settings.llm_default_model,
                    base_url=settings.llm_default_base_url,
                    api_key=settings.llm_default_api_key,
                    priority=1,
                    complexity="complex",
                    cost_per_million=10.0,
                    enabled=True,
                ),
                LLMModelConfig(
                    tenant_id=tenant.id,
                    name="混元 Lite",
                    provider="hunyuan",
                    model=settings.llm_lite_model,
                    base_url=settings.llm_lite_base_url,
                    api_key=settings.llm_lite_api_key,
                    priority=1,
                    complexity="lite",
                    cost_per_million=3.0,
                    enabled=True,
                ),
                LLMModelConfig(
                    tenant_id=tenant.id,
                    name="DeepSeek 兜底",
                    provider="deepseek",
                    model=settings.llm_fallback_model,
                    base_url=settings.llm_fallback_base_url,
                    api_key=settings.llm_fallback_api_key,
                    priority=2,
                    complexity="complex",
                    cost_per_million=1.0,
                    enabled=True,
                ),
        ]
        db.add_all(configs)

    if settings.llm_local_enabled and not db.query(LLMModelConfig).filter(
        LLMModelConfig.tenant_id == tenant.id,
        LLMModelConfig.provider == "ollama",
    ).first():
        db.add_all(
            [
                LLMModelConfig(
                    tenant_id=tenant.id,
                    name="本地 Qwen（复杂任务）",
                    provider="ollama",
                    model=settings.llm_local_model,
                    base_url=settings.llm_local_base_url,
                    api_key="",
                    priority=0,
                    complexity="complex",
                    cost_per_million=0.0,
                    enabled=True,
                ),
                LLMModelConfig(
                    tenant_id=tenant.id,
                    name="本地 Qwen（轻量任务）",
                    provider="ollama",
                    model=settings.llm_local_model,
                    base_url=settings.llm_local_base_url,
                    api_key="",
                    priority=0,
                    complexity="lite",
                    cost_per_million=0.0,
                    enabled=True,
                ),
            ]
        )

    if not db.query(PromptTemplate).filter(PromptTemplate.tenant_id == tenant.id).first():
        for key, content in PROMPT_TEMPLATES.items():
            db.add(
                PromptTemplate(
                    tenant_id=tenant.id,
                    key=key,
                    content=content,
                    version=1,
                    enabled=True,
                )
            )

    if not db.query(AgentDef).filter(AgentDef.tenant_id == tenant.id).first():
        db.add_all(
            [
                AgentDef(
                    tenant_id=tenant.id,
                    key="ops_assistant",
                    name="消费者运营助手",
                    description="处理日常运营咨询",
                ),
                AgentDef(
                    tenant_id=tenant.id,
                    key="sop_planner",
                    name="社群 SOP 规划",
                    description="生成社群运营计划",
                ),
                AgentDef(
                    tenant_id=tenant.id,
                    key="content_writer",
                    name="内容生成",
                    description="生成私域文案",
                ),
                AgentDef(
                    tenant_id=tenant.id,
                    key="sales_assistant",
                    name="导购助手",
                    description="个性化推荐与销售建议",
                ),
                AgentDef(
                    tenant_id=tenant.id,
                    key="insight_analyst",
                    name="数据洞察",
                    description="解读运营数据",
                ),
            ]
        )

    if not db.query(Capability).filter(Capability.tenant_id == tenant.id).first():
        db.add_all(
            [
                Capability(
                    tenant_id=tenant.id,
                    industry="美业",
                    product="皮肤护理",
                    capability="敏感肌护理方案与话术",
                    match_rules_json={"keywords": ["敏感修护", "补水保湿"]},
                ),
                Capability(
                    tenant_id=tenant.id,
                    industry="美业",
                    product="抗衰项目",
                    capability="抗衰项目介绍与体验邀约",
                    match_rules_json={"keywords": ["抗老紧致"]},
                ),
                Capability(
                    tenant_id=tenant.id,
                    industry="美业",
                    product="营销活动",
                    capability="活动策划与优惠券发放",
                    match_rules_json={"keywords": ["价格敏感", "有顾虑"]},
                ),
                Capability(
                    tenant_id=tenant.id,
                    industry="美业",
                    product="社群运营",
                    capability="社群 SOP 与内容排期",
                    match_rules_json={"keywords": ["身体舒压", "温养调理", "熬夜急救"]},
                ),
            ]
        )

    if not db.query(Strategy).filter(Strategy.tenant_id == tenant.id).first():
        db.add_all(
            [
                Strategy(
                    tenant_id=tenant.id,
                    name="敏感肌关怀策略",
                    strategy_type="sales",
                    agent_key="sales_assistant",
                    params_json={"keywords": ["敏感修护"]},
                ),
                Strategy(
                    tenant_id=tenant.id,
                    name="抗衰体验邀约策略",
                    strategy_type="campaign",
                    agent_key="content_writer",
                    params_json={"keywords": ["抗老紧致"]},
                ),
                Strategy(
                    tenant_id=tenant.id,
                    name="社群内容运营策略",
                    strategy_type="sop",
                    agent_key="sop_planner",
                    params_json={"keywords": ["身体舒压", "温养调理", "熬夜急救"]},
                ),
                Strategy(
                    tenant_id=tenant.id,
                    name="默认运营策略",
                    strategy_type="sop",
                    agent_key="ops_assistant",
                    params_json={"keywords": []},
                ),
            ]
        )

    if not db.query(ToolRegistry).filter(ToolRegistry.tenant_id == tenant.id).first():
        db.add_all(
            [
                ToolRegistry(
                    tenant_id=tenant.id,
                    name="current_time",
                    description="获取当前时间",
                ),
                ToolRegistry(
                    tenant_id=tenant.id,
                    name="echo",
                    description="本地回显工具",
                ),
            ]
        )

    if not db.query(KnowledgeDoc).filter(KnowledgeDoc.tenant_id == tenant.id).first():
        from app.knowledge.service import KnowledgeService

        KnowledgeService(db).ingest(
            tenant.id,
            "敏感肌护理与抗衰知识库.txt",
            SAMPLE_KNOWLEDGE,
            "txt",
            len(SAMPLE_KNOWLEDGE.encode("utf-8")),
        )

    db.commit()
