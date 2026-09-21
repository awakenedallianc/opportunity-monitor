"""专项来源（2026-09-20 从本机实测可用；每个子抓取独立 try/except，失败不影响其他）：
- treasury_curve   美国财政部名义/实际收益率曲线 XML（FRED 备份、10Y 实际利率）
- nyfed_rates      纽约联储 EFFR 与联邦基金目标区间
- fiscal_tga       财政部 TGA 余额（流动性）
- bls_cpi          BLS CPI-U（同比）
- coinmetrics      Coin Metrics 社区 API：BTC 实现价格（市值/MVRV）、MVRV
- sosovalue_etf    SoSoValue：美国 BTC/ETH/SOL 现货 ETF 每日净流入（月度加总、连续流入天数）
- cg_treasuries    CoinGecko 上市公司金库（Strategy BTC、BitMine ETH）
- cmc_altseason    CoinMarketCap 山寨季指数（未公开接口，三级来源）
- mempool          mempool.space：算力、距减半区块
- ultrasound       ultrasound.money：ETH 年化增发/销毁/供给增长
- funding          BTC/ETH 永续资金费率与持仓（Binance fapi → OKX 兜底）、Hyperliquid
- kalshi_fed       Kalshi：下次 FOMC 加/降息概率（替代 CME FedWatch）
- eia_brent_spot   EIA 布伦特实物现货（DEMO_KEY；期现价差 = 实物中断指标）
- lbma_gold        LBMA 黄金 PM 定盘价（官方口径交叉核对）
- multpl_cape      Shiller CAPE（multpl.com）
- llama_pm_volume  DefiLlama：Kalshi / Polymarket 日成交
- cg_categories    CoinGecko 分类市值：代币化股票、AI 代理
- rwa_xyz          rwa.xyz 代币化美债 / 股票总量（Next.js 页面内嵌 JSON）
- govtrack_clarity GovTrack：CLARITY 法案（H.R. 3633）状态
- llama_unlocks    DefiLlama 解锁页内嵌 JSON（emissions API 已收费）
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone

from ..utils import Http, log

UTC = timezone.utc


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


# ---------------- 财政部收益率曲线 ----------------
def fetch_treasury_curve(http: Http) -> list[dict]:
    import xml.etree.ElementTree as ET
    ns = {"a": "http://www.w3.org/2005/Atom", "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
          "d": "http://schemas.microsoft.com/ado/2007/08/dataservices"}
    out = []
    now = datetime.now(UTC)
    months = [(now - timedelta(days=30 * i)).strftime("%Y%m") for i in range(0, 14)]
    for data, fields in (("daily_treasury_yield_curve", {"BC_10YEAR": "ust.10y", "BC_2YEAR": "ust.2y", "BC_30YEAR": "ust.30y", "BC_3MONTH": "ust.3m"}),
                         ("daily_treasury_real_yield_curve", {"TC_10YEAR": "ust.real10y", "TC_5YEAR": "ust.real5y"})):
        fails = 0
        for ym in months:
            try:
                url = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
                       f"?data={data}&field_tdr_date_value_month={ym}")
                txt = http.get_text(url, timeout=40)
                root = ET.fromstring(txt.encode("utf-8"))
                entries = root.findall("a:entry", ns)
                if not entries:
                    break  # 早于可用月份：正常耗尽，停止
                fails = 0
                for entry in entries:
                    props = entry.find("a:content/m:properties", ns)
                    if props is None:
                        continue
                    d = props.find("d:NEW_DATE", ns)
                    date = (d.text or "")[:10] if d is not None else None
                    for tag, key in fields.items():
                        el = props.find(f"d:{tag}", ns)
                        if el is not None and el.text:
                            out.append({"key": key, "value": float(el.text), "source": "treasury.gov", "date": date, "_backfill": True})
            except Exception as e:
                # 瞬时网络/解析错误不放弃整个数据集（最新月份失败一次就 break 会丢掉全部曲线）
                fails += 1
                log.debug("treasury %s %s: %s", data, ym, e)
                if fails >= 2:
                    break
    latest: dict[str, dict] = {}
    for r in out:
        if r["key"] not in latest or r["date"] > latest[r["key"]]["date"]:
            latest[r["key"]] = r
    for k, r in latest.items():
        out.append({"key": k, "value": r["value"], "source": "treasury.gov", "asof": r["date"]})
    if "ust.10y" in latest and "ust.real10y" in latest:
        out.append({"key": "ust.breakeven10y", "value": latest["ust.10y"]["value"] - latest["ust.real10y"]["value"], "source": "treasury.gov"})
    return out


# ---------------- 纽约联储 ----------------
def fetch_nyfed_rates(http: Http) -> list[dict]:
    d = http.get_json("https://markets.newyorkfed.org/api/rates/all/latest.json")
    out = []
    for r in d.get("refRates", []):
        if r.get("type") == "EFFR":
            out.append({"key": "fed.effr", "value": float(r["percentRate"]), "source": "newyorkfed", "asof": r.get("effectiveDate")})
            if r.get("targetRateFrom") is not None:
                out.append({"key": "fed.target_low", "value": float(r["targetRateFrom"]), "source": "newyorkfed", "asof": r.get("effectiveDate")})
                out.append({"key": "fed.target_high", "value": float(r["targetRateTo"]), "source": "newyorkfed", "asof": r.get("effectiveDate")})
        if r.get("type") == "SOFR":
            out.append({"key": "fed.sofr", "value": float(r["percentRate"]), "source": "newyorkfed", "asof": r.get("effectiveDate")})
    try:
        h = http.get_json("https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json",
                          params={"startDate": (datetime.now(UTC) - timedelta(days=400)).strftime("%Y-%m-%d")})
        for r in h.get("refRates", []):
            out.append({"key": "fed.effr", "value": float(r["percentRate"]), "source": "newyorkfed", "date": r["effectiveDate"], "_backfill": True})
    except Exception as e:
        log.debug("effr history: %s", e)
    try:
        rp = http.get_json("https://markets.newyorkfed.org/api/rp/reverserepo/propositions/search.json",
                           params={"startDate": (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%d")})
        ops = rp.get("repo", {}).get("operations", [])
        if ops:
            o = ops[0]
            out.append({"key": "fed.rrp", "value": float(o.get("totalAmtAccepted") or 0), "source": "newyorkfed", "asof": o.get("operationDate")})
    except Exception as e:
        log.debug("rrp: %s", e)
    return out


# ---------------- 财政部 TGA ----------------
def fetch_fiscal_tga(http: Http) -> list[dict]:
    d = http.get_json("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/operating_cash_balance",
                      params={"sort": "-record_date", "page[size]": 60})
    out = []
    for r in d.get("data", []):
        if "Treasury General Account" in (r.get("account_type") or "") and r.get("open_today_bal"):
            out.append({"key": "fiscal.tga", "value": float(r["open_today_bal"]) * 1e6, "source": "fiscaldata.treasury.gov",
                        "date": r["record_date"], "_backfill": True})
    if out:
        out.append({"key": "fiscal.tga", "value": out[0]["value"], "source": "fiscaldata.treasury.gov", "asof": out[0]["date"]})
    return out


# ---------------- BLS CPI ----------------
def fetch_bls_cpi(http: Http) -> list[dict]:
    y = datetime.now(UTC).year
    # CUUR0000SA0 = 未季调（新闻/报告口径的同比用它；此前的 CUSR0000SA0 是季调，YoY 会差 0.1–0.2 个百分点）
    d = http.get_json(f"https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0", params={"startyear": y - 2, "endyear": y})
    series = d.get("Results", {}).get("series", [{}])[0].get("data", [])
    pts = {}
    for r in series:
        if r.get("period", "").startswith("M") and r["period"] != "M13":
            try:
                pts[f"{r['year']}-{r['period'][1:]}"] = float(r["value"])
            except (TypeError, ValueError):
                continue
    keys = sorted(pts)
    out = []
    for k in keys:
        y0, m0 = int(k[:4]), int(k[5:])
        prev = f"{y0-1}-{m0:02d}"
        if prev in pts:
            out.append({"key": "macro.cpi_yoy", "value": (pts[k] / pts[prev] - 1) * 100, "source": "bls", "date": f"{k}-01", "_backfill": True})
    if out:
        out.append({"key": "macro.cpi_yoy", "value": out[-1]["value"], "source": "bls", "asof": out[-1]["date"][:7]})
    return out


# ---------------- Coin Metrics ----------------
def fetch_coinmetrics(http: Http) -> list[dict]:
    start = (datetime.now(UTC) - timedelta(days=400)).strftime("%Y-%m-%d")
    d = http.get_json("https://community-api.coinmetrics.io/v4/timeseries/asset-metrics",
                      params={"assets": "btc", "metrics": "PriceUSD,CapMVRVCur,CapMrktCurUSD,SplyCur", "frequency": "1d",
                              "start_time": start, "page_size": 1000})
    out = []
    last = None
    for r in d.get("data", []):
        try:
            mvrv, mcap, sply = float(r["CapMVRVCur"]), float(r["CapMrktCurUSD"]), float(r["SplyCur"])
        except (KeyError, TypeError, ValueError):
            continue
        if mvrv <= 0 or sply <= 0:
            continue
        rp = mcap / mvrv / sply
        date = r["time"][:10]
        out.append({"key": "crypto.btc.realized_price", "value": rp, "source": "coinmetrics", "date": date, "_backfill": True})
        out.append({"key": "crypto.btc.mvrv", "value": mvrv, "source": "coinmetrics", "date": date, "_backfill": True})
        last = (date, rp, mvrv)
    if last:
        out.append({"key": "crypto.btc.realized_price", "value": last[1], "source": "coinmetrics", "asof": last[0],
                    "meta": {"method": "CapMrktCurUSD / CapMVRVCur / SplyCur"}})
        out.append({"key": "crypto.btc.mvrv", "value": last[2], "source": "coinmetrics", "asof": last[0]})
    return out


# ---------------- SoSoValue ETF 资金流 ----------------
def fetch_sosovalue_etf(http: Http) -> list[dict]:
    out = []
    for typ, key in (("us-btc-spot", "btc"), ("us-eth-spot", "eth"), ("us-sol-spot", "sol")):
        try:
            d = http.post_json("https://api.sosovalue.xyz/openapi/v2/etf/historicalInflowChart", {"type": typ},
                               headers={"Content-Type": "application/json"})
            rows = d.get("data") or []
            rows = [r for r in rows if r.get("date")]
            rows.sort(key=lambda r: r["date"])
            if not rows:
                continue
            daily = [(r["date"][:10], float(r.get("totalNetInflow") or 0)) for r in rows]
            for date, val in daily[-400:]:
                out.append({"key": f"etf.{key}.flow_daily", "value": val, "source": "sosovalue", "date": date, "_backfill": True})
            last = rows[-1]
            out.append({"key": f"etf.{key}.flow_daily", "value": float(last.get("totalNetInflow") or 0), "source": "sosovalue", "asof": last["date"][:10]})
            cum = float(last.get("cumNetInflow") or 0) or sum(v for _, v in daily)
            out.append({"key": f"etf.{key}.cum_flow", "value": cum, "source": "sosovalue", "asof": last["date"][:10]})
            if last.get("totalNetAssets"):
                out.append({"key": f"etf.{key}.aum", "value": float(last["totalNetAssets"]), "source": "sosovalue", "asof": last["date"][:10]})
            vals = [v for _, v in daily]
            out.append({"key": f"etf.{key}.flow_30d", "value": sum(vals[-21:]), "source": "sosovalue"})
            out.append({"key": f"etf.{key}.flow_60d", "value": sum(vals[-42:]), "source": "sosovalue"})
            # 连续净流入/流出交易日
            streak = 0
            for v in reversed(vals):
                if v > 0 and streak >= 0:
                    streak += 1
                elif v < 0 and streak <= 0:
                    streak -= 1
                else:
                    break
            out.append({"key": f"etf.{key}.streak_days", "value": streak, "source": "sosovalue"})
            time.sleep(0.8)
        except Exception as e:
            log.warning("sosovalue %s: %s", typ, e)
    return out


# ---------------- CoinGecko 上市公司金库 ----------------
def fetch_cg_treasuries(http: Http) -> list[dict]:
    out = []
    for coin, key in (("bitcoin", "btc"), ("ethereum", "eth")):
        try:
            d = http.get_json(f"https://api.coingecko.com/api/v3/companies/public_treasury/{coin}")
            out.append({"key": f"treasury.total_{key}", "value": float(d.get("total_holdings") or 0), "source": "coingecko",
                        "meta": {"companies": len(d.get("companies", [])), "pct_supply": d.get("market_cap_dominance")}})
            for c in d.get("companies", []):
                sym = (c.get("symbol") or "").split(".")[0]
                if sym in ("MSTR", "BMNR"):
                    out.append({"key": f"treasury.{sym}_{key}", "value": float(c.get("total_holdings") or 0), "source": "coingecko",
                                "meta": {"name": c.get("name"), "entry_value_usd": c.get("total_entry_value_usd")}})
            time.sleep(2.5)
        except Exception as e:
            log.warning("cg treasury %s: %s", coin, e)
    return out


# ---------------- CMC 山寨季 ----------------
def fetch_cmc_altseason(http: Http) -> list[dict]:
    end = int(time.time())
    start = end - 86400 * 120
    d = http.get_json("https://api.coinmarketcap.com/data-api/v3/altcoin-season/chart", params={"start": start, "end": end})
    pts = (d.get("data") or {}).get("points") or []
    out = []
    for p in pts:
        try:
            date = datetime.fromtimestamp(int(p["timestamp"]), tz=UTC).strftime("%Y-%m-%d")
            out.append({"key": "crypto.altseason", "value": float(p["altcoinIndex"]), "source": "coinmarketcap", "date": date, "_backfill": True})
        except Exception:
            continue
    if out:
        out.append({"key": "crypto.altseason", "value": out[-1]["value"], "source": "coinmarketcap", "asof": out[-1]["date"]})
    return out


# ---------------- mempool.space ----------------
def fetch_mempool(http: Http) -> list[dict]:
    out = []
    h = http.get_json("https://mempool.space/api/v1/mining/hashrate/3m")
    hr = h.get("hashrates") or []
    if hr:
        out.append({"key": "btc.hashrate_eh", "value": float(hr[-1]["avgHashrate"]) / 1e18, "source": "mempool.space"})
    tip = http.get_json("https://mempool.space/api/blocks/tip/height")
    if isinstance(tip, int):
        remaining = 1_050_000 - tip
        out.append({"key": "btc.blocks_to_halving", "value": remaining, "source": "mempool.space",
                    "meta": {"est_date": (datetime.now(UTC) + timedelta(minutes=10 * remaining)).strftime("%Y-%m-%d")}})
        out.append({"key": "btc.days_to_halving", "value": remaining * 10 / 1440, "source": "mempool.space"})
    return out


# ---------------- ultrasound.money ----------------
def fetch_ultrasound(http: Http) -> list[dict]:
    d = http.get_json("https://ultrasound.money/api/v2/fees/gauge-rates")
    g = d.get("d30") or d.get("d7") or d.get("d1") or {}
    out = []
    if g:
        out.append({"key": "eth.supply_growth_yearly_pct", "value": float(g.get("supply_growth_rate_yearly") or 0) * 100, "source": "ultrasound.money",
                    "meta": {"window": "d30" if "d30" in d else "d7"}})
        iss = (g.get("issuance_rate_yearly") or {}).get("eth")
        burn = (g.get("burn_rate_yearly") or {}).get("eth")
        if iss is not None:
            out.append({"key": "eth.issuance_yearly_eth", "value": float(iss), "source": "ultrasound.money"})
        if burn is not None:
            out.append({"key": "eth.burn_yearly_eth", "value": float(burn), "source": "ultrasound.money"})
    return out


# ---------------- 资金费率 / 持仓 ----------------
def fetch_funding(http: Http) -> list[dict]:
    out = []
    for sym in ("BTC", "ETH"):
        got = False
        try:
            d = http.get_json(f"https://fapi.binance.com/fapi/v1/premiumIndex", params={"symbol": f"{sym}USDT"})
            out.append({"key": f"funding.{sym}", "value": float(d["lastFundingRate"]) * 100, "source": "binance-fapi"})
            got = True
        except Exception:
            pass
        if not got:
            try:
                d = http.get_json("https://www.okx.com/api/v5/public/funding-rate", params={"instId": f"{sym}-USDT-SWAP"})
                out.append({"key": f"funding.{sym}", "value": float(d["data"][0]["fundingRate"]) * 100, "source": "okx"})
            except Exception as e:
                log.debug("funding %s: %s", sym, e)
    try:
        d = http.post_json("https://api.hyperliquid.xyz/info", {"type": "metaAndAssetCtxs"})
        universe = d[0].get("universe", [])
        ctxs = d[1]
        for u, c in zip(universe, ctxs):
            if u.get("name") in ("BTC", "ETH", "HYPE"):
                out.append({"key": f"hl.funding.{u['name']}", "value": float(c.get("funding") or 0) * 100 * 8, "source": "hyperliquid",
                            "meta": {"open_interest": c.get("openInterest"), "day_ntl_vlm": c.get("dayNtlVlm")}})
                if c.get("openInterest") and c.get("markPx"):
                    out.append({"key": f"hl.oi_usd.{u['name']}", "value": float(c["openInterest"]) * float(c["markPx"]), "source": "hyperliquid"})
        # 援助基金 HYPE 余额
        s = http.post_json("https://api.hyperliquid.xyz/info", {"type": "spotClearinghouseState", "user": "0xfefefefefefefefefefefefefefefefefefefefe"})
        for b in s.get("balances", []):
            if b.get("coin") == "HYPE":
                out.append({"key": "hl.af_hype_balance", "value": float(b.get("total") or 0), "source": "hyperliquid"})
    except Exception as e:
        log.debug("hyperliquid: %s", e)
    return out


# ---------------- Kalshi 联储 ----------------
def fetch_kalshi_fed(http: Http) -> list[dict]:
    d = http.get_json("https://api.elections.kalshi.com/trade-api/v2/events",
                      params={"series_ticker": "KXFEDDECISION", "status": "open", "with_nested_markets": "true", "limit": 20})
    evs = d.get("events") or []
    out = []
    if not evs:
        return out
    # 取最近的一次会议（event_ticker 形如 KXFEDDECISION-26OCT）
    def _key(e):
        m = re.search(r"-(\d{2})([A-Z]{3})", e.get("event_ticker", ""))
        months = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6, "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}
        return (int(m.group(1)), months.get(m.group(2), 13)) if m else (99, 99)
    evs.sort(key=_key)
    ev = evs[0]
    for m in ev.get("markets", []):
        sub = (m.get("subtitle") or m.get("yes_sub_title") or "").lower()
        # 价格字段为美元（0–1）：last_price_dollars / yes_bid_dollars / yes_ask_dollars；缺失时用 1 - no 侧中价
        def _f(k):
            try:
                return float(m.get(k)) if m.get(k) not in (None, "") else None
            except Exception:
                return None
        p = _f("last_price_dollars")
        if p is None and _f("yes_bid_dollars") is not None and _f("yes_ask_dollars") is not None:
            p = (_f("yes_bid_dollars") + _f("yes_ask_dollars")) / 2
        if p is None and _f("no_bid_dollars") is not None and _f("no_ask_dollars") is not None:
            p = 1 - (_f("no_bid_dollars") + _f("no_ask_dollars")) / 2
        if p is None:
            p = _f("last_price")
            if p is not None and p > 1:
                p = p / 100
        if p is None:
            continue
        p = p * 100
        if "0bps" in sub or "maintain" in sub or "no change" in sub or "unchanged" in sub:
            slug = "hold"
        elif "hike" in sub or "increase" in sub:
            slug = "hike"
        elif "cut" in sub or "decrease" in sub:
            slug = "cut"
        else:
            slug = None
        if slug:
            k = f"kalshi.fed_next.{slug}"
            # 同类多个（如 hike25/hike50）取和
            existing = next((x for x in out if x["key"] == k), None)
            if existing:
                existing["value"] += p
            else:
                out.append({"key": k, "value": p, "source": "kalshi", "meta": {"event": ev.get("title"), "ticker": ev.get("event_ticker")}})
    return out


# ---------------- EIA 布伦特现货 ----------------
def fetch_eia_brent_spot(http: Http) -> list[dict]:
    key = os.environ.get("EIA_API_KEY", "DEMO_KEY")
    d = http.get_json("https://api.eia.gov/v2/petroleum/pri/spt/data/",
                      params={"api_key": key, "frequency": "daily", "data[0]": "value", "facets[series][]": "RBRTE",
                              "sort[0][column]": "period", "sort[0][direction]": "desc", "length": 400})
    rows = (d.get("response") or {}).get("data") or []
    out = []
    for r in rows:
        try:
            out.append({"key": "eia.brent_spot", "value": float(r["value"]), "source": "eia", "date": r["period"], "_backfill": True})
        except Exception:
            continue
    if rows:
        out.append({"key": "eia.brent_spot", "value": float(rows[0]["value"]), "source": "eia", "asof": rows[0]["period"]})
    return out


# ---------------- LBMA 黄金 ----------------
def fetch_lbma_gold(http: Http) -> list[dict]:
    d = http.get_json("https://prices.lbma.org.uk/json/gold_pm.json", timeout=40)
    out = []
    for r in d[-400:]:
        try:
            out.append({"key": "lbma.gold_pm", "value": float(r["v"][0]), "source": "lbma", "date": r["d"], "_backfill": True})
        except Exception:
            continue
    if out:
        out.append({"key": "lbma.gold_pm", "value": out[-1]["value"], "source": "lbma", "asof": out[-1]["date"]})
    return out


# ---------------- multpl CAPE ----------------
def fetch_multpl_cape(http: Http) -> list[dict]:
    txt = http.get_text("https://www.multpl.com/shiller-pe/table/by-month")
    rows = re.findall(r"<td>\s*([A-Z][a-z]{2} \d{1,2}, \d{4})\s*</td>\s*<td>\s*(?:&#x2002;|&nbsp;)?\s*([\d]{1,3}\.\d{1,2})\s*</td>", txt, re.S)
    out = []
    for ds, val in rows[:24]:
        try:
            date = datetime.strptime(ds, "%b %d, %Y").strftime("%Y-%m-%d")
            out.append({"key": "val.cape", "value": float(val), "source": "multpl", "date": date, "_backfill": True})
        except Exception:
            continue
    if out:
        out.append({"key": "val.cape", "value": out[0]["value"], "source": "multpl", "asof": out[0]["date"]})
    return out


# ---------------- DefiLlama 预测市场成交 ----------------
def fetch_llama_pm_volume(http: Http) -> list[dict]:
    d = http.get_json("https://api.llama.fi/overview/dexs", params={"excludeTotalDataChart": "true", "excludeTotalDataChartBreakdown": "true"})
    out = []
    for p in d.get("protocols", []):
        n = (p.get("name") or "").lower()
        if n.startswith("kalshi"):
            out.append({"key": "pm.volume24h.kalshi", "value": float(p.get("total24h") or 0), "source": "defillama", "meta": {"30d": p.get("total30d")}})
        elif n.startswith("polymarket"):
            out.append({"key": "pm.volume24h.polymarket", "value": float(p.get("total24h") or 0), "source": "defillama", "meta": {"30d": p.get("total30d")}})
    return out


# ---------------- CoinGecko 分类 ----------------
def fetch_cg_categories(http: Http) -> list[dict]:
    d = http.get_json("https://api.coingecko.com/api/v3/coins/categories")
    out = []
    for c in d:
        cid = c.get("id")
        if cid in ("tokenized-stock", "ai-agents", "depin", "real-world-assets-rwa", "ai-meme-coins", "artificial-intelligence"):
            out.append({"key": f"cg.cat.{cid}", "value": float(c.get("market_cap") or 0), "source": "coingecko",
                        "meta": {"name": c.get("name"), "vol24h": c.get("volume_24h"), "chg24h": c.get("market_cap_change_24h")}})
    return out


# ---------------- rwa.xyz ----------------
def fetch_rwa_xyz(http: Http) -> list[dict]:
    out = []
    for page, key in (("treasuries", "rwa.treasuries"), ("stocks", "rwa.stocks")):
        try:
            txt = http.get_text(f"https://app.rwa.xyz/{page}", timeout=40)
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', txt, re.S)
            if not m:
                continue
            j = json.loads(m.group(1))
            aggs = j.get("props", {}).get("pageProps", {}).get("aggregates") or []
            for a in aggs:
                lbl = (a.get("label") or "").lower()
                if "value" in lbl or "market cap" in lbl or "total" in lbl:
                    out.append({"key": key, "value": float(a.get("value") or 0), "source": "rwa.xyz", "meta": {"label": a.get("label")}})
                    break
            time.sleep(1)
        except Exception as e:
            log.debug("rwa %s: %s", page, e)
    return out


# ---------------- GovTrack CLARITY ----------------
def fetch_govtrack_clarity(http: Http) -> list[dict]:
    d = http.get_json("https://www.govtrack.us/api/v2/bill", params={"congress": 119, "bill_type": "house_bill", "number": 3633})
    objs = d.get("objects") or []
    if not objs:
        return []
    b = objs[0]
    return [{"key": "bill.clarity.status", "value": None, "source": "govtrack",
             "meta": {"status": b.get("current_status"), "status_date": b.get("current_status_date"), "title": b.get("title_without_number"),
                      "url": "https://www.govtrack.us" + (b.get("link") or "")}}]


# ---------------- DefiLlama 解锁页 ----------------
def fetch_llama_unlocks(http: Http) -> list[dict]:
    txt = http.get_text("https://defillama.com/unlocks", timeout=60)
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', txt, re.S)
    if not m:
        return []
    j = json.loads(m.group(1))
    data = j.get("props", {}).get("pageProps", {}).get("data") or []
    wanted = {"XPL", "ENA", "MON", "ONDO", "HYPE", "ARB", "SUI", "APT", "ATH", "GRASS", "TAO", "PENDLE", "JUP", "OP", "ZEC", "AVAX", "SKY", "MORPHO", "INJ", "AKT"}
    out = []
    now = time.time()
    for t in data:
        sym = (t.get("tSymbol") or t.get("symbol") or "").upper()
        if sym not in wanted:
            continue
        ev = t.get("nextEvent") or {}
        ts = ev.get("date") or ev.get("timestamp")
        events = []
        for e in (t.get("upcomingEvent") or t.get("events") or [])[:12]:
            d0 = e.get("date") or e.get("timestamp")
            if not d0:
                continue
            events.append({"date": datetime.fromtimestamp(int(d0), tz=UTC).strftime("%Y-%m-%d"), "tokens": e.get("amount") or e.get("noOfTokens"),
                           "type": e.get("unlockType") or e.get("category"), "description": e.get("description")})
        nxt = None
        if ts:
            nd = datetime.fromtimestamp(int(ts), tz=UTC)
            nxt = {"date": nd.strftime("%Y-%m-%d"), "tokens": ev.get("amount") or ev.get("noOfTokens"), "type": ev.get("unlockType"),
                   "pct_circ": (float(ev.get("amount") or 0) / float(t.get("circSupply") or t.get("circ") or 1) * 100) if t.get("circSupply") or t.get("circ") else None}
        out.append({"key": f"unlock.next_days.{sym}", "value": ((int(ts) - now) / 86400) if ts else None, "source": "defillama",
                    "meta": {"next": nxt, "events": events, "circ": t.get("circSupply") or t.get("circ"), "max": t.get("maxSupply") or t.get("max")}})
    return out


# ---------------- IMF PortWatch 咽喉要道 ----------------
CHOKEPOINTS = {"hormuz": ("hormuz",), "bab_el_mandeb": ("bab", "mandeb"), "suez": ("suez",), "taiwan": ("taiwan",),
               "malacca": ("malacca",), "panama": ("panama",), "cape": ("good hope", "cape")}


def fetch_portwatch(http: Http) -> list[dict]:
    base = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/Daily_Chokepoints_Data/FeatureServer/0/query"
    rows = []
    offset = 0
    cutoff = (datetime.now(UTC) - timedelta(days=420)).strftime("%Y-%m-%d")
    for _ in range(20):  # 图层每页最多 1000 行；约 28 个要道/天 × 420 天 ≈ 12 页
        d = http.get_json(base, params={"where": "1=1", "outFields": "*", "orderByFields": "date DESC", "resultRecordCount": 1000,
                                        "resultOffset": offset, "f": "json"}, timeout=60)
        feats = d.get("features") or []
        if not feats:
            break
        stop = False
        for f in feats:
            a = f.get("attributes") or {}
            date = a.get("date")
            if isinstance(date, (int, float)):
                date = datetime.fromtimestamp(date / 1000, tz=UTC).strftime("%Y-%m-%d")
            date = str(date)[:10]
            if date < cutoff:
                stop = True
                continue
            rows.append((date, a))
        if stop or not d.get("exceededTransferLimit"):
            break
        offset += len(feats)
        time.sleep(0.5)
    out = []
    by_key: dict[str, list[tuple[str, float]]] = {}
    for date, a in rows:
        name = str(a.get("portname") or a.get("name") or "").lower()
        total = a.get("n_total")
        if total is None:
            # 兜底：所有 n_ 开头字段之和不可靠，只用 n_total
            continue
        for key, kws in CHOKEPOINTS.items():
            if all(k in name for k in kws) or (len(kws) == 1 and kws[0] in name):
                by_key.setdefault(key, []).append((date, float(total)))
                if key == "hormuz" and a.get("n_tanker") is not None:
                    by_key.setdefault("hormuz_tanker", []).append((date, float(a["n_tanker"])))
    for key, s in by_key.items():
        s.sort()
        for date, v in s:
            out.append({"key": f"chokepoint.{key}.transits", "value": v, "source": "imf-portwatch", "date": date, "_backfill": True})
        last = s[-1]
        out.append({"key": f"chokepoint.{key}.transits", "value": last[1], "source": "imf-portwatch", "asof": last[0]})
        vals = [v for _, v in s]
        avg7 = sum(vals[-7:]) / min(7, len(vals))
        # 基线：优先战前窗口 2025-11-01..2026-02-26（伊朗战争 2026-02-28 爆发）；不足 20 天则取一年前 90 天；再不足取最早 90 天
        prewar = [v for d0, v in s if "2025-11-01" <= d0 <= "2026-02-26"]
        older = [v for d0, v in s if d0 < (datetime.now(UTC) - timedelta(days=300)).strftime("%Y-%m-%d")]
        if len(prewar) >= 20:
            baseline, bnote = sum(prewar) / len(prewar), "prewar 2025-11-01..2026-02-26"
        elif older:
            baseline, bnote = sum(older[:90]) / min(90, len(older)), "year-ago 90d"
        else:
            baseline, bnote = sum(vals[:90]) / min(90, len(vals)), f"earliest 90d from {s[0][0]} (may be intra-war)"
        out.append({"key": f"chokepoint.{key}.avg7", "value": avg7, "source": "imf-portwatch", "asof": last[0]})
        out.append({"key": f"chokepoint.{key}.baseline", "value": baseline, "source": "imf-portwatch", "meta": {"window": bnote, "n_days": len(s)}})
        if baseline:
            out.append({"key": f"chokepoint.{key}.ratio", "value": avg7 / baseline, "source": "imf-portwatch", "asof": last[0],
                        "meta": {"avg7": avg7, "baseline": baseline, "window": bnote}})
    return out


# ---------------- GPR 地缘风险指数（Caldara–Iacoviello）----------------
def fetch_gpr(http: Http) -> list[dict]:
    import xlrd  # 纯 Python，读取 .xls
    r = http.get("https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls", timeout=60)
    r.raise_for_status()
    wb = xlrd.open_workbook(file_contents=r.content)
    sh = wb.sheet_by_index(0)
    head = [str(sh.cell_value(0, c)).strip().lower() for c in range(sh.ncols)]
    def col(name):
        return head.index(name) if name in head else None
    ci, cd, ct, ca = col("gprd"), col("date"), col("gprd_threat"), col("gprd_act")
    if ci is None or cd is None:
        return []
    out = []
    for rix in range(max(1, sh.nrows - 400), sh.nrows):
        try:
            dv = sh.cell_value(rix, cd)
            if isinstance(dv, float):
                y, m, dd, *_ = xlrd.xldate_as_tuple(dv, wb.datemode)
                date = f"{y:04d}-{m:02d}-{dd:02d}"
            else:
                # 文本日期必须补零规范化：'2026/9/5' 直接 replace 会得 '2026-9-5'，字符串 max() 会排错序
                parts = str(dv).strip().replace("/", "-").split("-")[:3]
                y, m, dd = (int(x) for x in parts)
                date = f"{y:04d}-{m:02d}-{dd:02d}"
            v = float(sh.cell_value(rix, ci))
        except Exception:
            continue
        out.append({"key": "gpr.daily", "value": v, "source": "iacoviello", "date": date, "_backfill": True})
        for c, k in ((ct, "gpr.threat"), (ca, "gpr.act")):
            if c is not None:
                try:
                    out.append({"key": k, "value": float(sh.cell_value(rix, c)), "source": "iacoviello", "date": date, "_backfill": True})
                except Exception:
                    pass
    if out:
        lastd = max(x["date"] for x in out)
        for k in ("gpr.daily", "gpr.threat", "gpr.act"):
            v = [x for x in out if x["key"] == k and x["date"] == lastd]
            if v:
                out.append({"key": k, "value": v[-1]["value"], "source": "iacoviello", "asof": lastd})
        dvals = [x["value"] for x in out if x["key"] == "gpr.daily" and x.get("_backfill")]
        out.append({"key": "gpr.daily_30d_avg", "value": sum(dvals[-30:]) / min(30, len(dvals)), "source": "iacoviello", "asof": lastd})
    return out


# ---------------- 解放军台海活动（plavis 社区 CSV，需与国防部页面核对）----------------
def fetch_plavis(http: Http) -> list[dict]:
    import csv, io
    txt = http.get_text("https://raw.githubusercontent.com/ypcat/plavis/main/data/pla_activity.csv", timeout=40)
    rows = list(csv.DictReader(io.StringIO(txt)))
    out = []
    pts = []
    for r in rows[-400:]:
        try:
            date = r.get("date", "")[:10]
            if r.get("total_aircraft") in ("", None):  # 未解析到通报的日子 = 缺失，不是 0
                continue
            n = float(r.get("total_aircraft"))
            pts.append((date, n))
            out.append({"key": "pla.aircraft_daily", "value": n, "source": "plavis", "date": date, "_backfill": True})
            if r.get("plan_vessels") or r.get("total_vessels"):
                out.append({"key": "pla.vessels_daily", "value": float(r.get("plan_vessels") or r.get("total_vessels") or 0), "source": "plavis", "date": date, "_backfill": True})
        except Exception:
            continue
    if pts:
        pts.sort()
        out.append({"key": "pla.aircraft_daily", "value": pts[-1][1], "source": "plavis", "asof": pts[-1][0]})
        vals = [v for _, v in pts]
        out.append({"key": "pla.aircraft_7d_avg", "value": sum(vals[-7:]) / min(7, len(vals)), "source": "plavis", "asof": pts[-1][0]})
        out.append({"key": "pla.aircraft_30d_max", "value": max(vals[-30:]), "source": "plavis", "asof": pts[-1][0]})
    return out


# ---------------- 集运运价：SCFI / Drewry WCI / FBX ----------------
def fetch_freight(http: Http) -> list[dict]:
    out = []
    try:
        txt = http.get_text("https://www.sse.net.cn/index/singleIndex", params={"indexType": "scfi"}, timeout=40)
        dates = re.findall(r"(20\d{2}-\d{2}-\d{2})", txt)
        vals = re.findall(r">\s*([1-9]\d{2,4}\.\d{2})\s*<", txt)
        if dates and vals:
            out.append({"key": "freight.scfi", "value": float(vals[0]), "source": "sse.net.cn", "asof": dates[0]})
    except Exception as e:
        log.debug("scfi: %s", e)
    try:
        txt = http.get_text("https://www.drewry.co.uk/supply-chain-advisors/supply-chain-expertise/world-container-index-assessed-by-drewry", timeout=40)
        m = re.search(r"\$([\d,]{4,7})\s*per\s*40\s*ft", txt, re.I)
        if m:
            out.append({"key": "freight.drewry_wci", "value": float(m.group(1).replace(",", "")), "source": "drewry"})
    except Exception as e:
        log.debug("drewry: %s", e)
    try:
        txt = http.get_text("https://fbx.freightos.com/", timeout=40)
        for label, key in (("FBX", "freight.fbx"), ("FBX01", "freight.fbx01"), ("FBX11", "freight.fbx11")):
            m = re.search(r'"label":"%s","value":"\$([\d,]+)"' % label, txt)
            if m:
                out.append({"key": key, "value": float(m.group(1).replace(",", "")), "source": "freightos"})
    except Exception as e:
        log.debug("fbx: %s", e)
    return out


# ---------------- 日本财务省 JGB 收益率（套息引信）----------------
def fetch_mof_jgb(http: Http) -> list[dict]:
    import csv as _csv
    import io as _io
    txt = http.get_text("https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv", timeout=40)
    rows = list(_csv.reader(_io.StringIO(txt)))
    # 找表头行（含 Date 与年限列）
    head_i = next((i for i, r in enumerate(rows) if r and str(r[0]).strip().lower() == "date"), None)
    if head_i is None:
        return []
    head = [c.strip() for c in rows[head_i]]
    cols = {}
    for want, key in (("10Y", "mof.jgb10y"), ("30Y", "mof.jgb30y"), ("40Y", "mof.jgb40y")):
        if want in head:
            cols[head.index(want)] = key
    out = []
    last = {}
    for r in rows[head_i + 1:]:
        if not r or not r[0].strip():
            continue
        ds = r[0].strip().replace("/", "-")
        try:
            y, m, d0 = (int(x) for x in ds.split("-")[:3])
            date = f"{y:04d}-{m:02d}-{d0:02d}"
        except (ValueError, IndexError):
            continue
        for ci, key in cols.items():
            try:
                v = float(r[ci])
            except (ValueError, IndexError):
                continue
            out.append({"key": key, "value": v, "source": "mof.go.jp", "date": date, "_backfill": True})
            last[key] = (date, v)
    for key, (date, v) in last.items():
        out.append({"key": key, "value": v, "source": "mof.go.jp", "asof": date})
    return out


# ---------------- CFTC 日元期货持仓（套息拥挤度）----------------
def fetch_cftc_cot(http: Http) -> list[dict]:
    d = http.get_json("https://publicreporting.cftc.gov/resource/6dca-aqww.json",
                      params={"cftc_contract_market_code": "097741", "$order": "report_date_as_yyyy_mm_dd DESC", "$limit": "60"})
    out = []
    pts = []
    for r in d if isinstance(d, list) else []:
        try:
            date = str(r["report_date_as_yyyy_mm_dd"])[:10]
            net = float(r["noncomm_positions_long_all"]) - float(r["noncomm_positions_short_all"])
        except (KeyError, TypeError, ValueError):
            continue
        pts.append((date, net))
    pts.sort()
    for date, net in pts:
        out.append({"key": "cftc.jpy_net", "value": net, "source": "cftc", "date": date, "_backfill": True})
    if pts:
        out.append({"key": "cftc.jpy_net", "value": pts[-1][1], "source": "cftc", "asof": pts[-1][0],
                    "meta": {"note": "非商业净头寸（多-空），周五发布周二数据"}})
    return out


# ---------------- NRC 核电机组每日出力（电力缺口 / 铀）----------------
def fetch_nrc_power(http: Http) -> list[dict]:
    txt = http.get_text("https://www.nrc.gov/documents-reports/document-collections/events-reports-associated-with/power-reactor-status-reports/PowerReactorStatusForLast365Days.txt", timeout=60)
    from datetime import datetime as _dt
    by_day: dict[str, list[float]] = {}
    for line in txt.splitlines():
        parts = line.split("|")
        if len(parts) < 3:
            continue
        try:
            date = _dt.strptime(parts[0].strip().split()[0], "%m/%d/%Y").strftime("%Y-%m-%d")
            power = float(parts[2])
        except (ValueError, IndexError):
            continue
        by_day.setdefault(date, []).append(power)
    days = sorted(by_day)[-90:]
    out = []
    for d0 in days:
        vals = by_day[d0]
        out.append({"key": "nrc.fleet_avg_power", "value": sum(vals) / len(vals), "source": "nrc.gov", "date": d0, "_backfill": True})
    if days:
        d0 = days[-1]
        out.append({"key": "nrc.fleet_avg_power", "value": sum(by_day[d0]) / len(by_day[d0]), "source": "nrc.gov", "asof": d0,
                    "meta": {"units": len(by_day[d0])}})
    return out


# ---------------- 财政部：总债务 / 利息 / 拍卖 / 债务上限余量（美债利息雪球）----------------
def fetch_fiscal_debt(http: Http) -> list[dict]:
    out = []
    base = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
    # 1) 日频总债务（回填 400 天，供 change/同比规则）
    try:
        d = http.get_json(f"{base}/v2/accounting/od/debt_to_penny",
                          params={"sort": "-record_date", "page[size]": 400, "fields": "record_date,tot_pub_debt_out_amt"})
        rows = d.get("data") or []
        for r in reversed(rows):
            try:
                out.append({"key": "fiscal.debt_total", "value": float(r["tot_pub_debt_out_amt"]), "source": "fiscaldata",
                            "date": r["record_date"], "_backfill": True})
            except (KeyError, TypeError, ValueError):
                continue
        if rows:
            out.append({"key": "fiscal.debt_total", "value": float(rows[0]["tot_pub_debt_out_amt"]), "source": "fiscaldata",
                        "asof": rows[0]["record_date"]})
    except Exception as e:
        log.debug("debt_to_penny: %s", e)
    # 2) 利息支出：滚动 12 月同比（月频数据集，字段名做候选探测）
    try:
        d = http.get_json(f"{base}/v2/accounting/od/interest_expense", params={"sort": "-record_date", "page[size]": 2500})
        rows = d.get("data") or []
        val_field = next((f for f in ("month_expense_amt", "expense_amt", "intragov_expense_amt") if rows and f in rows[0]), None)
        if val_field:
            monthly: dict[str, float] = {}
            for r in rows:
                try:
                    monthly[str(r["record_date"])[:7]] = monthly.get(str(r["record_date"])[:7], 0.0) + float(r[val_field])
                except (KeyError, TypeError, ValueError):
                    continue
            months = sorted(monthly)
            # 最旧一个月可能被分页截断，弃掉不完整的首月
            if len(months) >= 26:
                months = months[1:]
            if len(months) >= 24:
                cur12 = sum(monthly[m] for m in months[-12:])
                prev12 = sum(monthly[m] for m in months[-24:-12])
                if prev12:
                    out.append({"key": "fiscal.interest_12m_yoy", "value": (cur12 / prev12 - 1) * 100, "source": "fiscaldata",
                                "asof": f"{months[-1]}-01", "meta": {"cur_12m": cur12, "field": val_field}})
    except Exception as e:
        log.debug("interest_expense: %s", e)
    # 3) 拍卖认购倍数：10Y（近 3 场最低）与 30Y（最近一场）
    try:
        d = http.get_json(f"{base}/v1/accounting/od/auctions_query", params={"sort": "-auction_date", "page[size]": 120})
        rows = d.get("data") or []
        def b2c_list(sec_type: str, prefixes: tuple[str, ...]) -> list[float]:
            vals = []
            for r in rows:
                if r.get("security_type") != sec_type:
                    continue
                term = str(r.get("security_term") or "")
                if not term.startswith(prefixes):
                    continue
                try:
                    vals.append(float(r["bid_to_cover_ratio"]))
                except (KeyError, TypeError, ValueError):
                    continue
            return vals
        t10 = b2c_list("Note", ("10-", "9-Year 1"))
        t30 = b2c_list("Bond", ("30-", "29-Year"))
        if len(t10) >= 3:
            out.append({"key": "fiscal.auction_10y_b2c_min3", "value": min(t10[:3]), "source": "fiscaldata",
                        "meta": {"last3": t10[:3]}})
        if t30:
            out.append({"key": "fiscal.auction_30y_b2c", "value": t30[0], "source": "fiscaldata"})
    except Exception as e:
        log.debug("auctions_query: %s", e)
    # 4) 债务上限余量（DTS 表 IIIC；单位百万美元）：
    #    受限余额 = 公众持有 + 政府内部 − 不受限各项 + 其他受限项；余量 = 法定上限 − 受限余额
    try:
        d = http.get_json(f"{base}/v1/accounting/dts/debt_subject_to_limit",
                          params={"sort": "-record_date", "page[size]": 40})
        rows = d.get("data") or []
        limit = None
        bal = 0.0
        got = False
        latest_date = rows[0]["record_date"] if rows else None
        for r in rows:
            if r.get("record_date") != latest_date:
                break
            cat = (r.get("debt_catg") or "")
            try:
                v = float(r.get("close_today_bal"))
            except (TypeError, ValueError):
                continue
            if cat == "Statutory Debt Limit":
                limit = v
            elif cat in ("Debt Held by the Public", "Intragovernmental Holdings", "Other Debt Subject to Limit"):
                bal += v
                got = True
            elif cat == "Debt Not Subject to Limit":
                bal -= v
        if limit and got and limit > 1e6:  # 上限暂停期挂 0，跳过
            out.append({"key": "fiscal.limit_headroom", "value": (limit - bal) * 1e6, "source": "fiscaldata",
                        "asof": latest_date, "meta": {"limit_mm": limit, "balance_mm": bal}})
    except Exception as e:
        log.debug("debt_subject_to_limit: %s", e)
    return out


# ---------------- EIA 工业电价同比（数据中心电力缺口）----------------
def fetch_eia_power(http: Http) -> list[dict]:
    key = os.environ.get("EIA_API_KEY", "DEMO_KEY")
    d = http.get_json("https://api.eia.gov/v2/electricity/retail-sales/data/",
                      params={"api_key": key, "frequency": "monthly", "data[0]": "price",
                              "facets[sectorid][]": "IND", "facets[stateid][]": "US",
                              "sort[0][column]": "period", "sort[0][direction]": "desc", "length": 40})
    rows = (d.get("response") or {}).get("data") or []
    monthly = {}
    for r in rows:
        try:
            monthly[str(r["period"])] = float(r["price"])
        except (KeyError, TypeError, ValueError):
            continue
    out = []
    months = sorted(monthly)
    for m in months:
        y, mm = int(m[:4]), m[5:7]
        prev = f"{y - 1}-{mm}"
        if prev in monthly and monthly[prev]:
            out.append({"key": "eia.ind_power_yoy", "value": (monthly[m] / monthly[prev] - 1) * 100, "source": "eia",
                        "date": f"{m}-01", "_backfill": True})
    if months:
        out.append({"key": "eia.ind_power_price", "value": monthly[months[-1]], "source": "eia", "asof": months[-1]})
        if out and out[-1]["key"] != "eia.ind_power_yoy":
            yoys = [x for x in out if x["key"] == "eia.ind_power_yoy"]
            if yoys:
                out.append({"key": "eia.ind_power_yoy", "value": yoys[-1]["value"], "source": "eia", "asof": months[-1]})
    return out


SUBFETCHERS = {
    "portwatch": fetch_portwatch,
    "gpr": fetch_gpr,
    "plavis": fetch_plavis,
    "freight": fetch_freight,
    "treasury_curve": fetch_treasury_curve,
    "nyfed_rates": fetch_nyfed_rates,
    "fiscal_tga": fetch_fiscal_tga,
    "bls_cpi": fetch_bls_cpi,
    "coinmetrics": fetch_coinmetrics,
    "sosovalue_etf": fetch_sosovalue_etf,
    "cg_treasuries": fetch_cg_treasuries,
    "cmc_altseason": fetch_cmc_altseason,
    "mempool": fetch_mempool,
    "ultrasound": fetch_ultrasound,
    "funding": fetch_funding,
    "kalshi_fed": fetch_kalshi_fed,
    "eia_brent_spot": fetch_eia_brent_spot,
    "lbma_gold": fetch_lbma_gold,
    "multpl_cape": fetch_multpl_cape,
    "llama_pm_volume": fetch_llama_pm_volume,
    "cg_categories": fetch_cg_categories,
    "rwa_xyz": fetch_rwa_xyz,
    "govtrack_clarity": fetch_govtrack_clarity,
    "llama_unlocks": fetch_llama_unlocks,
    # 扩展第 1 批（2026-09-21，见 data/raw/expansion_research.json）
    "mof_jgb": fetch_mof_jgb,
    "cftc_cot": fetch_cftc_cot,
    "nrc_power": fetch_nrc_power,
    "fiscal_debt": fetch_fiscal_debt,
    "eia_power": fetch_eia_power,
}


def fetch(cfg: dict, settings: dict) -> dict:
    http = Http(timeout=30, min_interval=0.4)
    metrics: list[dict] = []
    notes = []
    status = {}
    enabled = cfg.get("extras") or list(SUBFETCHERS.keys())
    for name in enabled:
        fn = SUBFETCHERS.get(name)
        if not fn:
            continue
        t0 = time.time()
        try:
            m = fn(http)
            metrics += m
            status[name] = {"ok": True, "n": len(m), "s": round(time.time() - t0, 1)}
        except Exception as e:
            notes.append(f"{name}: {str(e)[:80]}")
            status[name] = {"ok": False, "error": str(e)[:120]}
            log.warning("extras %s: %s", name, e)
    return {"metrics": metrics, "news": [], "notes": "; ".join(notes), "sub_status": status}
