"""为餐饮/零售/教育/宠物/大健康生成行业专属默认模板。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.models import Industry, IndustryTemplate  # noqa: E402


def build_template(code: str) -> dict[str, dict]:
    templates = {
        "catering": {
            "activity": {
                "types": ["会员日", "储值回馈", "新菜上市", "节假日聚餐", "下午茶引流", "异业合作"],
            },
            "catalog": {
                "structure": ["引流款", "主推款", "利润款", "套餐组合"],
                "fields": ["名称", "价格", "成本", "毛利", "库存"],
            },
            "sales": {
                "sections": ["开场话术", "需求挖掘", "异议处理", "成交逼单", "回访节奏"],
                "layers": ["潜客", "新客", "复购", "流失"],
                "objections": [
                    {"issue": "价格太贵", "response": "可以对比套餐价值，推荐高性价比双人餐或储值返利。", "tone": "共情+算账", "scenario": "报价后"},
                    {"issue": "没时间到店", "response": "可先预约周末或工作日晚间时段，提前留位不排队。", "tone": "轻松", "scenario": "犹豫期"},
                    {"issue": "口味不确定", "response": "先推荐招牌菜试吃套餐，降低尝试门槛。", "tone": "真诚", "scenario": "新客"},
                ],
                "layer_plays": [
                    {"layer": "潜客", "goal": "建立信任", "action": "社群每日菜单预告+短视频探店", "script": "今天店里到了新鲜食材，晚上群里发招牌菜实拍。", "follow_up": "T+1 邀请进会员群"},
                    {"layer": "新客", "goal": "首单转化", "action": "招牌双人套餐+储值立减", "script": "新客首单可以叠加会员储值返利，今天最划算。", "follow_up": "到店后 3 天回访"},
                    {"layer": "复购", "goal": "提升频次", "action": "会员日折扣+新菜尝鲜", "script": "会员日到了，这周新菜提前帮你留位。", "follow_up": "节假日前 7 天提醒"},
                    {"layer": "流失", "goal": "召回激活", "action": "储值券+节日礼盒", "script": "好久没来啦，最近上了节日礼盒，想给你留一份。", "follow_up": "召回后 7 天跟进"},
                ],
            },
            "content": {
                "channels": ["朋友圈", "社群", "1v1", "公众号", "短视频"],
                "fields": ["渠道", "素材", "发布时间"],
                "materials": [
                    {"type": "每日菜单预告", "title": "今日菜单", "copy": "今天后厨到了什么，晚上群里见～", "channel": "社群", "purpose": "每日触达"},
                    {"type": "储值活动", "title": "储值返利", "copy": "会员储值满 1000 送 150，常来吃饭更划算。", "channel": "朋友圈", "purpose": "锁定复购"},
                    {"type": "顾客好评", "title": "晒单好评", "copy": "客人说这是本月最舒服的一顿，感谢信任。", "channel": "朋友圈", "purpose": "信任种草"},
                ],
                "schedules": [
                    {"channel": "朋友圈", "cadence": "每日 1 条", "time_slots": "12:00 / 20:00", "content_type": "菜单+晒单", "goal": "日常触达"},
                    {"channel": "社群", "cadence": "每周 3 次", "time_slots": "周一/三/五 19:00", "content_type": "菜单+活动", "goal": "到店转化"},
                    {"channel": "1v1", "cadence": "按节点", "time_slots": "T+0/T+3/T+7", "content_type": "邀约+回访", "goal": "复购召回"},
                ],
            },
            "kpi": {"metrics": ["到店率", "转化率", "储值额", "复购率", "GMV"]},
        },
        "retail": {
            "activity": {
                "types": ["新品首发", "秒杀裂变", "会员积分", "大促节点", "换季清仓"],
            },
            "catalog": {
                "structure": ["引流款", "主推款", "利润款", "组合套装"],
                "fields": ["名称", "价格", "成本", "毛利", "库存"],
            },
            "sales": {
                "sections": ["开场话术", "需求挖掘", "异议处理", "成交逼单", "回访节奏"],
                "layers": ["潜客", "新客", "复购", "流失"],
                "objections": [
                    {"issue": "价格太贵", "response": "搭配套装或积分抵现，整体客单价更划算。", "tone": "算账", "scenario": "报价后"},
                    {"issue": "担心尺码/不合适", "response": "支持无理由退换，先试后买。", "tone": "安心", "scenario": "犹豫期"},
                    {"issue": "等大促再买", "response": "首发价已是最低，叠加会员积分更合适。", "tone": "限时", "scenario": "逼单"},
                ],
                "layer_plays": [
                    {"layer": "潜客", "goal": "建立认知", "action": "新品预告+穿搭种草", "script": "新品下周一上，先放三套搭配给你看。", "follow_up": "上新当天触达"},
                    {"layer": "新客", "goal": "首单转化", "action": "秒杀款+运费险", "script": "秒杀款今天 18:00 开抢，先帮你锁一件。", "follow_up": "收货后 3 天回访"},
                    {"layer": "复购", "goal": "提升连带", "action": "套装搭配+积分加倍", "script": "你上次买的单品配这套新品很搭，积分还能抵现。", "follow_up": "换季前提醒"},
                    {"layer": "流失", "goal": "召回激活", "action": "清仓券+老客专场", "script": "好久不见，老客专场给你留了清仓券。", "follow_up": "召回后 7 天跟进"},
                ],
            },
            "content": {
                "channels": ["朋友圈", "社群", "1v1", "公众号", "短视频"],
                "fields": ["渠道", "素材", "发布时间"],
                "materials": [
                    {"type": "新品预告", "title": "新品剧透", "copy": "新品剧透：本周主打色系先看一波。", "channel": "朋友圈", "purpose": "预热"},
                    {"type": "秒杀裂变", "title": "秒杀倒计时", "copy": "今晚 18:00 秒杀开抢，邀请好友一起更划算。", "channel": "社群", "purpose": "裂变"},
                    {"type": "搭配种草", "title": "一周穿搭", "copy": "一周穿搭灵感：同一件单品三种搭法。", "channel": "短视频", "purpose": "种草"},
                ],
                "schedules": [
                    {"channel": "朋友圈", "cadence": "每日 1 条", "time_slots": "12:00 / 20:00", "content_type": "新品+种草", "goal": "日常触达"},
                    {"channel": "社群", "cadence": "每周 3 次", "time_slots": "周二/四/六 20:00", "content_type": "秒杀+活动", "goal": "转化"},
                    {"channel": "1v1", "cadence": "按节点", "time_slots": "T+0/T+3/T+7", "content_type": "上新+回访", "goal": "复购"},
                ],
            },
            "kpi": {"metrics": ["转化率", "GMV", "连带率", "会员复购率", "ROI"]},
        },
        "education": {
            "activity": {
                "types": ["试听课", "续费季", "转介绍裂变", "开学季", "家长会"],
            },
            "catalog": {
                "structure": ["体验课", "系统课", "续费卡", "裂变礼包"],
                "fields": ["名称", "价格", "课时", "适合人群", "转化路径"],
            },
            "sales": {
                "sections": ["咨询破冰", "试听转化", "异议处理", "续费逼单", "家长回访"],
                "layers": ["新客", "试听学员", "在读学员", "流失学员"],
                "objections": [
                    {"issue": "孩子没兴趣", "response": "先约试听课感受课堂氛围，让孩子自己判断。", "tone": "理解", "scenario": "试听前"},
                    {"issue": "课程价格高", "response": "季度课包分摊后每课时更低，试听满意再定。", "tone": "算账", "scenario": "报价后"},
                    {"issue": "担心效果", "response": "提供阶段学习报告和成果晒单，看得见进步。", "tone": "数据", "scenario": "续费期"},
                ],
                "layer_plays": [
                    {"layer": "新客", "goal": "约试听", "action": "体验课包+家长群", "script": "本周试听课还有 3 个名额，帮你约周六上午？", "follow_up": "试听前 1 天提醒"},
                    {"layer": "试听学员", "goal": "报名转化", "action": "试听后当天优惠", "script": "试听后当天报名送配套教材，名额保留到今晚。", "follow_up": "试听后 3 天跟进"},
                    {"layer": "在读学员", "goal": "续费", "action": "续费季折扣+成果报告", "script": "孩子这学期进步很明显，续费季有专属折扣。", "follow_up": "课程结束前 14 天提醒"},
                    {"layer": "流失学员", "goal": "召回", "action": "老学员礼包+转介绍", "script": "老学员回来可领复课礼包，还能参加转介绍活动。", "follow_up": "召回后 7 天跟进"},
                ],
            },
            "content": {
                "channels": ["家长群", "朋友圈", "1v1", "公众号", "视频号"],
                "fields": ["渠道", "素材", "发布时间"],
                "materials": [
                    {"type": "成果晒单", "title": "学员进步", "copy": "本周学员成果：从不敢开口到主动展示。", "channel": "朋友圈", "purpose": "信任"},
                    {"type": "试听预告", "title": "试听名额", "copy": "本周试听课仅剩 3 个名额，私信预约。", "channel": "家长群", "purpose": "转化"},
                    {"type": "家长课堂", "title": "教育干货", "copy": "家长课堂：如何帮孩子建立学习习惯。", "channel": "公众号", "purpose": "粘性"},
                ],
                "schedules": [
                    {"channel": "朋友圈", "cadence": "每周 5 次", "time_slots": "12:00 / 20:00", "content_type": "晒单+干货", "goal": "信任建设"},
                    {"channel": "家长群", "cadence": "每周 3 次", "time_slots": "周一/三/五 19:30", "content_type": "试听+活动", "goal": "转化"},
                    {"channel": "1v1", "cadence": "按节点", "time_slots": "T+0/T+3/T+7", "content_type": "邀约+回访", "goal": "续费召回"},
                ],
            },
            "kpi": {"metrics": ["试听转化率", "续费率", "转介绍率", "满班率", "营收"]},
        },
        "pet": {
            "activity": {
                "types": ["洗护会员日", "主粮订阅", "节假日寄养", "宠物生日", "新宠家长"],
            },
            "catalog": {
                "structure": ["主粮", "洗护服务", "寄养服务", "礼盒"],
                "fields": ["名称", "价格", "适用宠物", "服务时长", "库存"],
            },
            "sales": {
                "sections": ["破冰", "需求挖掘", "主粮推荐", "洗护逼单", "回访"],
                "layers": ["新宠家长", "洗护客", "主粮会员", "流失客"],
                "objections": [
                    {"issue": "宠物怕生", "response": "洗护师一对一安抚，第一次可以先参观再决定。", "tone": "安心", "scenario": "新客"},
                    {"issue": "主粮怕不适应", "response": "提供试吃装，适应后再订会员包。", "tone": "低门槛", "scenario": "主粮推荐"},
                    {"issue": "寄养担心安全", "response": "每日拍照反馈+24 小时监控，可随时查看。", "tone": "透明", "scenario": "节假日"},
                ],
                "layer_plays": [
                    {"layer": "新宠家长", "goal": "建立信任", "action": "洗护体验卡+养护知识", "script": "新宠到家先做一次温和洗护，顺便教你日常护理。", "follow_up": "洗护后 3 天回访"},
                    {"layer": "洗护客", "goal": "复购", "action": "洗护会员卡+生日护理", "script": "办洗护会员卡送生日美容一次，毛孩子仪式感拉满。", "follow_up": "每 30 天提醒"},
                    {"layer": "主粮会员", "goal": "订阅续费", "action": "主粮会员包+自动配送", "script": "主粮快吃完了吧，会员包自动续费还送零食。", "follow_up": "到期前 7 天提醒"},
                    {"layer": "流失客", "goal": "召回", "action": "寄养预约券+老客礼", "script": "节假日寄养可以提前约，老客还有专属礼。", "follow_up": "召回后 7 天跟进"},
                ],
            },
            "content": {
                "channels": ["朋友圈", "社群", "1v1", "视频号", "公众号"],
                "fields": ["渠道", "素材", "发布时间"],
                "materials": [
                    {"type": "宠物日常", "title": "毛孩子日常", "copy": "今日洗护小可爱出镜，欢迎来群里云吸宠。", "channel": "社群", "purpose": "活跃"},
                    {"type": "服务种草", "title": "洗护前后", "copy": "洗护前后对比来了，蓬松感直接拉满。", "channel": "朋友圈", "purpose": "种草"},
                    {"type": "节日提醒", "title": "寄养预约", "copy": "国庆寄养位已开放预约，早约早安心。", "channel": "朋友圈", "purpose": "转化"},
                ],
                "schedules": [
                    {"channel": "朋友圈", "cadence": "每日 1 条", "time_slots": "12:00 / 20:00", "content_type": "萌宠+种草", "goal": "日常触达"},
                    {"channel": "社群", "cadence": "每周 3 次", "time_slots": "周二/四/六 19:30", "content_type": "云吸宠+活动", "goal": "活跃转化"},
                    {"channel": "1v1", "cadence": "按节点", "time_slots": "T+0/T+3/T+7", "content_type": "洗护+回访", "goal": "复购"},
                ],
            },
            "kpi": {"metrics": ["洗护复购率", "订阅续费率", "寄养预订率", "客单价", "GMV"]},
        },
        "health": {
            "activity": {
                "types": ["健康管理订阅", "滋补节庆", "检测服务", "会员调理", "专家直播"],
            },
            "catalog": {
                "structure": ["健康管理套餐", "滋补礼盒", "检测服务", "会员调理卡"],
                "fields": ["名称", "价格", "适用人群", "服务周期", "复购路径"],
            },
            "sales": {
                "sections": ["咨询破冰", "健康需求挖掘", "异议处理", "会员促成", "调理回访"],
                "layers": ["关注健康", "检测客", "调理会员", "流失会员"],
                "objections": [
                    {"issue": "价格高", "response": "会员调理按月分摊，含检测和报告解读。", "tone": "算账", "scenario": "报价后"},
                    {"issue": "担心过度推销", "response": "先做检测出报告，按结果给建议，不强制办卡。", "tone": "专业", "scenario": "新客"},
                    {"issue": "调理效果慢", "response": "提供周期数据对比，每阶段都有可量化的变化。", "tone": "数据", "scenario": "复购"},
                ],
                "layer_plays": [
                    {"layer": "关注健康", "goal": "建立专业信任", "action": "健康干货+检测科普", "script": "先分享一份常见误区清单，感兴趣再约检测。", "follow_up": "内容后 3 天触达"},
                    {"layer": "检测客", "goal": "报告解读转化", "action": "检测报告+会员调理", "script": "报告出来了，我帮你约个时间详细解读。", "follow_up": "解读后 3 天跟进"},
                    {"layer": "调理会员", "goal": "续费", "action": "周期对比+会员权益", "script": "这个周期数据比上期改善明显，续费还有权益。", "follow_up": "周期结束前 7 天提醒"},
                    {"layer": "流失会员", "goal": "召回", "action": "复检套餐+老客礼", "script": "好久没做复检了，老客复检有专属套餐。", "follow_up": "召回后 7 天跟进"},
                ],
            },
            "content": {
                "channels": ["朋友圈", "社群", "1v1", "公众号", "短视频"],
                "fields": ["渠道", "素材", "发布时间"],
                "materials": [
                    {"type": "健康干货", "title": "今日健康课", "copy": "今日健康课：熬夜后如何快速恢复状态。", "channel": "公众号", "purpose": "专业信任"},
                    {"type": "客户见证", "title": "调理反馈", "copy": "会员 3 个月调理反馈：睡眠和精力都有改善。", "channel": "朋友圈", "purpose": "信任"},
                    {"type": "节庆滋补", "title": "滋补礼盒", "copy": "节庆滋补礼盒上线，送父母很合适。", "channel": "社群", "purpose": "转化"},
                ],
                "schedules": [
                    {"channel": "朋友圈", "cadence": "每日 1 条", "time_slots": "12:00 / 20:00", "content_type": "干货+见证", "goal": "日常触达"},
                    {"channel": "社群", "cadence": "每周 3 次", "time_slots": "周一/三/五 19:30", "content_type": "健康+活动", "goal": "转化"},
                    {"channel": "1v1", "cadence": "按节点", "time_slots": "T+0/T+3/T+7", "content_type": "检测+回访", "goal": "复购"},
                ],
            },
            "kpi": {"metrics": ["订阅续费率", "检测到店率", "复购率", "客单价", "GMV"]},
        },
    }
    return templates[code]


def main() -> None:
    codes = ["catering", "retail", "education", "pet", "health"]
    with SessionLocal() as db:
        industries = {row.code: row for row in db.query(Industry).all()}
        updated = 0
        created = 0
        for code in codes:
            industry = industries.get(code)
            if industry is None:
                print(f"[跳过] 未找到行业 {code}")
                continue
            for kind, data in build_template(code).items():
                row = (
                    db.query(IndustryTemplate)
                    .filter(
                        IndustryTemplate.industry_id == industry.id,
                        IndustryTemplate.kind == kind,
                    )
                    .first()
                )
                if row is None:
                    db.add(
                        IndustryTemplate(
                            industry_id=industry.id,
                            kind=kind,
                            name=f"{industry.name} {kind} 模板",
                            data_json=data,
                            enabled=True,
                        )
                    )
                    created += 1
                else:
                    row.data_json = data
                    updated += 1
            print(f"[完成] {industry.name} 模板")
        db.commit()
        print(f"新增 {created} 个模板，更新 {updated} 个模板")


if __name__ == "__main__":
    main()
