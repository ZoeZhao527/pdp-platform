"""外部热点信号采集（从 Linkstrate-Z 迁移，改为 httpx 实现）。"""

from __future__ import annotations

from typing import Any

import httpx

COLLECTOR_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://weibo.com/",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def _http_get_json(url: str, timeout: float = 6) -> dict[str, Any]:
    with httpx.Client(headers=COLLECTOR_HEADERS, timeout=timeout) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json()


def fetch_weibo_hot() -> list[tuple[str, str, int, str]]:
    data = _http_get_json("https://weibo.com/ajax/statuses/hot_band")
    items = (data.get("data") or {}).get("band_list") or []
    rows: list[tuple[str, str, int, str]] = []
    for item in items[:30]:
        word = (item.get("word") or item.get("word_scheme") or "").strip()
        if not word:
            continue
        try:
            heat = int(str(item.get("num") or "0").replace(",", ""))
        except ValueError:
            heat = 0
        label = item.get("icon_desc") or item.get("label_name") or item.get("small_icon_desc") or ""
        trend = "上升" if label in ("沸", "爆", "热") else "稳定" if label else "实时"
        rows.append(("微博热搜", word, heat, trend))
    if not rows:
        raise RuntimeError("微博热搜为空")
    return rows


def fetch_baidu_hot() -> list[tuple[str, str, int, str]]:
    data = _http_get_json("https://top.baidu.com/api/board?platform=wise&tab=realtime")
    cards = (data.get("data") or {}).get("cards") or []
    block = cards[0]["content"][0] if cards else {}
    items = block.get("content") if isinstance(block, dict) else []
    rows: list[tuple[str, str, int, str]] = []
    for idx, item in enumerate(items[:30], 1):
        word = (item.get("word") or "").strip()
        if not word:
            continue
        try:
            heat = int(item.get("hotScore") or (100 - idx))
        except (TypeError, ValueError):
            heat = 100 - idx
        tag = str(item.get("hotTag") or "")
        trend = {"3": "上升", "2": "稳定", "1": "下降"}.get(tag, "实时")
        rows.append(("百度热搜", word, heat, trend))
    if not rows:
        raise RuntimeError("百度热搜为空")
    return rows


def fetch_bilibili_hot() -> list[tuple[str, str, int, str]]:
    data = _http_get_json("https://s.search.bilibili.com/main/hotword")
    items = data.get("list") or []
    rows: list[tuple[str, str, int, str]] = []
    for item in items[:30]:
        word = (item.get("keyword") or item.get("show_name") or "").strip()
        if not word:
            continue
        try:
            heat = int(item.get("heat_score") or item.get("pos") or item.get("heat") or 0)
        except (TypeError, ValueError):
            heat = 0
        rows.append(("B站热词", word, heat, "实时"))
    if not rows:
        raise RuntimeError("B站热词为空")
    return rows


def collect_all() -> tuple[list[tuple[str, str, str, int, str]], list[dict]]:
    """返回 (rows, results)，rows 为热点数据，results 记录每个来源的采集结果。"""
    rows: list[tuple[str, str, str, int, str]] = []
    results: list[dict] = []
    for source_key, platform, fetcher in (
        ("weibo", "微博热搜", fetch_weibo_hot),
        ("baidu", "百度热搜", fetch_baidu_hot),
        ("bilibili", "B站热词", fetch_bilibili_hot),
    ):
        try:
            batch = fetcher()
            for platform_name, keyword, heat, trend in batch:
                rows.append((source_key, platform_name, keyword, heat, trend))
            results.append({"source": platform, "ok": True, "count": len(batch)})
        except Exception as exc:  # noqa: BLE001
            results.append({"source": platform, "ok": False, "error": str(exc)[:120]})
    return rows, results
