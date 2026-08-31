"""为 6 个行业生成演示数据，便于演示全局行业切换。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.flywheel.pipeline import FlywheelService  # noqa: E402
from app.knowledge.service import KnowledgeService  # noqa: E402
from app.llm_gateway.router import LLMRouter  # noqa: E402
from app.models import Capability, DemandSignal, Industry, KnowledgeDoc, Strategy  # noqa: E402

DEMO = {
    "catering": {
        "products": [
            {"name": "招牌双人套餐", "category": "正餐", "price": 298, "efficacy": ["聚餐", "高性价比"], "segments": ["家庭", "白领"], "seasons": ["周末", "节假日"]},
            {"name": "会员储值卡", "category": "会员卡", "price": 1000, "efficacy": ["储值", "返利"], "segments": ["老客", "会员"], "seasons": ["全年"]},
            {"name": "下午茶组合", "category": "茶饮", "price": 88, "efficacy": ["下午茶", "打卡"], "segments": ["女性", "白领"], "seasons": ["下午"]},
            {"name": "节日礼盒", "category": "礼盒", "price": 199, "efficacy": ["送礼", "节日"], "segments": ["送礼人群"], "seasons": ["节庆"]},
        ],
        "knowledge": "餐饮消费者运营要点：会员日折扣、储值卡锁定复购、社群每日菜单预告、异业合作引流。",
        "signals": ["顾客问有没有新菜品优惠", "老客咨询储值卡返利", "周末聚餐人多想提前预约"],
    },
    "retail": {
        "products": [
            {"name": "夏季新品连衣裙", "category": "服装", "price": 399, "efficacy": ["夏季", "新款"], "segments": ["女性", "年轻客群"], "seasons": ["夏季"]},
            {"name": "会员积分卡", "category": "会员卡", "price": 0, "efficacy": ["积分", "复购"], "segments": ["会员"], "seasons": ["全年"]},
            {"name": "爆款秒杀组合", "category": "组合", "price": 199, "efficacy": ["秒杀", "引流"], "segments": ["价格敏感"], "seasons": ["大促"]},
            {"name": "换季套装", "category": "套装", "price": 699, "efficacy": ["换季", "套装"], "segments": ["家庭"], "seasons": ["换季"]},
        ],
        "knowledge": "零售消费者运营要点：新品首发预热、会员积分兑换、秒杀裂变、搭配组合提升客单。",
        "signals": ["顾客问夏季新品什么时候上", "老会员积分怎么兑换", "秒杀活动还有名额吗"],
    },
    "education": {
        "products": [
            {"name": "体验课包", "category": "课程", "price": 99, "efficacy": ["体验", "引流"], "segments": ["新客"], "seasons": ["开学季"]},
            {"name": "季度课程包", "category": "课程", "price": 2999, "efficacy": ["系统学习"], "segments": ["学员"], "seasons": ["学期"]},
            {"name": "续费优惠卡", "category": "会员卡", "price": 0, "efficacy": ["续费", "优惠"], "segments": ["老学员"], "seasons": ["续班季"]},
            {"name": "家长裂变礼包", "category": "活动", "price": 0, "efficacy": ["裂变", "转介绍"], "segments": ["家长"], "seasons": ["全年"]},
        ],
        "knowledge": "教育消费者运营要点：试听课转化、家长转介绍裂变、续费节点提醒、学习成果晒单。",
        "signals": ["家长想约试听课", "学员课程快到期问续费", "家长群想了解转介绍奖励"],
    },
    "pet": {
        "products": [
            {"name": "主粮会员包", "category": "宠物食品", "price": 399, "efficacy": ["主粮", "会员"], "segments": ["养宠家庭"], "seasons": ["全年"]},
            {"name": "洗护服务卡", "category": "宠物服务", "price": 299, "efficacy": ["洗护", "服务"], "segments": ["养宠家庭"], "seasons": ["全年"]},
            {"name": "寄养套餐", "category": "宠物服务", "price": 599, "efficacy": ["寄养", "节假日"], "segments": ["出差人群"], "seasons": ["节假日"]},
            {"name": "宠物生日礼盒", "category": "礼盒", "price": 159, "efficacy": ["生日", "仪式感"], "segments": ["养宠家庭"], "seasons": ["生日"]},
        ],
        "knowledge": "宠物消费者运营要点：洗护服务复购、主粮订阅制、节假日寄养预约、宠物生日关怀。",
        "signals": ["宠物主粮快吃完了问有没有会员价", "想给猫预约洗澡", "节假日想寄养宠物"],
    },
    "health": {
        "products": [
            {"name": "健康管理套餐", "category": "健康管理", "price": 1999, "efficacy": ["健康管理", "体检"], "segments": ["职场人群"], "seasons": ["全年"]},
            {"name": "滋补礼盒", "category": "滋补", "price": 599, "efficacy": ["滋补", "送礼"], "segments": ["中老年"], "seasons": ["节庆"]},
            {"name": "检测服务卡", "category": "服务", "price": 299, "efficacy": ["检测", "健康"], "segments": ["关注健康"], "seasons": ["全年"]},
            {"name": "会员调理卡", "category": "会员卡", "price": 999, "efficacy": ["调理", "复购"], "segments": ["会员"], "seasons": ["全年"]},
        ],
        "knowledge": "大健康消费者运营要点：健康管理订阅、滋补礼盒节庆营销、检测报告解读、会员调理回访。",
        "signals": ["想了解健康管理套餐", "过节想给父母买滋补品", "检测报告想找专业解读"],
    },
}


def main() -> None:
    settings = get_settings()
    tenant_id = settings.default_tenant_id
    with SessionLocal() as db:
        industries = {row.code: row for row in db.query(Industry).all()}
        llm_router = LLMRouter(db)
        flywheel = FlywheelService(db, llm_router)
        knowledge = KnowledgeService(db)

        for code, data in DEMO.items():
            industry = industries.get(code)
            if industry is None:
                continue
            iid = industry.id

            for product in data["products"]:
                exists = db.query(Capability).filter(
                    Capability.tenant_id == tenant_id,
                    Capability.industry_id == iid,
                    Capability.product == product["name"],
                ).first()
                if exists:
                    continue
                db.add(
                    Capability(
                        tenant_id=tenant_id,
                        industry_id=iid,
                        category=product["category"],
                        industry=industry.name,
                        product=product["name"],
                        capability=product["name"],
                        price=product["price"],
                        efficacy_json=product["efficacy"],
                        segments_json=product["segments"],
                        seasons_json=product["seasons"],
                        description=product["name"],
                        is_focus=False,
                        match_rules_json={"keywords": product["efficacy"]},
                    )
                )

            exists_doc = db.query(KnowledgeDoc).filter(
                KnowledgeDoc.tenant_id == tenant_id,
                KnowledgeDoc.industry_id == iid,
            ).first()
            if exists_doc is None:
                knowledge.ingest(
                    tenant_id,
                    f"{industry.name}消费者运营知识库.txt",
                    data["knowledge"],
                    "txt",
                    len(data["knowledge"].encode("utf-8")),
                    industry_id=iid,
                )

            for signal_text in data["signals"]:
                exists_signal = db.query(DemandSignal).filter(
                    DemandSignal.tenant_id == tenant_id,
                    DemandSignal.industry_id == iid,
                    DemandSignal.raw_content == signal_text,
                ).first()
                if exists_signal:
                    continue
                signal = DemandSignal(
                    tenant_id=tenant_id,
                    industry_id=iid,
                    source_type="topic",
                    raw_content=signal_text,
                    status="new",
                )
                db.add(signal)
                db.commit()
                db.refresh(signal)
                flywheel.process_signal(tenant_id, signal)

            if not db.query(Strategy).filter(
                Strategy.tenant_id == tenant_id,
                Strategy.industry_id == iid,
            ).first():
                db.add_all(
                    [
                        Strategy(
                            tenant_id=tenant_id,
                            industry_id=iid,
                            name=f"{industry.name}会员日策略",
                            strategy_type="campaign",
                            agent_key="content_writer",
                            params_json={"keywords": ["会员日", "复购"]},
                            status="草稿",
                            managed=False,
                            enabled=True,
                        ),
                        Strategy(
                            tenant_id=tenant_id,
                            industry_id=iid,
                            name=f"{industry.name}裂变拉新策略",
                            strategy_type="campaign",
                            agent_key="content_writer",
                            params_json={"keywords": ["裂变", "拉新"]},
                            status="草稿",
                            managed=False,
                            enabled=True,
                        ),
                    ]
                )
            db.commit()
            print(f"已生成 {industry.name} 演示数据")


if __name__ == "__main__":
    main()
