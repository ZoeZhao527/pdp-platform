#!/usr/bin/env python3
"""资产包价格重映射 — 把美丽田园特征价位整体偏移"""
import sqlite3, json, re

DB = "/Users/zhaoxinyuan/pdp-platform/backend/demo.db"

# 价格映射表（从大到小排序，避免部分匹配）
PRICE_MAP = {
    # 5位数
    "22198": "22198",  # 非价格，跳过
    # 4位数
    "6280": "6480",
    "5760": "5980",
    "6800": "7200",
    "3980": "4180",
    "3600": "3800",
    "2280": "2480",
    "1980": "2180",
    "1780": "1860",
    "1500": "1800",
    "1040": "1080",
    "1000": "1200",
    # 3位数
    "980": "1020",
    "960": "990",
    "760": "799",
    "680": "720",
    "660": "690",
    "598": "568",
    "549": "580",
    "498": "478",
    "485": "459",
    "450": "470",
    "449": "469",
    "419": "449",
    "399": "429",
    "380": "360",
    "300": "280",
    "299": "259",
    "269": "289",
    "208": "228",
    "198": "218",
    "188": "176",
    "168": "158",
    "1380": "1420",
    "1280": "1320",
    "1580": "1680",
    "197": "217",
    "222": "242",
    # 2位数
    "20": "15",
    "30": "25",
    "11": "9",
    "100": "80",
}

# 按长度降序排列，避免短数字先匹配到长数字的子串
sorted_prices = sorted(PRICE_MAP.items(), key=lambda x: len(x[0]), reverse=True)

def remap_text(text):
    """对文本中的价格做替换 — 只替换后面跟'元'或在价格上下文中的数字"""
    if not text or not isinstance(text, str):
        return text
    # 策略1: 替换 "数字元" 模式
    for old, new in sorted_prices:
        if old == new:
            continue
        # 替换 "数字元" 
        text = text.replace(f"{old}元", f"{new}元")
    # 策略2: 替换 JSON 字段里的独立价格数字
    # 匹配 "price": "198" 或 "selling_price": "1780" 等
    for old, new in sorted_prices:
        if old == new:
            continue
        # "number" in quotes (JSON string value)
        text = text.replace(f'"{old}"', f'"{new}"')
    
    # 策略3: 替换 "数字护理" 这种模式 (如 "1380元护理" 已被策略1处理,
    # 但 "门市价6280" 这种没跟"元"的也要处理)
    # 用正则找所有数字+元的模式做最终扫描
    def replace_price_match(m):
        num = m.group(1)
        if num in PRICE_MAP:
            return f"{PRICE_MAP[num]}元"
        return m.group(0)
    text = re.sub(r'(\d+)元', replace_price_match, text)
    
    return text

def remap_json(obj):
    if isinstance(obj, str):
        return remap_text(obj)
    if isinstance(obj, list):
        return [remap_json(i) for i in obj]
    if isinstance(obj, dict):
        return {k: remap_json(v) for k, v in obj.items()}
    return obj

conn = sqlite3.connect(DB)
c = conn.cursor()

# 处理所有含价格的表
tables_cols = {
    "instructions": ["asset_json", "content"],
    "strategy_executions": ["result_json"],
    "strategy_tasks": ["result_json", "script"],
    "flywheel_metrics": ["snapshot_json"],
    "agent_runs": ["input_json", "output_json"],
    "knowledge_chunks": ["content"],
}

total = 0
for table, cols in tables_cols.items():
    for col in cols:
        c.execute(f'SELECT id, "{col}" FROM "{table}" WHERE "{col}" IS NOT NULL')
        rows = c.fetchall()
        updated = 0
        for row_id, raw in rows:
            if raw is None:
                continue
            # 尝试 JSON 解析
            try:
                data = json.loads(raw)
                cleaned = remap_json(data)
                new_str = json.dumps(cleaned, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                new_str = remap_text(str(raw))
            if new_str != raw:
                c.execute(f'UPDATE "{table}" SET "{col}" = ? WHERE id = ?', (new_str, row_id))
                updated += 1
        if updated > 0:
            print(f"{table}.{col}: {updated} rows updated")
            total += updated

conn.commit()
conn.close()
print(f"\nTotal: {total} rows updated")
