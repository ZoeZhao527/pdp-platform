"""需求标签规则（从 Linkstrate-Z 迁移）。"""

from __future__ import annotations

LABEL_RULES = [
    ("补水保湿", ["补水", "保湿", "水润", "干燥", "干敏", "缺水"]),
    ("清洁净颜", ["清洁", "毛孔", "出油", "油皮", "净颜", "黑头"]),
    ("美白提亮", ["美白", "暗沉", "焕白", "亮肤", "提亮", "淡斑", "白皙", "肤色不均"]),
    ("敏感修护", ["敏感", "过敏", "泛红", "修护", "舒缓", "屏障"]),
    ("眼部护理", ["眼部", "眼周", "黑眼圈", "细纹", "眼袋"]),
    ("身体舒压", ["身体", "肩颈", "背部", "疲劳", "酸痛", "放松", "按摩"]),
    ("温养调理", ["温灸", "湿气", "三伏", "养生", "暖养", "驱寒"]),
    ("抗老紧致", ["抗老", "胶原", "紧致", "轮廓", "多肽", "熟龄"]),
    ("熬夜急救", ["熬夜", "气色", "急救", "倦容"]),
]

PRICE_WORDS = ["贵", "比价", "便宜", "优惠", "券", "预算", "性价比", "对比"]
CONCERN_WORDS = ["怕", "担心", "距离", "太远", "外地", "异地", "不能用", "不确定", "犹豫"]


def label_signal(raw: str, segment: str | None = None) -> tuple[str, list[str], float]:
    categories: list[str] = []
    for category, words in LABEL_RULES:
        if any(word in raw for word in words):
            categories.append(category)

    seg = segment or "体验客"
    if "会员" in raw or "老客" in raw or "续" in raw:
        seg = "会员"
    elif "新客" in raw or "第一次" in raw or "首次" in raw:
        seg = "新客"

    tags = list(categories)
    tags.append(f"人群:{seg}")
    if any(word in raw for word in PRICE_WORDS):
        tags.append("价格敏感")
    if any(word in raw for word in CONCERN_WORDS):
        tags.append("有顾虑")

    confidence = min(0.95, 0.55 + 0.12 * len(categories))
    category = categories[0] if categories else "待分类"
    return category, tags, round(confidence, 2)

