"""Polymarket Gamma API：预测市场概率（台海、伊朗、俄乌、美联储、IPO、加密法案等）。免费、无密钥。

config/watchlist.yaml 里的 polymarket 项：{key, label, slug?, query?, match?, outcome?}
- slug  : 事件 slug（精确）
- query : 用 /public-search 搜索，取 slug 含 match 的第一个事件
- outcome: 取哪个结果的概率（默认 Yes / 第一个）
"""
from __future__ import annotations

import json

from ..utils import Http, log

GAMMA = "https://gamma-api.polymarket.com"


def _prob_from_market(m: dict, outcome: str | None) -> float | None:
    try:
        outcomes = json.loads(m.get("outcomes") or "[]")
        prices = json.loads(m.get("outcomePrices") or "[]")
    except Exception:
        return None
    if not prices:
        return None
    if outcome and outcome in outcomes:
        return float(prices[outcomes.index(outcome)]) * 100
    return float(prices[0]) * 100


def _find_event(http: Http, item: dict) -> dict | None:
    if item.get("slug"):
        evs = http.get_json(f"{GAMMA}/events", params={"slug": item["slug"]})
        if evs:
            return evs[0]
    if item.get("query"):
        res = http.get_json(f"{GAMMA}/public-search", params={"q": item["query"], "limit_per_type": 10})
        evs = res.get("events", []) if isinstance(res, dict) else []
        match = (item.get("match") or "").lower()
        for e in evs:
            if e.get("closed"):
                continue
            if not match or match in (e.get("slug", "") + " " + e.get("title", "")).lower():
                return e
    return None


def fetch(cfg: dict, settings: dict) -> dict:
    http = Http(timeout=20, min_interval=0.5)
    metrics: list[dict] = []
    notes = []
    for item in cfg.get("polymarket", []):
        try:
            ev = _find_event(http, item)
            if not ev:
                notes.append(f"{item['key']}: not found")
                continue
            markets = ev.get("markets") or []
            # 多市场事件（如“何时…”）取指定 market_match 或成交量最大的
            mm = (item.get("market_match") or "").lower()
            cand = [m for m in markets if not m.get("closed")] or markets
            if mm:
                cand = [m for m in cand if mm in (m.get("question", "") + m.get("slug", "")).lower()] or cand
            if not cand:
                notes.append(f"{item['key']}: no markets")
                continue
            m = max(cand, key=lambda x: float(x.get("volumeNum") or x.get("volume") or 0))
            prob = _prob_from_market(m, item.get("outcome", "Yes"))
            metrics.append({"key": f"pm.{item['key']}", "value": prob, "source": "polymarket",
                            "asof": m.get("updatedAt") or ev.get("updatedAt"),
                            "meta": {"label": item.get("label"), "question": m.get("question"), "event": ev.get("title"),
                                     "slug": ev.get("slug"), "volume": float(ev.get("volume") or 0),
                                     "end": ev.get("endDate"), "url": f"https://polymarket.com/event/{ev.get('slug')}"}})
            # 概率历史（CLOB，日频）用于曲线
            try:
                outcomes = json.loads(m.get("outcomes") or "[]")
                tokens = json.loads(m.get("clobTokenIds") or "[]")
                idx = outcomes.index(item.get("outcome", "Yes")) if item.get("outcome", "Yes") in outcomes else 0
                if tokens:
                    h = http.get_json("https://clob.polymarket.com/prices-history",
                                      params={"market": tokens[idx], "interval": "max", "fidelity": 1440})
                    seen = set()
                    for p in (h.get("history") or [])[-400:]:
                        from datetime import datetime, timezone
                        date = datetime.fromtimestamp(int(p["t"]), tz=timezone.utc).strftime("%Y-%m-%d")
                        if date in seen:
                            continue
                        seen.add(date)
                        metrics.append({"key": f"pm.{item['key']}", "value": float(p["p"]) * 100, "source": "polymarket",
                                        "date": date, "_backfill": True})
            except Exception as e:
                log.debug("pm history %s: %s", item.get("key"), e)
        except Exception as e:
            notes.append(f"{item.get('key')}: {e}")
            log.warning("polymarket %s: %s", item.get("key"), e)
    return {"metrics": metrics, "news": [], "notes": "; ".join(notes)}
