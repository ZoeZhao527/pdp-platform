"""platform.py - wrapper: loads original bytecode from .pyc and patches generation logic.

Patches:
- Normalizes campaign_brief card keys (Chinese -> English)
- Extracts prices from brand card items, matches to care_items KB by price
- Injects matched care item details into instruction content for ALL LLM steps
- Post-generation: cleans product_mix to keep only brand card + matched care items
- chat_instruction: creates instruction directly, no clarification loop
"""
import os
import re
import json
import importlib.util
from importlib.machinery import SourcelessFileLoader
import unicodedata

_PYC = os.path.join(os.path.dirname(__file__), "__pycache__", "platform_orig.cpython-312.pyc")

_spec = importlib.util.spec_from_loader(
    "app.api._platform_pyc",
    SourcelessFileLoader("app.api._platform_pyc", _PYC),
)
_orig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_orig)

for _name in dir(_orig):
    globals()[_name] = getattr(_orig, _name)

router = _orig.router

# ---------------------------------------------------------------------------
# Campaign brief key normalization (Chinese brand-material keys -> English)
# ---------------------------------------------------------------------------
_KEY_MAP = {
    'card_name': 'card_name', '卡名': 'card_name', '名称': 'card_name',
    '套餐名称': 'card_name', '护理名称': 'card_name', '项目名称': 'card_name',
    '品名': 'card_name', '产品名称': 'card_name', '卡项名称': 'card_name',
    '疗程名称': 'card_name', '套餐名': 'card_name',
    'card_type': 'card_type', '卡种': 'card_type', '卡类型': 'card_type',
    '类型': 'card_type', '套餐类型': 'card_type',
    'market_price': 'market_price', '门市价': 'market_price', '原价': 'market_price',
    '原门市价': 'market_price', '标准价': 'market_price', '面价': 'market_price',
    '标价': 'market_price', '总价': 'market_price', '价值': 'market_price',
    'selling_price': 'selling_price', '售价': 'selling_price', '定价': 'selling_price',
    '活动价': 'selling_price', '促销价': 'selling_price', '优惠价': 'selling_price',
    '到手价': 'selling_price', '特价': 'selling_price', '推广价': 'selling_price',
    '销售价': 'selling_price', '结算价': 'selling_price',
    'items': 'items', '包含项目': 'items', '项目': 'items',
    '套餐内容': 'items', '套餐项目': 'items', '内容': 'items',
    '护理项目': 'items', '卡内容': 'items', '套餐明细': 'items',
    '包含内容': 'items', '卡项内容': 'items', '组合内容': 'items',
    'selling_point': 'selling_point', '卖点': 'selling_point',
    '主图一卖点提炼': 'selling_point', '卖点提炼': 'selling_point',
    '核心卖点': 'selling_point', '主图卖点': 'selling_point',
    '产品卖点': 'selling_point',
    'discount': 'discount', '折扣': 'discount', '折扣率': 'discount',
    'bonus': 'bonus', '赠品': 'bonus', '礼品': 'bonus', '赠项': 'bonus',
    'detail': 'detail', '详情推荐护理及功效': 'detail',
    '推荐护理': 'detail', '护理详情': 'detail', '功效': 'detail',
    'recommended_items': 'recommended_items',
    '主图二推荐护理': 'recommended_items',
    '推荐护理搭配': 'recommended_items',
}


def _normalize_campaign_brief(cb):
    """Normalize campaign_brief card keys to the format _llm_generate_asset expects."""
    if not cb or not isinstance(cb, dict):
        return cb
    cards = cb.get('cards')
    if not cards or not isinstance(cards, list):
        return cb
    new_cards = []
    for card in cards:
        if not isinstance(card, dict):
            new_cards.append(card)
            continue
        new_card = {}
        for k, v in card.items():
            mapped = _KEY_MAP.get(k, k)
            new_card[mapped] = v
            if mapped != k:
                new_card[k] = v
        new_cards.append(new_card)
    return {'cards': new_cards, **{k: v for k, v in cb.items() if k != 'cards'}}


# ---------------------------------------------------------------------------
# NEW: Extract price-count pairs from brand card items string
# ---------------------------------------------------------------------------
def _extract_price_count_pairs(items_str):
    """Parse '1380元护理*1+980元护理*2' -> [(1380, 1), (980, 2)]"""
    if not items_str or not isinstance(items_str, str):
        return []
    # Try pattern: number + 元 + ... + separator + number
    pairs = re.findall(r'(\d+)\s*元[^*+\-]+[*\xd7xx]\s*(\d+)', items_str)
    result = [(int(p), int(c)) for p, c in pairs]
    if not result:
        # Fallback: just extract prices with 元 suffix
        prices = re.findall(r'(\d+)\s*元', items_str)
        result = [(int(p), 1) for p in prices]
    return result


# ---------------------------------------------------------------------------
# NEW: Match care items by price from knowledge base (care_items category)
# ---------------------------------------------------------------------------
def _match_care_items_by_price(db, tenant_id, price_count_pairs):
    """Search care_items KB docs for items matching each price."""
    if not price_count_pairs:
        return {}

    try:
        from sqlalchemy import text as _sql_text
        rows = db.execute(_sql_text(
            "SELECT id FROM knowledge_docs "
            "WHERE tenant_id = :tid AND metadata_json LIKE '%care_items%'"
        ), {"tid": tenant_id}).fetchall()
        doc_ids = [r[0] for r in rows]
    except Exception:
        doc_ids = []

    if not doc_ids:
        return {p: {'count': c, 'items': []} for p, c in price_count_pairs}

    # Fetch all chunks from care_items docs
    try:
        from sqlalchemy import text as _sql_text
        if len(doc_ids) == 1:
            chunks = db.execute(_sql_text(
                "SELECT content FROM knowledge_chunks WHERE doc_id = :did"
            ), {"did": doc_ids[0]}).fetchall()
        else:
            placeholders = ','.join([f':d{i}' for i in range(len(doc_ids))])
            params = {f'd{i}': doc_ids[i] for i in range(len(doc_ids))}
            chunks = db.execute(_sql_text(
                f"SELECT content FROM knowledge_chunks WHERE doc_id IN ({placeholders})"
            ), params).fetchall()
    except Exception:
        chunks = []

    all_content = '\n'.join([(c[0] or '') for c in chunks])
    lines = all_content.split('\n')

    matched = {}
    for price, count in price_count_pairs:
        price_str = str(price)
        items = []
        for line in lines:
            # Match price as a pipe-delimited field: | 1380 | or |1380|
            if f'| {price_str} |' in line or f'|{price_str}|' in line:
                parts = [p.strip() for p in line.split('|')]
                category = parts[0] if parts else ''
                # Find name with Chinese brackets
                name_matches = re.findall(r'([^|\s]*[\u3010-\u3011][^|\s]*)', line)
                if not name_matches:
                    # Fallback: look for the 5th field (index 4)
                    if len(parts) > 4:
                        candidate = parts[4].strip()
                        if candidate and len(candidate) > 2:
                            name_matches = [candidate]
                for nm in name_matches:
                    nm = nm.strip()
                    # Filter noise: must have Chinese chars, > 4 chars, not purely numeric
                    has_chinese = bool(re.search(r'[一-鿿]', nm))
                    too_short = len(nm) < 5
                    is_numeric = nm.replace('【','').replace('】','').strip().isdigit()
                    if (nm and has_chinese and not too_short and not is_numeric
                            and nm not in [i['name'] for i in items]):
                        items.append({
                            'name': nm,
                            'category': category,
                            'price': price,
                        })
        matched[price] = {'count': count, 'items': items}

    return matched


# ---------------------------------------------------------------------------
# NEW: Build structured context block for LLM injection
# ---------------------------------------------------------------------------
def _build_care_item_context(brand_card, matched):
    """Build a text block with matched care items for LLM instruction injection."""
    lines = ['\n\n【品牌卡项包含的护理项目 - 按门市价匹配原料库结果】']

    cn = brand_card.get('card_name') or brand_card.get('套餐名称') or ''
    ct = brand_card.get('card_type') or brand_card.get('卡种') or ''
    mp = brand_card.get('market_price') or brand_card.get('门市价') or ''
    sp = brand_card.get('selling_price') or brand_card.get('活动价') or ''
    disc = brand_card.get('discount') or brand_card.get('折扣') or ''
    sp_pt = brand_card.get('selling_point') or brand_card.get('主图一卖点提炼') or ''
    items_str = brand_card.get('items') or brand_card.get('套餐内容') or ''

    lines.append(f'品牌主推卡: {cn} | 类型: {ct} | 门市价: {mp} | 活动价: {sp} | 折扣: {disc}')
    if sp_pt:
        lines.append(f'核心卖点: {sp_pt}')
    if items_str:
        lines.append(f'卡项组成: {items_str}')
    lines.append('')
    lines.append('该卡包含以下护理项目（已从护理项目原料库按门市价匹配）:')

    for price, info in matched.items():
        count = info['count']
        items = info['items']
        lines.append(f'\n门市价{price}元护理项目（卡内含{count}次）:')
        if items:
            for item in items[:8]:
                lines.append(f'  - {item["name"]}（品项分类: {item["category"]}）')
        else:
            lines.append(f'  （原料库未找到{price}元价位匹配项，请根据该价位护理项目特点生成内容）')

    lines.append('')
    lines.append('重要规则:')
    lines.append('1. 销售话术、朋友圈内容、内容排期、活动详情必须围绕上述具体护理项目的功效和卖点展开')
    lines.append('2. 货盘只需展示品牌主推卡，不要从知识库拉取其他成品卡塞入货盘')
    lines.append('3. 客服1v1话术要从客户肤质/需求切入，推荐对应的护理项目')
    lines.append('4. 朋友圈内容要体现护理项目的具体功效价值，而非泛泛而谈')

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Monkey-patch _llm_generate_asset: normalize campaign_brief keys
# ---------------------------------------------------------------------------
_orig_llm_generate_asset = _orig._llm_generate_asset


def _patched_llm_generate_asset(db, llm_router, tenant_id, instruction, params, template_map,
                                products, knowledge_refs, card_catalog, reasoning, campaign_brief):
    cb = _normalize_campaign_brief(campaign_brief)
    result = _orig_llm_generate_asset(db, llm_router, tenant_id, instruction, params,
                                      template_map, products, knowledge_refs,
                                      card_catalog, reasoning, cb)
    return result


_orig._llm_generate_asset = _patched_llm_generate_asset


# ---------------------------------------------------------------------------
# Wrap _generate_instruction_impl: inject care item context + clean product_mix
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# KB context injection: search knowledge base for care items, sales scripts,
# and activity patterns relevant to the instruction, inject as LLM context.
# ---------------------------------------------------------------------------
_SEASON_KEYWORDS = {
    '春': ['春季', '春天', '换季', '抗敏', '舒缓', '初春'],
    '夏': ['夏季', '夏天', '防晒', '晒后', '控油', '美白', '清凉'],
    '秋': ['秋季', '秋天', '换季', '补水', '保湿', '修护', '干燥', '初秋'],
    '冬': ['冬季', '冬天', '滋养', '润燥', '保暖', '深层滋润'],
}


def _build_kb_context_injection(content, db, tenant_id):
    """Search KB for relevant care items, sales scripts, and activity patterns.
    Returns a context string to append to instruction content, or '' if none."""
    if not content or not tenant_id:
        return ''
    from sqlalchemy import text as _sql_text
    lines = ['\n\n【知识库参考上下文 - 基于品牌真实资料生成内容，不要泛泛而谈】']

    # --- Inject current date + season so LLM matches the right season ---
    from datetime import datetime as _dt
    _now = _dt.now()
    _month = _now.month
    if _month in (2, 3):
        _season = '初春'
    elif _month in (4, 5):
        _season = '春末夏初'
    elif _month in (6, 7):
        _season = '夏季'
    elif _month == 8:
        _season = '夏末秋初'
    elif _month in (9, 10):
        _season = '秋季'
    elif _month == 11:
        _season = '秋末冬初'
    else:
        _season = '冬季'
    lines.append(f'【当前时间】{_now.strftime("%Y年%m月%d日")} {_season}（所有活动策划、内容排期必须匹配当前季节 {_season}，禁止使用其他季节）')

    # --- Inject brand sales logic (target/no-touch segments) ---
    try:
        _trow = db.execute(_sql_text("SELECT config_json FROM tenants WHERE id = :tid"), {"tid": tenant_id}).fetchone()
        if _trow and _trow[0]:
            _tcfg = json.loads(_trow[0])
            _sl = _tcfg.get("sales_logic")
            if _sl:
                _rule = _sl.get("rule", "")
                _targets = ", ".join(_sl.get("target_segments", []))
                _notouch = ", ".join(_sl.get("no_touch_segments", []))
                lines.append(f"\n【品牌销售逻辑】{_rule}。目标人群：{_targets}。不触达人群：{_notouch}。所有销售话术、分层打法、朋友圈内容只针对目标人群，不对不触达人群做任何销售动作。")
    except Exception:
        pass

    def _norm(t):
        if not t:
            return ''
        return unicodedata.normalize('NFKC', t).replace('\u3000', ' ').replace('\r', '')

    def _sanitize_kw(kw):
        """Escape single quotes for safe SQL LIKE interpolation."""
        return kw.replace("'", "''").replace("%", "\\%").replace("_", "\\_")

    # 1. Extract keywords from instruction content
    keywords = set()
    for season, kws in _SEASON_KEYWORDS.items():
        if any(kw in content for kw in [season] + kws):
            keywords.update(kws)
    # Card type keywords
    for card_kw in ['三次卡', '四次卡', '六次卡', '体验卡', '疗程卡', '储值卡', '单次', '月卡']:
        if card_kw in content:
            keywords.add(card_kw)
    # Action / care-area keywords
    for act_kw in ['补水', '修护', '美白', '抗衰', '祛痘', '舒缓', '排毒', '塑形', '肩颈', '眼部',
                   '面部', '身体', '清洁', '保湿', '紧致', '淡斑', '控油', '滋养', '抗敏',
                   '防晒', '晒后', '头部', '背部', '腿部', '手部', '排毒', '排湿', '通络']:
        if act_kw in content:
            keywords.add(act_kw)
    # Extract 2-4 char Chinese terms from instruction text for targeted search
    _stopwords = {'不要', '可以', '需要', '一个', '这个', '那个', '什么', '怎么',
                  '我们', '你们', '他们', '她们', '自己', '知道', '明白', '理解',
                  '但是', '因为', '所以', '如果', '虽然', '不过', '然后', '现在',
                  '已经', '还是', '或者', '应该', '可能', '一定', '必须', '重要',
                  '生成', '内容', '参考', '围绕', '给我', '给我', '帮忙', '帮我'}
    for term in re.findall(r'[\u4e00-\u9fff]{2,4}', content):
        if term not in _stopwords:
            keywords.add(term)
    if not keywords:
        keywords = {'补水', '修护', '护理'}

    # Limit to 8 keywords to keep SQL manageable
    kw_list = sorted(keywords, key=lambda k: len(k), reverse=True)[:8]
    def _kw_or(alias='kc.content'):
        """Build OR clause from keyword list for SQL LIKE."""
        if not kw_list:
            return '1=1'
        return ' OR '.join(f"{alias} LIKE '%{_sanitize_kw(k)}%'" for k in kw_list)

    # 2. Search KB for care items with pricing — keyword-filtered, fallback to broad
    try:
        kw_cond = _kw_or()
        care_chunks = db.execute(_sql_text(
            f"SELECT content FROM knowledge_chunks kc "
            f"JOIN knowledge_docs kd ON kc.doc_id = kd.id "
            f"WHERE kd.tenant_id = :tid AND kc.content LIKE '%门市价%' "
            f"AND ({kw_cond}) "
            f"ORDER BY LENGTH(kc.content) DESC LIMIT 5"
        ), {"tid": tenant_id}).fetchall()
        if not care_chunks:
            care_chunks = db.execute(_sql_text(
            "SELECT content FROM knowledge_chunks kc "
            "JOIN knowledge_docs kd ON kc.doc_id = kd.id "
            "WHERE kd.tenant_id = :tid AND kc.content LIKE '%门市价%' "
            "ORDER BY LENGTH(kc.content) DESC LIMIT 5"
            ), {"tid": tenant_id}).fetchall()
        if care_chunks:
            lines.append('\n--- 品牌护理项目参考（含门市价，用于组卡和话术参考）---')
            for ch in care_chunks[:3]:
                txt = _norm(ch[0])[:500] if ch[0] else ''
                lines.append(txt)
    except Exception:
        pass

    # 3. Search KB for sales script examples — keyword-filtered, fallback to broad
    try:
        kw_cond2 = _kw_or()
        script_chunks = db.execute(_sql_text(
            f"SELECT content FROM knowledge_chunks kc "
            f"JOIN knowledge_docs kd ON kc.doc_id = kd.id "
            f"WHERE kd.tenant_id = :tid AND "
            f"(kc.content LIKE '%话术%' OR kc.content LIKE '%朋友圈%' OR kc.content LIKE '%1v1%' OR kc.content LIKE '%销售%') "
            f"AND ({kw_cond2}) "
            f"ORDER BY LENGTH(kc.content) DESC LIMIT 3"
        ), {"tid": tenant_id}).fetchall()
        if not script_chunks:
            script_chunks = db.execute(_sql_text(
            "SELECT content FROM knowledge_chunks kc "
            "JOIN knowledge_docs kd ON kc.doc_id = kd.id "
            "WHERE kd.tenant_id = :tid AND "
            "(kc.content LIKE '%话术%' OR kc.content LIKE '%朋友圈%' OR kc.content LIKE '%1v1%' OR kc.content LIKE '%销售%') "
            "ORDER BY LENGTH(kc.content) DESC LIMIT 3"
            ), {"tid": tenant_id}).fetchall()
        if script_chunks:
            lines.append('\n--- 品牌话术参考（请参考风格和结构，但不要照搬）---')
            for ch in script_chunks[:2]:
                txt = _norm(ch[0])[:500] if ch[0] else ''
                lines.append(txt)
    except Exception:
        pass

    # 4. Search KB for activity pattern examples — keyword-filtered, fallback to broad
    try:
        kw_cond3 = _kw_or()
        act_chunks = db.execute(_sql_text(
            f"SELECT content FROM knowledge_chunks kc "
            f"JOIN knowledge_docs kd ON kc.doc_id = kd.id "
            f"WHERE kd.tenant_id = :tid AND "
            f"(kc.content LIKE '%活动%' OR kc.content LIKE '%排期%' OR kc.content LIKE '%货盘%') "
            f"AND ({kw_cond3}) "
            f"ORDER BY LENGTH(kc.content) DESC LIMIT 3"
        ), {"tid": tenant_id}).fetchall()
        if not act_chunks:
            act_chunks = db.execute(_sql_text(
            "SELECT content FROM knowledge_chunks kc "
            "JOIN knowledge_docs kd ON kc.doc_id = kd.id "
            "WHERE kd.tenant_id = :tid AND "
            "(kc.content LIKE '%活动%' OR kc.content LIKE '%排期%' OR kc.content LIKE '%货盘%') "
            "ORDER BY LENGTH(kc.content) DESC LIMIT 3"
            ), {"tid": tenant_id}).fetchall()
        if act_chunks:
            lines.append('\n--- 品牌过往活动参考（参考活动节奏和货盘结构）---')
            for ch in act_chunks[:2]:
                txt = _norm(ch[0])[:500] if ch[0] else ''
                lines.append(txt)
    except Exception:
        pass

    lines.append('\n--- 生成要求 ---')
    lines.append('1. 活动规划要有具体的玩法机制（拼团几人几折、储值返利金额、秒杀时间和数量）')
    lines.append('2. 货盘卡项的护理项目要参考上面品牌真实项目名和门市价')
    lines.append('3. 1v1话术要结合具体护理项目功效，不要泛泛而谈')
    lines.append('4. 朋友圈内容要多样：种草、科普、见证、活动、互动交替')
    lines.append('5. 社群内容要有群内互动设计（打卡、抽奖、接龙等）')

    result = '\n'.join(lines)
    if len(result) < 50:
        return ''
    return _norm(result)[:2500]  # Cap at 2500 chars — enough for meaningful context


_orig_generate_instruction_impl = _orig._generate_instruction_impl


def _patched_generate_instruction_impl(instruction_id, runtime):
    # --- PRE-GENERATION: inject care item context into instruction content ---
    instr = runtime.db.query(_orig.Instruction).filter(
        _orig.Instruction.id == instruction_id
    ).first()

    orig_content = None
    kb_context = _build_kb_context_injection(instr.content if instr else '', runtime.db, runtime.tenant_id)
    if kb_context and instr:
        orig_content = instr.content
        instr.content = instr.content + kb_context
        runtime.db.commit()

    if instr and instr.campaign_brief_json:
        try:
            cb_raw = instr.campaign_brief_json
            cb = json.loads(cb_raw) if isinstance(cb_raw, str) else cb_raw
        except Exception:
            cb = None
        cb = _normalize_campaign_brief(cb)

        if cb and isinstance(cb, dict) and cb.get('cards'):
            all_cards = [c for c in cb['cards'] if isinstance(c, dict)]
            card_count = len(all_cards)

            # Build context for EACH brand card (not just the first)
            brand_lines = [f"\n【品牌指定销售卡项 - 共{card_count}张 - 必须围绕这些卡项生成所有内容】"]
            brand_lines.append("重要：不要自己组卡，不要从知识库添加额外卡项，货盘只包含以下品牌指定的卡项。")
            brand_lines.append("")

            for idx, bc in enumerate(all_cards):
                bcn = bc.get('card_name') or bc.get('套餐名称') or ''
                bct = bc.get('card_type') or bc.get('卡种') or ''
                bmp = bc.get('market_price') or bc.get('门市价') or ''
                bsp = bc.get('selling_price') or bc.get('活动价') or ''
                bdisc = bc.get('discount') or bc.get('折扣') or ''
                bsp_pt = bc.get('selling_point') or bc.get('主图一卖点提炼') or ''
                bc_items = bc.get('items') or bc.get('套餐内容') or ''

                # Per-card care item matching
                price_pairs = _extract_price_count_pairs(bc_items)
                matched = _match_care_items_by_price(runtime.db, runtime.tenant_id, price_pairs)
                context_text = _build_care_item_context(bc, matched)

                bline = f"【卡{idx+1}】卡名: {bcn}"
                if bct:
                    bline += f" | 类型: {bct}"
                if bmp:
                    bline += f" | 门市价: {bmp}"
                if bsp:
                    bline += f" | 活动价: {bsp}"
                if bdisc:
                    bline += f" | 折扣: {bdisc}"
                if bc_items:
                    bline += f" | 包含: {bc_items}"
                if bsp_pt:
                    bline += f" | 卖点: {bsp_pt}"
                brand_lines.append(bline)
                brand_lines.append(context_text)

            full_injection = '\n'.join(brand_lines)
            if orig_content is None:
                orig_content = instr.content
            instr.content = instr.content + full_injection
            runtime.db.commit()

    # --- CALL ORIGINAL GENERATION PIPELINE ---
    try:
        result = _orig_generate_instruction_impl(instruction_id, runtime)
    except Exception as gen_err:
        import traceback as _tb
        with open('/tmp/patch_debug.log', 'a') as _f:
            _f.write(f"GEN ERROR {instruction_id}: {gen_err}\n{_tb.format_exc()}\n")
        if orig_content is not None:
            try:
                instr_e = runtime.db.query(_orig.Instruction).filter(
                    _orig.Instruction.id == instruction_id
                ).first()
                if instr_e:
                    instr_e.content = orig_content
                    instr_e.status = '生成失败'
                    runtime.db.commit()
            except Exception:
                pass
        raise

    # --- RESTORE original instruction content ---
    if orig_content is not None:
        try:
            instr2 = runtime.db.query(_orig.Instruction).filter(
                _orig.Instruction.id == instruction_id
            ).first()
            if instr2:
                instr2.content = orig_content
                runtime.db.commit()
        except Exception:
            pass

    # --- FAILURE DETECTION: if generation returned empty asset, mark as failed ---
    try:
        if result is None or not isinstance(result, dict) or not result.get("asset"):
            instr_fail = runtime.db.query(_orig.Instruction).filter(
                _orig.Instruction.id == instruction_id
            ).first()
            if instr_fail and instr_fail.status == "\u751f\u6210\u4e2d":
                instr_fail.status = "\u751f\u6210\u5931\u8d25"
                runtime.db.commit()
            return result if result else {}
    except Exception:
        pass

    # --- POST-GENERATION: clean up product_mix ---
    try:
        if not isinstance(result, dict):
            return result
        asset = result.get('asset')
        if not isinstance(asset, dict):
            return result

        # Re-read instruction for campaign_brief
        # --- GLOBAL CLEANUP: applied to ALL asset packs ---
        _TEXT_FIXES = {
            '多莓水动力': '多重水动力',
            '多莓': '多重',
        }
        def _fix_text(obj):
            if isinstance(obj, str):
                for old, new in _TEXT_FIXES.items():
                    obj = obj.replace(old, new)
                return obj
            elif isinstance(obj, dict):
                return {k: _fix_text(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_fix_text(v) for v in obj]
            return obj
        try:
            asset = _fix_text(asset)
            result['asset'] = asset
        except Exception:
            pass

        # Clean up product_mix: only show cards, not individual care items
        cs_existing = asset.get('card_structure')
        if isinstance(cs_existing, dict):
            cs_cards = cs_existing.get('cards', [])
            if isinstance(cs_cards, list) and len(cs_cards) > 0:
                # product_mix should mirror card_structure.cards, not show 26 individual items
                pm = asset.get('product_mix')
                if isinstance(pm, list) and len(pm) > len(cs_cards):
                    asset['product_mix'] = cs_cards

        # Persist global cleanup to instruction.asset_json
        try:
            instr_global = runtime.db.query(_orig.Instruction).filter(
                _orig.Instruction.id == instruction_id
            ).first()
            if instr_global:
                instr_global.asset_json = asset
                runtime.db.commit()
        except Exception:
            pass

        # --- BRAND CARD CLEANUP: only when campaign_brief has cards ---
        instr3 = runtime.db.query(_orig.Instruction).filter(
            _orig.Instruction.id == instruction_id
        ).first()
        with open('/tmp/patch_debug.log', 'a') as _dbg:
            _dbg.write(f"BRAND_CLEANUP_START instr={instruction_id} cb_json={'yes' if instr3 and instr3.campaign_brief_json else 'no'}\n")
        if not instr3 or not instr3.campaign_brief_json:
            return result

        try:
            cb_raw = instr3.campaign_brief_json
            cb = json.loads(cb_raw) if isinstance(cb_raw, str) else cb_raw
        except Exception:
            cb = None
        cb = _normalize_campaign_brief(cb)

        if not cb or not isinstance(cb, dict) or not cb.get('cards'):
            return result

        all_cards = [c for c in cb['cards'] if isinstance(c, dict)]

        # Build clean entries for ALL brand cards
        clean_cards = []
        all_brand_names = []
        for bc in all_cards:
            bcn = bc.get('card_name') or bc.get('套餐名称') or ''
            if bcn:
                all_brand_names.append(bcn)
            bc_items = bc.get('items') or bc.get('套餐内容') or ''
            price_pairs = _extract_price_count_pairs(bc_items)
            matched = _match_care_items_by_price(runtime.db, runtime.tenant_id, price_pairs)

            contains = []
            for price, info in matched.items():
                item_names = [i['name'] for i in info['items'][:5]]
                contains.append({
                    'price': price,
                    'count': info['count'],
                    'care_items': item_names,
                })

            clean_card = {
                'name': bcn,
                'card_name': bcn,
                'card_type': bc.get('card_type') or bc.get('卡种') or '',
                'market_price': str(bc.get('market_price') or bc.get('门市价') or ''),
                'selling_price': str(bc.get('selling_price') or bc.get('活动价') or ''),
                'items': bc_items,
                'selling_point': bc.get('selling_point') or bc.get('主图一卖点提炼') or '',
                'discount': bc.get('discount') or bc.get('折扣') or '',
                'source': 'brand_brief',
                'role': '品牌主推',
                'contains': contains,
            }
            clean_cards.append(clean_card)

        # Replace product_mix with ALL brand cards (no extra cards)
        asset['product_mix'] = clean_cards
        with open('/tmp/patch_debug.log', 'a') as _dbg:
            _dbg.write(f"BRAND_CLEANUP_BUILT clean_cards={len(clean_cards)} names={all_brand_names}\n")

        # Update card_structure: when brand cards are uploaded, wipe ALL
        # self-generated cards so the LLM's own 组卡 never leaks through.
        cs = asset.get('card_structure')
        if isinstance(cs, dict):
            cs['brand_cards'] = clean_cards
            cs.pop('items', None)
            cs.pop('brand_card', None)
            # Replace any LLM-self-generated cards with the real brand cards
            cs['cards'] = clean_cards
            # Rewrite summary to drop "新组卡 / 按组卡规则新组" wording
            brand_label = '、'.join(all_brand_names) if all_brand_names else '品牌指定卡'
            cs['summary'] = (
                f'本次货盘完全使用品牌上传的成品卡（{brand_label}），'
                f'共 {len(clean_cards)} 张，不另行组卡。'
                f'所有销售内容、朋友圈、1v1 话术均围绕这些品牌成品卡展开。'
            )
            # Replace self-组卡 rules with brand-card usage note
            cs['rules'] = '使用品牌上传的成品卡，按原价/活动价直接售卖，不重新组卡、不检查破价。'
        else:
            asset['card_structure'] = {
                'brand_cards': clean_cards,
                'cards': clean_cards,
                'summary': (
                    f'本次货盘完全使用品牌上传的成品卡（'
                    f'{"、".join(all_brand_names) if all_brand_names else "品牌指定卡"}），'
                    f'共 {len(clean_cards)} 张，不另行组卡。'
                ),
                'rules': '使用品牌上传的成品卡，按原价/活动价直接售卖，不重新组卡、不检查破价。',
            }

        # Update activity_plan to reference brand cards
        ap = asset.get('activity_plan')
        if isinstance(ap, dict):
            ap_types = ap.get('types', [])
            if isinstance(ap_types, list):
                for t in ap_types:
                    if isinstance(t, dict):
                        if not t.get('products'):
                            t['products'] = all_brand_names

        # Update sales_playbook to reference brand cards
        sp = asset.get('sales_playbook')
        if isinstance(sp, dict):
            sp_sections = sp.get('sections', [])
            if isinstance(sp_sections, list):
                for sec in sp_sections:
                    if isinstance(sec, dict) and not sec.get('products'):
                        sec['products'] = all_brand_names
            sp_obj = sp.get('objections', [])
            if isinstance(sp_obj, list):
                for obj in sp_obj:
                    if isinstance(obj, dict):
                        resp = obj.get('response', '')
                        if resp and not any(bn in resp for bn in all_brand_names):
                            obj['response'] = resp + f'\n（推荐：{", ".join(all_brand_names[:2])}）'

        # Update content_schedule to reference brand cards in daily_content
        csc = asset.get('content_schedule')
        if isinstance(csc, dict):
            daily = csc.get('daily_content', [])
            if isinstance(daily, list):
                for dc in daily:
                    if isinstance(dc, dict):
                        content = dc.get('content', '')
                        if content and not any(bn in content for bn in all_brand_names):
                            dc['content'] = content

        # Update DB: write cleaned asset to BOTH strategy_task and instruction
        task_id = result.get('task_id')
        with open('/tmp/patch_debug.log', 'a') as _dbg:
            _dbg.write(f"BRAND_CLEANUP_PERSIST task_id={task_id} pm_cards={len(asset.get('product_mix', [])) if isinstance(asset.get('product_mix'), list) else 'N/A'}\n")
        if task_id:
            task = runtime.db.query(_orig.StrategyTask).filter(
                _orig.StrategyTask.id == task_id
            ).first()
            if task:
                # result_json is a JSON column: assign dict directly, NOT json.dumps (causes double-encoding)
                task.result_json = result
                runtime.db.commit()

        # Also persist cleaned asset back to instruction.asset_json — this is
        # what the frontend detail view actually reads from.
        if instr3:
            try:
                instr3.asset_json = asset
                runtime.db.commit()
                with open('/tmp/patch_debug.log', 'a') as _dbg:
                    _dbg.write(f"BRAND_CLEANUP_DONE persisted to instruction\n")
            except Exception:
                import traceback as _tb2
                with open('/tmp/patch_debug.log', 'a') as _dbg:
                    _dbg.write(f"BRAND_CLEANUP_PERSIST_ERR: {_tb2.format_exc()}\n")
                pass

        result['asset'] = asset

        # --- POLLING RE-APPLY: the original bytecode (platform_orig.pyc)
        # overwrites instruction.asset_json AFTER this function returns.
        # Poll the DB every 2s for up to 30s; each time the asset has been
        # overwritten back to self-generated cards, re-apply the clean version.
        import threading as _threading_mod
        _poll_asset = json.loads(json.dumps(asset, ensure_ascii=False))
        _poll_result = json.loads(json.dumps(result, ensure_ascii=False))
        _poll_task_id = task_id
        _poll_brand_names = list(all_brand_names)
        def _polling_brand_overwrite():
            import time as _time_mod
            import sqlite3 as _sqlite3
            import json as _pjson
            _db_path = 'pdp.db'
            try:
                _db_path = str(runtime.db.bind.engine.url.database)
                if not _db_path or _db_path == 'None':
                    _db_path = 'pdp.db'
            except Exception:
                pass
            _clean_asset_str = _pjson.dumps(_poll_asset, ensure_ascii=False)
            _clean_result_str = _pjson.dumps(_poll_result, ensure_ascii=False)
            for _attempt in range(15):
                _time_mod.sleep(2)
                try:
                    _conn = _sqlite3.connect(_db_path)
                    _row = _conn.execute(
                        "SELECT asset_json FROM instructions WHERE id = ?",
                        (instruction_id,)
                    ).fetchone()
                    if _row and _row[0]:
                        _cur = _pjson.loads(_row[0])
                        _pm = _cur.get('product_mix', [])
                        _needs_fix = False
                        if isinstance(_pm, list):
                            if len(_pm) != len(_poll_brand_names):
                                _needs_fix = True
                            else:
                                for _card in _pm:
                                    if isinstance(_card, dict):
                                        _cn = _card.get('name', '') or _card.get('card_name', '')
                                        if _cn not in _poll_brand_names:
                                            _needs_fix = True
                                            break
                        if _needs_fix:
                            _conn.execute(
                                "UPDATE instructions SET asset_json = ? WHERE id = ?",
                                (_clean_asset_str, instruction_id)
                            )
                            if _poll_task_id:
                                _conn.execute(
                                    "UPDATE strategy_tasks SET result_json = ? WHERE id = ?",
                                    (_clean_result_str, _poll_task_id)
                                )
                            _conn.commit()
                            with open('/tmp/patch_debug.log', 'a') as _dbg:
                                _dbg.write(f"BRAND_POLL_FIX attempt={_attempt+1} instr={instruction_id} fixed\n")
                        else:
                            _conn.close()
                            with open('/tmp/patch_debug.log', 'a') as _dbg:
                                _dbg.write(f"BRAND_POLL_OK attempt={_attempt+1} instr={instruction_id} stable\n")
                            break
                    _conn.close()
                except Exception as _de:
                    import traceback as _dtb
                    with open('/tmp/patch_debug.log', 'a') as _dbg:
                        _dbg.write(f"BRAND_POLL_ERR attempt={_attempt+1}: {_de}\n{_dtb.format_exc()}\n")
            else:
                with open('/tmp/patch_debug.log', 'a') as _dbg:
                    _dbg.write(f"BRAND_POLL_TIMEOUT instr={instruction_id} gave up\n")
        _threading_mod.Thread(target=_polling_brand_overwrite, daemon=True).start()

    except Exception as e:
        import traceback
        with open('/tmp/patch_debug.log', 'a') as f:
            f.write(f"POST-GEN CLEANUP ERROR: {e}\n{traceback.format_exc()}\n")

    return result


_orig._generate_instruction_impl = _patched_generate_instruction_impl


# ---------------------------------------------------------------------------
# Hybrid LLM routing: steps 3/4/5 use complexity='lite' (qwen3.7-max, fast)
# Steps 1+2 keep complexity='complex' (glm-5.2, reasoning) for quality
# ---------------------------------------------------------------------------
def _make_lite_wrapper(orig_fn):
    """Wrap an LLM gen function so its router.complete calls use complexity='lite'."""
    def wrapper(*args, **kwargs):
        llm_router = args[1] if len(args) > 1 else kwargs.get('llm_router')
        if llm_router is None:
            return orig_fn(*args, **kwargs)
        orig_complete = llm_router.complete

        def lite_complete(*a, **kw):
            if 'complexity' in kw:
                kw['complexity'] = 'lite'
            elif len(a) >= 4:
                a = list(a)
                a[3] = 'lite'
                a = tuple(a)
            else:
                kw['complexity'] = 'lite'
            return orig_complete(*a, **kw)

        llm_router.complete = lite_complete
        try:
            return orig_fn(*args, **kwargs)
        finally:
            llm_router.complete = orig_complete
    return wrapper


_orig._llm_generate_activity_focused = _make_lite_wrapper(_orig._llm_generate_activity_focused)
_orig._llm_generate_scripts_focused = _make_lite_wrapper(_orig._llm_generate_scripts_focused)
_orig._llm_generate_daily_content = _make_lite_wrapper(_orig._llm_generate_daily_content)


# ---------------------------------------------------------------------------
# Remove old chat_instruction route, register patched version
# ---------------------------------------------------------------------------
_CHAT_PATHS = {"/instructions/chat", "/api/v1/platform/instructions/chat"}
router.routes = [
    r for r in router.routes
    if not (
        hasattr(r, "path")
        and r.path in _CHAT_PATHS
        and hasattr(r, "methods")
        and "POST" in r.methods
    )
]

from fastapi import Depends
from fastapi import HTTPException
from app.auth import require_roles
from app.api.deps import Runtime, get_runtime
from app.models import Instruction


def chat_instruction(
    payload: ChatInstructionIn,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
):
    """Create instruction directly, parse keywords from natural language."""
    import re as _re

    msg = payload.message.strip()
    params: dict = {}

    m = _re.search(r'预算[：:\s]*([0-9.]+\s*[万千百元万]*)', msg)
    if m:
        params["budget"] = m.group(1).strip()

    m = _re.search(r'(GMV|gmv|销售额|订单量|转化率|复购率|拉新)[^0-9]*(增长|提升|达到|目标)?\s*([0-9.]+\s*%?)', msg)
    if m:
        params["goal_type"] = m.group(1)
        params["goal_value"] = f"{m.group(1)} {'增长' if '增长' in (m.group(2) or '') else '目标'} {m.group(3)}".strip()
        params["kpi_metrics"] = m.group(1)

    m = _re.search(r'针对([^，。\s]+(?:客户|人群|用户|客))', msg)
    if m:
        params["layers"] = m.group(1).strip()

    activity_kw = []
    for kw in ["秒杀", "裂变", "会员日", "直播", "节庆", "体验", "补水发", "充值", "拼团", "打卡", "抽奖"]:
        if kw in msg:
            activity_kw.append(kw)
    m = _re.search(r'策划([^，。]+活动)', msg)
    if m:
        activity_kw.insert(0, m.group(1).strip())
    if activity_kw:
        params["activity_type"] = "、".join(activity_kw)

    _channels = []
    for ch in ["朋友圈", "社群", "1v1", "一对一", "公众号", "短视频", "直播", "短信"]:
        if ch in msg:
            _channels.append("1v1" if ch == "一对一" else ch)
    if _channels:
        params["content_channels"] = "、".join(_channels)

    m = _re.search(r'(每天|每周|每月|每日|每\d+天)\s*[0-9]*\s*条', msg)
    if m:
        params["frequency"] = m.group(0)

    params["automation_mode"] = "全自动" if "全自动" in msg else "半自动"

    title = msg
    for prefix in ["帮我策划", "帮我做", "帮我设计", "策划", "设计", "做一个", "来一个"]:
        if title.startswith(prefix):
            title = title[len(prefix):]
            break
    title = title[:20].replace("，", "·").replace("。", "").strip()
    if not title:
        title = msg[:20]

    summary_parts = []
    label_map = {"goal_value": "目标", "layers": "人群", "activity_type": "活动", "budget": "预算", "content_channels": "渠道", "frequency": "频率"}
    for key, label in label_map.items():
        val = params.get(key)
        if val:
            summary_parts.append(f"{label}: {val}")
    summary = "、".join(summary_parts) if summary_parts else "已按默认参数创建"

    raw_cb = getattr(payload, "campaign_brief", None)
    cb = _normalize_campaign_brief(raw_cb) if raw_cb else None

    # --- 3.0 Interactive: pre-generation clarification ---
    _has_audience = bool(params.get("layers")) or any(
        kw in msg for kw in [
            "新客", "老客", "会员", "潜客", "体验客", "复购", "干皮",
            "敏感肌", "油皮", "干性", "混合", "高潜", "沉睡", "新粉",
        ]
    )
    _has_budget = bool(params.get("budget")) or bool(params.get("goal_value"))
    _has_activity = bool(params.get("activity_type")) or bool(
        cb and isinstance(cb, dict) and cb.get("cards")
    )
    _has_channels = bool(params.get("content_channels"))
    _has_timeframe = any(
        kw in msg for kw in [
            "本周", "本月", "下周", "周", "月", "季", "秋", "春", "夏", "冬",
            "8月", "9月", "10月", "11月", "12月", "1月", "2月", "3月", "4月",
            "5月", "6月", "7月", "即将", "马上",
        ]
    )

    _missing_dims = []
    if not _has_audience:
        _missing_dims.append({
            "dimension": "audience",
            "question": "这次运营针对哪类客户？",
            "examples": ["新客拉新", "老客复购", "会员激活", "体验客转化"],
        })
    if not _has_budget:
        _missing_dims.append({
            "dimension": "budget",
            "question": "预算或目标是什么？",
            "examples": ["预算5000元", "GMV增长20%", "转化率15%"],
        })
    if not _has_activity:
        _missing_dims.append({
            "dimension": "activity",
            "question": "主推什么产品或活动方向？",
            "examples": ["推广XX卡项", "秋季补水活动", "秒杀裂变"],
        })
    if not _has_channels:
        _missing_dims.append({
            "dimension": "channels",
            "question": "主要通过哪些渠道触达？",
            "examples": ["朋友圈+1v1", "社群+公众号", "全渠道"],
        })
    if not _has_timeframe:
        _missing_dims.append({
            "dimension": "timeframe",
            "question": "执行周期是什么时候？",
            "examples": ["本周", "本月", "秋季9月"],
        })

    if len(_missing_dims) >= 2:
        return {
            "needs_clarification": True,
            "title": title,
            "questions": _missing_dims[:3],
            "parsed_params": params,
        }

    instruction = Instruction(
        tenant_id=runtime.tenant_id,
        industry_id=runtime.industry_id,
        title=title,
        content=msg,
        params_json=params,
        campaign_brief_json=cb,
        status="待处理",
    )
    runtime.db.add(instruction)
    runtime.db.commit()
    runtime.db.refresh(instruction)
    _log_run(runtime.db, runtime.tenant_id, "instruction", "created",
              instruction_id=instruction.id, detail=f"指令: {title}",
              operator=_auth.get("user", "运营"))
    return {
        "instruction_id": instruction.id,
        "title": title,
        "content": msg,
        "params": params,
        "summary": summary,
        "status": instruction.status,
    }


router.add_api_route(
    "/instructions/chat",
    chat_instruction,
    methods=["POST"],
    response_model=None,
)


# ---------------------------------------------------------------------------
# Safe JSON parse helper — handles str (incl. double-encoded), None, dict
# ---------------------------------------------------------------------------
def _safe_parse_json(val):
    """Parse val to dict/list, handling double-encoded strings."""
    if val is None:
        return {}
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        try:
            p = json.loads(val)
            # Handle double-encoding (JSON column got a json.dumps'd string)
            if isinstance(p, str):
                p = json.loads(p)
            return p if isinstance(p, (dict, list)) else {}
        except Exception:
            return {}
    return {}


# ---------------------------------------------------------------------------
# Monkey-patch list_instructions: safely parse result_json before .get()
# ---------------------------------------------------------------------------
_LIST_PATHS = {"/instructions"}
router.routes = [
    r for r in router.routes
    if not (
        hasattr(r, "path")
        and r.path in _LIST_PATHS
        and hasattr(r, "methods")
        and "GET" in r.methods
    )
]


def list_instruction_safe(
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
):
    """List instructions with safe result_json parsing (handles double-encoding)."""
    rows = runtime.db.query(Instruction).filter(
        Instruction.tenant_id == runtime.tenant_id
    ).filter(
        Instruction.industry_id == runtime.industry_id
    ).order_by(
        Instruction.created_at.desc()
    ).limit(100).all()

    instruction_ids = [row.id for row in rows]

    tasks = []
    if instruction_ids:
        tasks = runtime.db.query(_orig.StrategyTask).filter(
            _orig.StrategyTask.instruction_id.in_(instruction_ids)
        ).order_by(
            _orig.StrategyTask.created_at.asc()
        ).all()

    tasks_by_instruction = {}
    for task in tasks:
        rj = _safe_parse_json(task.result_json)
        tasks_by_instruction.setdefault(task.instruction_id or "", []).append({
            "id": task.id,
            "title": task.title,
            "channel": task.channel,
            "status": task.status,
            "due_at": task.due_at,
            "message_id": rj.get("message_id") if isinstance(rj, dict) else None,
            "todo": bool(rj.get("todo")) if isinstance(rj, dict) else False,
        })

    result = []
    for row in rows:
        result.append({
            "id": row.id,
            "title": row.title,
            "content": row.content,
            "status": row.status,
            "industry_id": row.industry_id,
            "created_by": row.created_by,
            "strategy_ids": row.strategy_ids_json,
            "asset": row.asset_json,
            "params": row.params_json,
            "tasks": tasks_by_instruction.get(row.id, []),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        })
    return result


router.add_api_route(
    "/instructions",
    list_instruction_safe,
    methods=["GET"],
    response_model=None,
)


# ---------------------------------------------------------------------------
# 3.0 P1: Interactive revision — operator reviews asset, sends feedback, LLM revises
# ---------------------------------------------------------------------------
from pydantic import BaseModel as _BM


class ReviseInstructionIn(_BM):
    message: str


def _log_run(db, tenant_id: str, module: str, event: str,
             instruction_id: str | None = None, detail: str = "",
             operator: str = "系统", extra: dict | None = None):
    """Write a system_runlog row for audit trail / strategy iteration."""
    try:
        from app.models import SystemRunlog
        log = SystemRunlog(
            tenant_id=tenant_id,
            instruction_id=instruction_id,
            module=module,
            event=event,
            detail=detail,
            operator=operator,
            extra_json=extra,
            name=f"{module}.{event}",
        )
        db.add(log)
        db.commit()
    except Exception:
        db.rollback()


def revise_instruction(
    instruction_id: str,
    payload: ReviseInstructionIn,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
):
    """Revise an existing asset package based on operator feedback.

    Flow: operator reviews asset -> sends modification note -> LLM revises
    the relevant sections -> updated asset replaces the old one.  The
    conversation context (original instruction + feedback) is preserved.
    """
    import json as _json

    instr = runtime.db.query(Instruction).filter(
        Instruction.id == instruction_id,
        Instruction.tenant_id == runtime.tenant_id,
    ).first()
    if not instr:
        raise HTTPException(status_code=404, detail="指令不存在")

    current_asset = instr.asset_json
    if not current_asset:
        raise HTTPException(status_code=400, detail="资产包尚未生成，无法修改")

    asset_str = _json.dumps(current_asset, ensure_ascii=False, indent=2) if isinstance(current_asset, dict) else str(current_asset)
    feedback = payload.message.strip()

    sys_prompt = (
        "你是消费者运营策略修订专家。运营人员审阅了已生成的策略资产包，提出修改意见。\n"
        "请根据修改意见，对资产包做增量调整，保持未提及部分不变。\n"
        "输出要求：返回完整的 JSON 资产包，结构与输入完全一致，不要输出任何解释文字。\n"
        "字段说明：activity_plan(活动策划), card_structure(货盘卡项), "
        "sales_playbook(销售话术), script_templates(话术模板), "
        "content_schedule(内容排期), content_materials(内容素材), "
        "activity_details(活动详情), audience(目标人群), kpi_targets(KPI), constraints(约束)。"
    )
    user_msg = (
        f"【原始指令】{instr.content}\n\n"
        f"【当前资产包 JSON】\n{asset_str}\n\n"
        f"【运营修改意见】{feedback}\n\n"
        "请输出修订后的完整 JSON 资产包，保持结构一致。"
    )

    try:
        result = runtime.llm_router.complete(
            tenant_id=runtime.tenant_id,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_msg},
            ],
            complexity="complex",
            max_tokens=4096,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        _log_run(runtime.db, runtime.tenant_id, "instruction", "revise_failed",
                  instruction_id=instruction_id, detail=str(exc),
                  operator=_auth.get("user", "运营"))
        raise HTTPException(status_code=502, detail=f"LLM 修订失败: {exc}")

    raw = result.content.strip()
    # Strip code fences if present
    if raw.startswith("```"):
        lines = raw.split("\n", 1)
        raw = lines[1] if len(lines) > 1 else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3].strip()

    try:
        revised = _json.loads(raw)
    except _json.JSONDecodeError:
        # Try to extract JSON block
        import re as _re2
        m = _re2.search(r'\{[\s\S]*\}', raw)
        if m:
            revised = _json.loads(m.group())
        else:
            _log_run(runtime.db, runtime.tenant_id, "instruction", "revise_parse_failed",
                      instruction_id=instruction_id, detail="LLM output not valid JSON",
                      operator=_auth.get("user", "运营"))
            raise HTTPException(status_code=502, detail="LLM 返回格式异常，无法解析为 JSON")

    instr.asset_json = revised
    instr.status = "已产出"  # keep at "已产出" so operator can re-approve
    runtime.db.commit()

    _log_run(runtime.db, runtime.tenant_id, "instruction", "revised",
              instruction_id=instruction_id, detail=f"修改意见: {feedback[:200]}",
              operator=_auth.get("user", "运营"),
              extra={"feedback": feedback})

    return {
        "instruction_id": instruction_id,
        "status": instr.status,
        "asset": revised,
        "revision_note": "资产包已根据修改意见更新，请重新审阅后批准或继续修改",
    }


router.add_api_route(
    "/instructions/{instruction_id}/revise",
    revise_instruction,
    methods=["POST"],
    response_model=None,
)


# ---------------------------------------------------------------------------
# 3.0 P3: System runlog endpoints
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 3.0+: Wrap approve endpoint to add runlog logging
# ---------------------------------------------------------------------------
_APPROVE_PATHS = set()
for _r in list(router.routes):
    _p = getattr(_r, "path", "")
    if "approve" in _p and hasattr(_r, "methods") and "POST" in _r.methods:
        _APPROVE_PATHS.add(_p)
        _orig_approve = _r.endpoint
        break

if _APPROVE_PATHS:
    router.routes = [
        r for r in router.routes
        if not (hasattr(r, "path") and r.path in _APPROVE_PATHS
                and hasattr(r, "methods") and "POST" in r.methods)
    ]

    def _wrapped_approve(
        instruction_id: str,
        runtime: Runtime = Depends(get_runtime),
        _auth: dict = Depends(require_roles("admin", "operator")),
    ):
        """Approve instruction, decompose into tasks, materialize plan todos, log."""
        result = _orig_approve(instruction_id, runtime, _auth)
        _log_run(
            runtime.db,
            runtime.tenant_id,
            "instruction",
            "approved",
            instruction_id=instruction_id,
            detail=f"批准: {result.get('status', '')}, tasks={result.get('tasks', 0)}, todos={result.get('todo_count', 0)}",
            operator=_auth.get("user", "运营"),
        )
        # Ensure plan todos are materialized
        try:
            from app.orchestration.executor import materialize_plan_todos
            instr = runtime.db.query(Instruction).filter(
                Instruction.id == instruction_id
            ).first()
            if instr and instr.status == "已批准":
                todo_count = materialize_plan_todos(runtime.db, instr)
                if todo_count:
                    result["todo_count"] = todo_count
        except Exception:
            pass
        return result

    for _p in _APPROVE_PATHS:
        if "/api/v1" in _p:
            _reg_path = _p.replace("/api/v1/platform", "")
        else:
            _reg_path = _p
        router.add_api_route(
            _reg_path,
            _wrapped_approve,
            methods=["POST"],
            response_model=None,
        )

def list_runlogs(
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator", "viewer")),
    module: str | None = None,
    instruction_id: str | None = None,
    limit: int = 200,
):
    """List system run logs, filterable by module / instruction / time."""
    from app.models import SystemRunlog
    q = runtime.db.query(SystemRunlog).filter(
        SystemRunlog.tenant_id == runtime.tenant_id
    )
    if module:
        q = q.filter(SystemRunlog.module == module)
    if instruction_id:
        q = q.filter(SystemRunlog.instruction_id == instruction_id)
    rows = q.order_by(SystemRunlog.created_at.desc()).limit(min(limit, 500)).all()
    return [{
        "id": r.id,
        "instruction_id": r.instruction_id,
        "module": r.module,
        "event": r.event,
        "detail": r.detail,
        "operator": r.operator,
        "extra": r.extra_json,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in rows]


router.add_api_route(
    "/runlogs",
    list_runlogs,
     methods=["GET"],
     response_model=None,
)


# ---------------------------------------------------------------------------
# 3.0: Send execution task directly to Feishu group
# ---------------------------------------------------------------------------

def send_todo_to_feishu(
    todo_id: str,
    runtime: "Runtime" = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
):
    """Send a single execution task's content to the tenant's Feishu group."""
    from app.integrations.feishu import get_feishu_client
    from app.models import StrategyTask, Tenant, Instruction

    task = runtime.db.query(StrategyTask).filter(
        StrategyTask.id == todo_id,
        StrategyTask.tenant_id == runtime.tenant_id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # --- Fetch brand name and instruction title for context ---
    brand_name = ""
    instr_title = ""
    if task.tenant_id:
        _tenant = runtime.db.query(Tenant).filter(Tenant.id == task.tenant_id).first()
        if _tenant:
            brand_name = _tenant.name or ""
    if task.instruction_id:
        _instr = runtime.db.query(Instruction).filter(Instruction.id == task.instruction_id).first()
        if _instr:
            instr_title = _instr.title or ""

    # --- Channel to color/icon mapping ---
    ch_raw = (task.channel or "通用").strip()
    _CH_META = {
        "朋友圈": {"color": "green", "icon": "📸"},
        "社群": {"color": "purple", "icon": "💬"},
        "1v1": {"color": "blue", "icon": "🎯"},
        "私聊": {"color": "blue", "icon": "🎯"},
        "货盘": {"color": "orange", "icon": "🛒"},
        "卡项": {"color": "orange", "icon": "🛒"},
        "活动": {"color": "violet", "icon": "🎉"},
        "公众号": {"color": "turquoise", "icon": "📰"},
        "短信": {"color": "grey", "icon": "✉️"},
        "通用": {"color": "blue", "icon": "📋"},
    }
    _cm = _CH_META.get(ch_raw, _CH_META.get(ch_raw.lower(), _CH_META["通用"]))
    ch_display = f"{_cm['icon']} {ch_raw}"
    header_color = _cm["color"]

    # --- Priority indicator based on due_at ---
    priority_label = ""
    if task.due_at:
        try:
            from datetime import datetime, date as _date
            _ds = str(task.due_at).strip()[:19]
            _dd = None
            for _fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M", "%Y年%m月%d日"):
                try:
                    _dd = datetime.strptime(_ds[:len(_fmt)], _fmt).date()
                    break
                except ValueError:
                    continue
            if _dd:
                _days = (_dd - _date.today()).days
                if _days < 0:
                    priority_label = "🔴 已逾期"
                elif _days == 0:
                    priority_label = "🟡 今日截止"
                elif _days <= 2:
                    priority_label = f"🟠 紧急（{_days}天内）"
                else:
                    priority_label = "🟢 常规"
        except Exception:
            pass

    # --- Header title: brand · instruction · channel ---
    _hp = []
    if brand_name:
        _hp.append(brand_name)
    if instr_title:
        _hp.append(instr_title if len(instr_title) <= 20 else instr_title[:18] + "...")
    _hp.append(ch_raw)
    header_title = " · ".join(_hp) if _hp else "策略任务"

    # --- Parse script into structured sections ---
    def _parse_sections(text):
        if not text:
            return []
        text = text.strip()
        import re
        _pat = re.compile(r'^(?:【([^】]+)】|([^\n:：]{2,12})[：:])\s*\n?', re.MULTILINE)
        sections = []
        last_end = 0
        last_hdr = None
        for m in _pat.finditer(text):
            if m.start() > last_end and last_hdr is not None:
                _c = text[last_end:m.start()].strip()
                if _c:
                    sections.append({"header": last_hdr, "content": _c})
            last_hdr = (m.group(1) or m.group(2)).strip()
            last_end = m.end()
        if last_hdr is not None and last_end < len(text):
            _r = text[last_end:].strip()
            if _r:
                sections.append({"header": last_hdr, "content": _r})
        if not sections:
            return [{"header": "", "content": text}]
        return sections

    # --- Build card elements ---
    elements = []

    # Info bar: channel / audience / due / priority
    fields = []
    fields.append({"is_short": True, "text": {"tag": "lark_md", "content": f"**渠道**\n{ch_display}"}})
    if task.audience:
        fields.append({"is_short": True, "text": {"tag": "lark_md", "content": f"**🎯 目标人群**\n{task.audience}"}})
    if task.due_at:
        fields.append({"is_short": True, "text": {"tag": "lark_md", "content": f"**⏰ 截止**\n{task.due_at}"}})
    if priority_label:
        fields.append({"is_short": True, "text": {"tag": "lark_md", "content": f"**优先级**\n{priority_label}"}})
    if fields:
        elements.append({"tag": "div", "fields": fields})

    # Task title as subtitle
    if task.title and task.title != ch_raw:
        elements.append({"tag": "hr"})
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**📋 任务** {task.title}"}})

    # Divider before main content
    elements.append({"tag": "hr"})

    # Main content: parse script into labeled sections
    if task.script:
        script_text = str(task.script)
        _secs = _parse_sections(script_text)
        _total = 0
        _MAX = 3500
        for _i, _s in enumerate(_secs):
            _sc = _s["content"]
            if _total + len(_sc) > _MAX:
                _rem = _MAX - _total
                if _rem > 50:
                    _sc = _sc[:_rem] + "…"
                else:
                    break
            _total += len(_sc)
            if _s["header"]:
                elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**{_s['header']}**"}})
                elements.append({"tag": "div", "text": {"tag": "lark_md", "content": _sc}})
                if _i < len(_secs) - 1:
                    elements.append({"tag": "hr"})
            else:
                elements.append({"tag": "div", "text": {"tag": "lark_md", "content": _sc}})

    # Acceptance criteria
    if task.acceptance:
        elements.append({"tag": "hr"})
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**✅ 验收标准**\n{task.acceptance}"}})

    # Instruction source context at the bottom
    if instr_title or brand_name:
        elements.append({"tag": "hr"})
        _src = "📌 "
        if brand_name:
            _src += f"品牌：{brand_name}"
        if instr_title:
            _src += f" ｜ 指令：{instr_title}"
        elements.append({"tag": "note", "elements": [{"tag": "plain_text", "content": _src[:200]}]})
    else:
        elements.append({"tag": "hr"})
        elements.append({"tag": "note", "elements": [{"tag": "plain_text", "content": "由消费者运营中台自动下发"}]})

    client = get_feishu_client(runtime.tenant_id)
    if client.mock:
        result = {"ok": False, "detail": "飞书未配置或未开启消息发送，请先在飞书配置页面填写信息并开启"}
        return {"ok": False, "task_id": todo_id, "send_result": result, "mock": True}

    try:
        result = client.send_card(header_title, elements, header_template=header_color)
    except Exception as exc:
        _log_run(runtime.db, runtime.tenant_id, "feishu", "send_failed",
                  instruction_id=task.instruction_id,
                  detail=f"任务 {todo_id} 发送飞书失败: {exc}",
                  operator=_auth.get("user", "运营"))
        raise HTTPException(status_code=502, detail=f"飞书发送失败: {exc}")

    if result.get("ok"):
        task.status = "已下发"
        task.external_ref = result.get("message_id", "")
        runtime.db.commit()
        _log_run(runtime.db, runtime.tenant_id, "feishu", "task_dispatched",
                  instruction_id=task.instruction_id,
                  detail=f"任务 {todo_id} 已下发到飞书群",
                  operator=_auth.get("user", "运营"))

    return {
        "ok": result.get("ok", False),
        "task_id": todo_id,
        "task_title": task.title,
        "status": task.status,
        "send_result": result,
    }


router.add_api_route(
    "/execution/todos/{todo_id}/send-feishu",
    send_todo_to_feishu,
    methods=["POST"],
    response_model=None,
)




# ── 3.0: 运行日志读取接口 ──
def list_runlogs(
    module: str | None = None,
    instruction_id: str | None = None,
    limit: int = 200,
    runtime=Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator", "n")),
):
    """读取系统运行日志，支持按模块/指令过滤。"""
    from app.models import SystemRunlog
    q = (
        runtime.db.query(SystemRunlog)
        .filter(SystemRunlog.tenant_id == runtime.tenant_id)
    )
    if module:
        q = q.filter(SystemRunlog.module == module)
    if instruction_id:
        q = q.filter(SystemRunlog.instruction_id == instruction_id)
    rows = q.order_by(SystemRunlog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "instruction_id": r.instruction_id,
            "module": r.module,
            "event": r.event,
            "detail": r.detail,
            "operator": r.operator,
            "extra": r.extra_json,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


router.add_api_route(
    "/runlogs",
    list_runlogs,
    methods=["GET"],
    response_model=None,
)
