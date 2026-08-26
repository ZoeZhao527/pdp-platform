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
_orig_generate_instruction_impl = _orig._generate_instruction_impl


def _patched_generate_instruction_impl(instruction_id, runtime):
    # --- PRE-GENERATION: inject care item context into instruction content ---
    instr = runtime.db.query(_orig.Instruction).filter(
        _orig.Instruction.id == instruction_id
    ).first()

    orig_content = None
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
            orig_content = instr.content
            instr.content = instr.content + full_injection
            runtime.db.commit()

    # --- CALL ORIGINAL GENERATION PIPELINE ---
    result = _orig_generate_instruction_impl(instruction_id, runtime)

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

    # --- POST-GENERATION: clean up product_mix ---
    try:
        if not isinstance(result, dict):
            return result
        asset = result.get('asset')
        if not isinstance(asset, dict):
            return result

        # Re-read instruction for campaign_brief
        instr3 = runtime.db.query(_orig.Instruction).filter(
            _orig.Instruction.id == instruction_id
        ).first()
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

        # Update DB: write cleaned asset to BOTH strategy_task and instruction
        task_id = result.get('task_id')
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
            except Exception:
                pass

        result['asset'] = asset

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
