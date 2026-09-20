"""DefiLlama：协议手续费/收入、TVL、链级费用（REV 代理）、稳定币供给、代币解锁。全部免费无需密钥。"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from ..utils import Http, log

BASE = "https://api.llama.fi"


def _ts2date(ts: int | float) -> str:
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")


def fetch_protocol_fees(http: Http, slug: str, sym: str, data_type: str = "dailyFees") -> list[dict]:
    d = http.get_json(f"{BASE}/summary/fees/{slug}", params={"dataType": data_type})
    prefix = "fees" if data_type == "dailyFees" else "rev"
    out = [
        {"key": f"{prefix}24h.{sym}", "value": d.get("total24h"), "source": "defillama"},
        {"key": f"{prefix}7d.{sym}", "value": d.get("total7d"), "source": "defillama"},
        {"key": f"{prefix}30d.{sym}", "value": d.get("total30d"), "source": "defillama"},
        {"key": f"{prefix}all.{sym}", "value": d.get("totalAllTime"), "source": "defillama"},
    ]
    chart = d.get("totalDataChart") or []
    # 回填日度序列（最近 400 天）与滚动 30 日和（供"季度环比"类规则）
    pts = [(int(ts), float(v)) for ts, v in chart[-400:] if v is not None]
    for ts, v in pts:
        out.append({"key": f"{prefix}daily.{sym}", "value": v, "source": "defillama", "date": _ts2date(ts), "_backfill": True})
    vals = [v for _, v in pts]
    for i in range(29, len(pts)):  # 含当日的 30 点滚动和，与 DefiLlama total30d 口径一致
        out.append({"key": f"{prefix}30d.{sym}", "value": sum(vals[i - 29:i + 1]), "source": "defillama",
                    "date": _ts2date(pts[i][0]), "_backfill": True})
    return out


def fetch_chain_fees(http: Http, chain: str) -> list[dict]:
    out = []
    for dt, prefix in (("dailyFees", "chainfees"), ("dailyRevenue", "chainrev")):
        try:
            d = http.get_json(f"{BASE}/overview/fees/{chain}", params={"dataType": dt, "excludeTotalDataChart": "false",
                                                                          "excludeTotalDataChartBreakdown": "true"})
            out += [
                {"key": f"{prefix}24h.{chain}", "value": d.get("total24h"), "source": "defillama"},
                {"key": f"{prefix}30d.{chain}", "value": d.get("total30d"), "source": "defillama"},
            ]
            chart = d.get("totalDataChart") or []
            pts = [(int(ts), float(v)) for ts, v in chart[-400:] if v is not None]
            vals = [v for _, v in pts]
            for i in range(29, len(pts)):
                out.append({"key": f"{prefix}30d.{chain}", "value": sum(vals[i - 29:i + 1]), "source": "defillama",
                            "date": _ts2date(pts[i][0]), "_backfill": True})
        except Exception as e:
            log.warning("chain fees %s %s: %s", chain, dt, e)
    return out


def fetch_tvl(http: Http, slug: str, sym: str) -> list[dict]:
    d = http.get_json(f"{BASE}/protocol/{slug}")
    out = []
    tvls = d.get("tvl") or []
    if tvls:
        for p in tvls[-400:]:
            out.append({"key": f"tvl.{sym}", "value": p.get("totalLiquidityUSD"), "source": "defillama",
                        "date": _ts2date(p["date"]), "_backfill": True})
        out.append({"key": f"tvl.{sym}", "value": tvls[-1].get("totalLiquidityUSD"), "source": "defillama"})
    return out


# DefiLlama 稳定币 id（同名 symbol 可能有多个，如 USDS=Sky Dollar(209) vs Sable Coin(149)）
STABLE_IDS = {"USDT": "1", "USDC": "2", "DAI": "5", "USDe": "146", "USDS": "209", "PYUSD": "120", "RLUSD": "250", "USDG": "286"}


def fetch_stablecoins(http: Http, wanted: dict[str, str]) -> list[dict]:
    """wanted: {DefiLlama symbol -> 我们的键}，另输出总量。优先按 id 匹配；无 id 映射时取同 symbol 中流通量最大者。"""
    d = http.get_json("https://stablecoins.llama.fi/stablecoins", params={"includePrices": "false"})
    total = 0.0
    out = []
    best: dict[str, tuple[float, dict]] = {}
    for a in d.get("peggedAssets", []):
        circ = (a.get("circulating") or {}).get("peggedUSD")
        if circ is None:
            continue
        circ = float(circ)
        total += circ
        sym = a.get("symbol")
        if sym not in wanted:
            continue
        want_id = STABLE_IDS.get(sym)
        if want_id:
            if str(a.get("id")) == want_id:
                best[sym] = (circ, a)
        elif sym not in best or circ > best[sym][0]:
            best[sym] = (circ, a)
    for sym, (circ, a) in best.items():
        out.append({"key": f"stable.{wanted[sym]}", "value": circ, "source": "defillama",
                    "meta": {"name": a.get("name"), "id": a.get("id")}})
    out.append({"key": "stable.total", "value": total, "source": "defillama"})
    # 总量历史（供 30/90 天变化规则）
    try:
        h = http.get_json("https://stablecoins.llama.fi/stablecoincharts/all")
        for p in h[-400:]:
            v = (p.get("totalCirculatingUSD") or {}).get("peggedUSD")
            if v is not None:
                out.append({"key": "stable.total", "value": float(v), "source": "defillama",
                            "date": _ts2date(p["date"]), "_backfill": True})
    except Exception as e:
        log.warning("stablecoincharts: %s", e)
    return out


def fetch_unlocks(http: Http, tokens: list[dict]) -> list[dict]:
    """tokens: [{slug, symbol}] ；返回未来 180 天内的解锁事件（存入 meta）。"""
    out = []
    now = time.time()
    for t in tokens:
        try:
            d = http.get_json(f"{BASE}/emission/{t['slug']}")
            body = d.get("body") if isinstance(d, dict) else None
            body = body or d
            events = []
            meta = body.get("metadata", {}) if isinstance(body, dict) else {}
            for ev in (meta.get("events") or body.get("events") or []):
                ts = ev.get("timestamp")
                if not ts:
                    continue
                if now - 86400 * 30 <= ts <= now + 86400 * 180:
                    events.append({"date": _ts2date(ts), "tokens": ev.get("noOfTokens"),
                                   "description": ev.get("description"), "category": ev.get("category"),
                                   "type": ev.get("unlockType")})
            upcoming = [e for e in events if e["date"] >= datetime.now(timezone.utc).strftime("%Y-%m-%d")]
            nxt = min(upcoming, key=lambda e: e["date"]) if upcoming else None
            out.append({"key": f"unlock.next_days.{t['symbol']}",
                        "value": (datetime.strptime(nxt["date"], "%Y-%m-%d") - datetime.utcnow()).days if nxt else None,
                        "source": "defillama", "meta": {"events": events[:20], "next": nxt}})
            time.sleep(0.5)
        except Exception as e:
            log.warning("unlock %s: %s", t.get("slug"), e)
    return out


def fetch(cfg: dict, settings: dict) -> dict:
    http = Http(timeout=30, min_interval=0.6)
    metrics: list[dict] = []
    notes = []
    dl = cfg.get("defillama", {})
    for p in dl.get("fees", []):
        try:
            metrics += fetch_protocol_fees(http, p["slug"], p["symbol"], "dailyFees")
            if p.get("revenue", True):
                metrics += fetch_protocol_fees(http, p["slug"], p["symbol"], "dailyRevenue")
        except Exception as e:
            notes.append(f"fees {p['slug']}: {e}")
            log.warning("fees %s: %s", p["slug"], e)
    for chain in dl.get("chains", ["solana", "ethereum"]):
        metrics += fetch_chain_fees(http, chain)
    for p in dl.get("tvl", []):
        try:
            metrics += fetch_tvl(http, p["slug"], p["symbol"])
        except Exception as e:
            notes.append(f"tvl {p['slug']}: {e}")
    try:
        metrics += fetch_stablecoins(http, dl.get("stablecoins", {"USDT": "USDT", "USDC": "USDC", "USDe": "USDe", "USDS": "USDS", "DAI": "DAI"}))
    except Exception as e:
        notes.append(f"stablecoins: {e}")
    # 解锁：emissions API 已收费（402），改由 extras.llama_unlocks 解析解锁页
    return {"metrics": metrics, "news": [], "notes": "; ".join(notes)}
