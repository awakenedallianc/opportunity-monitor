"""加密：CoinGecko（价格/市值/ATH）、Binance K 线（周/月均线）、Alternative.me 恐惧贪婪指数。"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from ..utils import Http, log, chunked

CG = "https://api.coingecko.com/api/v3"
# Binance 主站在美国 IP（GitHub Actions）会被拒绝，依次回退到公开镜像
BINANCE_BASES = ["https://api.binance.com", "https://data-api.binance.vision", "https://api1.binance.com"]


def _sym_map(cfg: dict) -> dict[str, str]:
    """coingecko id -> 我们的代号（如 GRAM/TON、CC）。"""
    return {c["id"]: c["symbol"] for c in cfg.get("crypto", []) if c.get("id")}


def fetch_coingecko(cfg: dict, http: Http) -> tuple[list[dict], dict]:
    ids = [c["id"] for c in cfg.get("crypto", []) if c.get("id")]
    symmap = _sym_map(cfg)
    metrics: list[dict] = []
    raw: dict = {}
    for batch in chunked(ids, 100):
        data = http.get_json(f"{CG}/coins/markets", params={
            "vs_currency": "usd", "ids": ",".join(batch), "per_page": 250, "page": 1,
            "sparkline": "false", "price_change_percentage": "24h,7d,30d,1y"})
        for c in data:
            sym = symmap.get(c["id"], c.get("symbol", "").upper())
            raw[sym] = c
            asof = c.get("last_updated")
            src = "coingecko"
            metrics += [
                {"key": f"px.{sym}", "value": c.get("current_price"), "source": src, "asof": asof,
                 "meta": {"name": c.get("name"), "rank": c.get("market_cap_rank"), "id": c["id"]}},
                {"key": f"mcap.{sym}", "value": c.get("market_cap"), "source": src, "asof": asof},
                {"key": f"fdv.{sym}", "value": c.get("fully_diluted_valuation"), "source": src, "asof": asof},
                {"key": f"vol24.{sym}", "value": c.get("total_volume"), "source": src, "asof": asof},
                {"key": f"ath.{sym}", "value": c.get("ath"), "source": src, "asof": c.get("ath_date"),
                 "meta": {"ath_date": c.get("ath_date")}},
                {"key": f"athdd.{sym}", "value": c.get("ath_change_percentage"), "source": src, "asof": asof},
                {"key": f"chg24h.{sym}", "value": c.get("price_change_percentage_24h_in_currency"), "source": src, "asof": asof},
                {"key": f"chg7d.{sym}", "value": c.get("price_change_percentage_7d_in_currency"), "source": src, "asof": asof},
                {"key": f"chg30d.{sym}", "value": c.get("price_change_percentage_30d_in_currency"), "source": src, "asof": asof},
                {"key": f"chg1y.{sym}", "value": c.get("price_change_percentage_1y_in_currency"), "source": src, "asof": asof},
                {"key": f"circ.{sym}", "value": c.get("circulating_supply"), "source": src, "asof": asof},
                {"key": f"supply_ratio.{sym}",
                 "value": (c["circulating_supply"] / c["total_supply"] * 100) if c.get("total_supply") and c.get("circulating_supply") else None,
                 "source": src, "asof": asof},
            ]
    # 全局
    g = http.get_json(f"{CG}/global").get("data", {})
    dom = g.get("market_cap_percentage", {})
    metrics += [
        {"key": "crypto.btc_dominance", "value": dom.get("btc"), "source": "coingecko"},
        {"key": "crypto.eth_dominance", "value": dom.get("eth"), "source": "coingecko"},
        {"key": "crypto.total_mcap", "value": g.get("total_market_cap", {}).get("usd"), "source": "coingecko"},
        {"key": "crypto.total_vol24", "value": g.get("total_volume", {}).get("usd"), "source": "coingecko"},
        {"key": "crypto.mcap_chg24h", "value": g.get("market_cap_change_percentage_24h_usd"), "source": "coingecko"},
    ]
    return metrics, raw


def _klines(http: Http, symbol: str, interval: str, limit: int) -> list[list]:
    last_err = None
    for base in BINANCE_BASES:
        try:
            r = http.get(f"{base}/api/v3/klines", params={"symbol": symbol, "interval": interval, "limit": limit})
            if r.status_code == 200:
                return r.json()
            last_err = f"{r.status_code}"
        except Exception as e:
            last_err = str(e)
    raise RuntimeError(f"binance klines {symbol} {interval} failed: {last_err}")


def fetch_binance_ma(cfg: dict, http: Http) -> tuple[list[dict], dict]:
    """周线/月线收盘与 50/200 周均线。已收盘 K 线 = 除最后一根之外。"""
    metrics: list[dict] = []
    series: dict = {}
    pairs = cfg.get("binance_pairs", [
        {"symbol": "BTCUSDT", "key": "btc"}, {"symbol": "ETHUSDT", "key": "eth"},
        {"symbol": "SOLUSDT", "key": "sol"}, {"symbol": "ETHBTC", "key": "ethbtc"}, {"symbol": "SOLBTC", "key": "solbtc"}])
    for p in pairs:
        sym, k = p["symbol"], p["key"]
        try:
            wk = _klines(http, sym, "1w", 260)
            closes = [float(x[4]) for x in wk]
            done = closes[:-1]  # 已完成的周
            if len(done) >= 50:
                metrics.append({"key": f"crypto.{k}.wma50", "value": sum(done[-50:]) / 50, "source": "binance"})
            if len(done) >= 200:
                metrics.append({"key": f"crypto.{k}.wma200", "value": sum(done[-200:]) / 200, "source": "binance"})
            if done:
                metrics.append({"key": f"crypto.{k}.weekly_close", "value": done[-1], "source": "binance",
                                "asof": datetime.fromtimestamp(wk[-2][6] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")})
            metrics.append({"key": f"crypto.{k}.week_high", "value": max(float(x[2]) for x in wk[-52:]), "source": "binance"})
            mo = _klines(http, sym, "1M", 24)
            mclose = [float(x[4]) for x in mo][:-1]
            if mclose:
                metrics.append({"key": f"crypto.{k}.monthly_close", "value": mclose[-1], "source": "binance",
                                "asof": datetime.fromtimestamp(mo[-2][6] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")})
            # 日线回填（最近 400 天）供曲线使用
            dk = _klines(http, sym, "1d", 400)
            series[k] = [(datetime.fromtimestamp(x[0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d"), float(x[4])) for x in dk]
            time.sleep(0.3)
        except Exception as e:
            log.warning("binance %s: %s", sym, e)
    return metrics, series


def fetch_fng(http: Http) -> list[dict]:
    d = http.get_json("https://api.alternative.me/fng/", params={"limit": 30})
    rows = d.get("data", [])
    out = []
    if rows:
        cur = rows[0]
        out.append({"key": "crypto.fng", "value": float(cur["value"]), "source": "alternative.me",
                    "meta": {"label": cur.get("value_classification")},
                    "asof": datetime.fromtimestamp(int(cur["timestamp"]), tz=timezone.utc).strftime("%Y-%m-%d")})
        # 历史回填
        for r in rows[1:]:
            out.append({"key": "crypto.fng", "value": float(r["value"]), "source": "alternative.me",
                        "date": datetime.fromtimestamp(int(r["timestamp"]), tz=timezone.utc).strftime("%Y-%m-%d")})
    return out


def fetch(cfg: dict, settings: dict) -> dict:
    http = Http(timeout=25, min_interval=1.5)
    metrics: list[dict] = []
    notes = []
    raw = {}
    cg_ok = False
    try:
        m, raw = fetch_coingecko(cfg, http)
        metrics += m
        cg_ok = True
    except Exception as e:
        notes.append(f"coingecko: {e}")
        log.warning("coingecko failed: %s", e)
    try:
        m, series = fetch_binance_ma(cfg, Http(timeout=20, min_interval=0.3))
        metrics += m
        # 把日线序列写成历史行（date 指定）
        keymap = {"btc": "px.BTC", "eth": "px.ETH", "sol": "px.SOL", "ethbtc": "crypto.ethbtc", "solbtc": "crypto.solbtc"}
        for k, s in series.items():
            key = keymap.get(k)
            if not key:
                continue
            for d, v in s[:-1]:  # 最后一根未收盘，由 CoinGecko 当前价代替
                metrics.append({"key": key, "value": v, "source": "binance", "date": d, "_backfill": True})
            if not cg_ok and s:
                # CoinGecko 失败（云端运行器常见 429）：用 Binance 当前 K 线收盘兜底，标记降级
                metrics.append({"key": key, "value": s[-1][1], "source": "binance-fallback", "asof": s[-1][0],
                                "meta": {"degraded": True, "reason": "coingecko unavailable"}})
        if not cg_ok:
            notes.append("DEGRADED: 主流币价格由 Binance 兜底，市值/ATH/山寨币缺失")
    except Exception as e:
        notes.append(f"binance: {e}")
    try:
        metrics += fetch_fng(Http(timeout=15))
    except Exception as e:
        notes.append(f"fng: {e}")
    return {"metrics": metrics, "news": [], "notes": "; ".join(notes), "raw": {"coingecko": raw}}
