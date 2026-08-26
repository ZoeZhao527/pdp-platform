#!/usr/bin/env python3
"""精准清洗 strategy_executions.result_json / strategy_tasks.result_json / guardrail_hits.content 中残留的品牌词"""
import sqlite3, json, sys

DB = "/Users/zhaoxinyuan/pdp-platform/backend/demo.db"

# 替换映射（长词在前，避免部分替换）
REPLACEMENTS = [
    # 复合词优先
    ("科莱璞臻奢焕颜活力套盒", "护理套盒"),
    ("美麗田園", "美业品牌"),
    ("美麗", "美业"),
    # 品牌原料 / 护理项目名
    ("科莱璞", "美容仪器"),
    ("科莱", "美容"),
    ("AQUA", "补水"),
    ("API焕能", "焕能护理"),
    ("黄金能量", "滋养护理"),
    ("鱼子精华", "精华护理"),
    ("3D透感", "透感护理"),
    ("冷萃胶原", "胶原护理"),
    ("INFU排补", "排补护理"),
    ("膜力透亮", "透亮护理"),
    ("睛喜雾化", "雾化护理"),
    ("晴喜雾化", "雾化护理"),
    ("多重水动力", "补水护理"),
    ("真肌水光", "水光护理"),
    ("眞肌水光", "水光护理"),
    ("净透润颜", "润颜护理"),
    ("活力悦颜", "悦颜护理"),
    ("富养焕颜", "焕颜护理"),
    ("水感润肤", "润肤护理"),
    ("真肌净澈", "净澈护理"),
    ("眞肌净澈", "净澈护理"),
    ("净润双效", "双效护理"),
    ("臻奢", "奢华"),
    ("金丝颜", "黄金护理"),
    ("美麗", "美业"),
    ("美麗", "美业"),  # variant
    ("万茜", "明星"),
    ("美療師", "护理师"),
    ("SPA疏引", "疏通护理"),
    ("水氧复颜", "复颜护理"),
    # 产品/卡项名
    ("少女鲜肌", "鲜肌护理"),
    ("胶原焕白", "焕白护理"),
    ("夏日亮肤", "亮肤护理"),
    ("晶透焕彩", "焕彩护理"),
    ("轻体排浊", "排浊护理"),
    ("均衡养护", "养护护理"),
    ("双杯紧肤", "紧肤护理"),
    ("纯新胶原", "新胶原护理"),
    ("轻体焕活", "焕活护理"),
]

def clean_text(text):
    if not text or not isinstance(text, str):
        return text
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    return text

def clean_json(obj):
    """递归清洗 JSON 结构里所有字符串"""
    if isinstance(obj, str):
        return clean_text(obj)
    if isinstance(obj, list):
        return [clean_json(item) for item in obj]
    if isinstance(obj, dict):
        return {k: clean_json(v) for k, v in obj.items()}
    return obj

def clean_json_column(table, col, is_json=True):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(f"SELECT id, {col} FROM {table} WHERE {col} IS NOT NULL")
    rows = c.fetchall()
    updated = 0
    for row_id, raw in rows:
        if raw is None:
            continue
        if is_json:
            try:
                data = json.loads(raw)
                cleaned = clean_json(data)
                new_str = json.dumps(cleaned, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                new_str = clean_text(str(raw))
        else:
            new_str = clean_text(str(raw))
        if new_str != raw:
            c.execute(f"UPDATE {table} SET {col} = ? WHERE id = ?", (new_str, row_id))
            updated += 1
    conn.commit()
    conn.close()
    return updated, len(rows)

# 1. strategy_executions.result_json (JSON)
u1, t1 = clean_json_column("strategy_executions", "result_json", is_json=True)
print(f"strategy_executions.result_json: {u1}/{t1} rows updated")

# 2. strategy_executions.metrics_json (JSON)
u2, t2 = clean_json_column("strategy_executions", "metrics_json", is_json=True)
print(f"strategy_executions.metrics_json: {u2}/{t2} rows updated")

# 3. strategy_tasks.result_json (JSON)
u3, t3 = clean_json_column("strategy_tasks", "result_json", is_json=True)
print(f"strategy_tasks.result_json: {u3}/{t3} rows updated")

# 4. strategy_tasks.script (text/JSON hybrid)
u4, t4 = clean_json_column("strategy_tasks", "script", is_json=True)
print(f"strategy_tasks.script: {u4}/{t4} rows updated")

# 5. guardrail_hits.content (plain text)
u5, t5 = clean_json_column("guardrail_hits", "content", is_json=False)
print(f"guardrail_hits.content: {u5}/{t5} rows updated")

# 6. instructions.asset_json (JSON)
u6, t6 = clean_json_column("instructions", "asset_json", is_json=True)
print(f"instructions.asset_json: {u6}/{t6} rows updated")

# 7. instructions.content (text)
u7, t7 = clean_json_column("instructions", "content", is_json=False)
print(f"instructions.content: {u7}/{t7} rows updated")

# 8. strategies.params_json (JSON)
u8, t8 = clean_json_column("strategies", "params_json", is_json=True)
print(f"strategies.params_json: {u8}/{t8} rows updated")

# 9. strategies.name (text)
u9, t9 = clean_json_column("strategies", "name", is_json=False)
print(f"strategies.name: {u9}/{t9} rows updated")

# 10. knowledge_chunks.content (text) — double check
u10, t10 = clean_json_column("knowledge_chunks", "content", is_json=False)
print(f"knowledge_chunks.content: {u10}/{t10} rows updated")

# 11. capabilities.product / capability / description
for col in ["product", "capability", "description"]:
    u, t = clean_json_column("capabilities", col, is_json=False)
    if u > 0:
        print(f"capabilities.{col}: {u}/{t} rows updated")

# 12. demand_signals.raw_content
u12, t12 = clean_json_column("demand_signals", "raw_content", is_json=False)
print(f"demand_signals.raw_content: {u12}/{t12} rows updated")

# 13. match_results.reasons_json (JSON)
u13, t13 = clean_json_column("match_results", "reasons_json", is_json=True)
print(f"match_results.reasons_json: {u13}/{t13} rows updated")

print("\n=== DONE ===")
