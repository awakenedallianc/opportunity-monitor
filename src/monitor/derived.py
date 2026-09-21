"""派生指标：由原始指标计算出报告逻辑里真正用到的比率/回撤/估值。"""
from __future__ import annotations

from typing import Any


def _v(latest: dict[str, dict], key: str) -> float | None:
    m = latest.get(key)
    return None if m is None else m.get("value")


def compute(latest: dict[str, dict], watch: dict[str, Any]) -> list[dict]:
    out: list[dict] = []

    def add(key: str, value: float | None, meta: dict | None = None, source: str = "derived"):
        if value is not None:
            out.append({"key": key, "value": float(value), "source": source, "meta": meta})

    btc, eth, sol = _v(latest, "px.BTC"), _v(latest, "px.ETH"), _v(latest, "px.SOL")
    if btc and eth:
        add("crypto.ethbtc", eth / btc)
    if btc and sol:
        add("crypto.solbtc", sol / btc)

    # 报告基准 ATH（数据源窗口不足时用报告值兜底）
    anchors = watch.get("anchors", {})
    for key, cfg in anchors.items():
        cur = _v(latest, f"px.{key}")
        peak = cfg.get("ath")
        hi = _v(latest, f"hi52w.{key}")
        if cur and peak:
            if hi and hi > peak:
                peak = hi
            add(f"dd_ath.{key}", (cur / peak - 1) * 100, {"ath": peak, "note": cfg.get("note")})
        base = cfg.get("prewar")
        if cur and base:
            add(f"vs_prewar.{key}", (cur / base - 1) * 100, {"prewar": base})

    # 估值：市值 / 年化费用（P/F）与市值 / 年化收入（P/S）
    for c in watch.get("crypto", []):
        sym = c["symbol"]
        mcap = _v(latest, f"mcap.{sym}")
        f30 = _v(latest, f"fees30d.{sym}")
        r30 = _v(latest, f"rev30d.{sym}")
        if mcap and f30 and f30 > 0:
            add(f"pf.{sym}", mcap / (f30 * 12.17))
        if mcap and r30 and r30 > 0:
            add(f"ps.{sym}", mcap / (r30 * 12.17))

    # HYPE：97% 手续费回购 → 年化回购/市值
    mcap_h, f30_h, fdv_h = _v(latest, "mcap.HYPE"), _v(latest, "fees30d.HYPE"), _v(latest, "fdv.HYPE")
    if mcap_h and f30_h:
        add("crypto.hype.buyback_yield", f30_h * 12.17 * 0.97 / mcap_h * 100,
            {"circ_source": "coingecko", "circ": _v(latest, "circ.HYPE"), "note": "流通量口径各家差异大（CoinGecko 2.2 亿 vs 其他 3.3–3.9 亿）",
             "fdv_yield_pct": (f30_h * 12.17 * 0.97 / fdv_h * 100) if fdv_h else None})

    # 市场宽度：SPY 与等权 RSP 的 30 日差
    spy, rsp = _v(latest, "chg30d.SPY"), _v(latest, "chg30d.RSP")
    if spy is not None and rsp is not None:
        add("ai.breadth_gap_30d", spy - rsp)

    # 稳定币：USDe 相对 75 亿回购阈值的进度
    usde = _v(latest, "stable.USDe")
    if usde:
        add("crypto.usde_vs_threshold", usde / 7.5e9 * 100)

    # 黄金/白银比、油金比
    gold, silver, brent = _v(latest, "px.GOLD"), _v(latest, "px.SILVER"), _v(latest, "px.BRENT")
    if gold and silver:
        add("ratio.gold_silver", gold / silver)
    if gold and brent:
        add("ratio.gold_oil", gold / brent)
    # BTC/黄金
    if btc and gold:
        add("ratio.btc_gold", btc / gold)

    # 10Y 名义 - 盈亏平衡 = 实际收益率近似（若 FRED DFII10 缺失）
    n10, be10 = _v(latest, "fred.DGS10"), _v(latest, "fred.T10YIE")
    if n10 is not None and be10 is not None and _v(latest, "fred.DFII10") is None:
        add("fred.real10y_approx", n10 - be10)

    # FRED 不可达时的兜底：用财政部曲线填充同义键
    for src, dst in (("ust.10y", "fred.DGS10"), ("ust.2y", "fred.DGS2"), ("ust.real10y", "fred.DFII10"), ("ust.breakeven10y", "fred.T10YIE")):
        if _v(latest, dst) is None and _v(latest, src) is not None:
            add(dst, _v(latest, src), {"fallback": src}, source="treasury.gov")

    # 布伦特实物现货 − 期货 = 物理中断溢价
    spot = _v(latest, "eia.brent_spot")
    if spot and brent:
        add("war.brent_physical_premium", spot - brent, {"spot": spot, "futures": brent})

    # BTC 价格 / 实现价格
    rp = _v(latest, "crypto.btc.realized_price")
    if btc and rp:
        add("crypto.btc.price_vs_realized", (btc / rp - 1) * 100)

    # 联邦基金期货隐含利率（近月）
    zq = _v(latest, "px.FEDFUNDS_FUT")
    if zq:
        add("fed.implied_front", 100 - zq, {"symbol": "ZQ=F"})

    # 离岸-在岸人民币价差（正=离岸承压/资金外流；负=回流）
    cnh, cny = _v(latest, "px.CNH"), _v(latest, "px.USDCNY")
    if cnh is not None and cny is not None:
        add("fx.cnh_cny_spread", cnh - cny)

    # SOFR − EFFR 价差（回购压力温度计）
    sofr, effr = _v(latest, "fed.sofr"), _v(latest, "fed.effr")
    if sofr is not None and effr is not None:
        add("fed.sofr_effr_spread", sofr - effr)

    return out


# 需要历史序列的派生：比值回填 + 比值的 200 日线（供「站上/跌破 200 日线」类规则）
RATIOS = [
    ("ratio.copper_gold", "px.COPPER", "px.GOLD"),   # 铜金比：实物需求 vs 恐惧
    ("ratio.hyg_lqd", "px.HYG", "px.LQD"),           # 高收益/投资级：信用分层
    ("ratio.hyg_ief", "px.HYG", "px.IEF"),           # 高收益/国债：信用趋势
    ("ratio.vix_term", "px.VIX", "px.VIX3M"),        # VIX 期限结构：>1 倒挂=危机模式
    ("ratio.ceg_spx", "px.CEG", "px.SPX"),           # 发电商相对大盘：缺电定价权
    ("ratio.ceg_xlu", "px.CEG", "px.XLU"),           # 发电商相对公用事业：AI 电力叙事
    ("ratio.gev_spx", "px.GEV", "px.SPX"),           # 电网设备相对大盘
    # 第 2 批
    ("ratio.emb_ief", "px.EMB", "px.IEF"),           # EM 主权债利差代理（危机总闸门）
    ("ratio.qqq_qqew", "px.QQQ", "px.QQEW"),         # 纳指集中度（顶部结构）
    ("ratio.ura_spx", "px.URA", "px.SPX"),           # 铀矿相对大盘
    ("ratio.crland_hsi", "px.CRLAND", "px.HSI"),     # 地产幸存者相对恒指
    ("ratio.gold_silver", "px.GOLD", "px.SILVER"),   # 金银比（回填版，compute() 的当日值与此一致）
]


def compute_series(store) -> list[dict]:
    out: list[dict] = []
    for key, a, b in RATIOS:
        sa, sb = dict(store.series(a, 420)), dict(store.series(b, 420))
        days = sorted(set(sa) & set(sb))
        vals = [(d, sa[d] / sb[d]) for d in days if sb[d]]
        if not vals:
            continue
        out += [{"key": key, "value": v, "date": d, "source": "derived", "_backfill": True} for d, v in vals]
        d_last, v_last = vals[-1]
        out.append({"key": key, "value": v_last, "source": "derived", "asof": d_last})
        if len(vals) >= 200:
            out.append({"key": f"sma200.{key}", "value": sum(v for _, v in vals[-200:]) / 200,
                        "source": "derived", "asof": d_last})
    # CFTC 日元净头寸 4 周变化（净头寸可为负，change 型规则不适用，这里直接算差值）
    s = store.series("cftc.jpy_net", 90)
    if len(s) >= 5:
        out.append({"key": "cftc.jpy_net_chg4w", "value": s[-1][1] - s[-5][1], "source": "derived", "asof": s[-1][0]})

    # ---- 第 2 批派生 ----
    # CNH 20/60 日均线（人民币趋势判断；现汇 CNH=X 无历史，用期货 CNH=F 序列）
    s = store.series("px.CNHF", 120)
    if len(s) >= 60:
        vals = [v for _, v in s]
        out.append({"key": "fx.cnh_ma20", "value": sum(vals[-20:]) / 20, "source": "derived", "asof": s[-1][0]})
        out.append({"key": "fx.cnh_ma60", "value": sum(vals[-60:]) / 60, "source": "derived", "asof": s[-1][0]})
    # SOFR−EFFR 尖峰计数（近 21 个交易日 >10bp 的天数；2019-09 回购危机同款前兆）
    sofr = dict(store.series("fed.sofr", 60))
    effr = dict(store.series("fed.effr", 60))
    common = sorted(set(sofr) & set(effr))[-21:]
    if len(common) >= 10:
        n = sum(1 for d in common if sofr[d] - effr[d] > 0.10)
        out.append({"key": "fed.sofr_spikes_1m", "value": float(n), "source": "derived", "asof": common[-1]})
    # SOMA 4 周变化（≥0 = QT 实质结束）
    s = store.series("fed.soma_total", 60)
    if len(s) >= 5:
        out.append({"key": "fed.soma_chg4w", "value": s[-1][1] - s[-5][1], "source": "derived", "asof": s[-1][0]})
    # 星座在轨数 90 天净增（绝对差）
    for key, dst in (("space.starlink_count", "space.starlink_chg90"), ("space.kuiper_count", "space.kuiper_chg90"),
                     ("space.asts_count", "space.asts_chg90")):
        s = store.series(key, 120)
        if len(s) >= 2:
            base = next((v for d, v in s if d <= (datetime_shift(s[-1][0], -90))), s[0][1])
            out.append({"key": dst, "value": s[-1][1] - base, "source": "derived", "asof": s[-1][0]})
    # 金价与 10Y 实际收益率的 60 日日度变化相关性（>0 = 负相关失效 = 换锚信号）
    g = dict(store.series("px.GOLD", 150))
    r = dict(store.series("ust.real10y", 150))
    common = sorted(set(g) & set(r))
    if len(common) >= 61:
        dg = [g[common[i]] - g[common[i - 1]] for i in range(1, len(common))][-60:]
        dr = [r[common[i]] - r[common[i - 1]] for i in range(1, len(common))][-60:]
        n = len(dg)
        mg, mr = sum(dg) / n, sum(dr) / n
        cov = sum((a - mg) * (b - mr) for a, b in zip(dg, dr))
        vg = sum((a - mg) ** 2 for a in dg) ** 0.5
        vr = sum((b - mr) ** 2 for b in dr) ** 0.5
        if vg and vr:
            out.append({"key": "dedollar.gold_realrate_corr60", "value": cov / (vg * vr), "source": "derived",
                        "asof": common[-1], "meta": {"note": "60 日日度变化相关性；正常 <-0.3，>0=央行购金主导定价"}})
    return out


def datetime_shift(date_str: str, days: int) -> str:
    from datetime import datetime as _dt, timedelta as _td
    return (_dt.strptime(date_str, "%Y-%m-%d") + _td(days=days)).strftime("%Y-%m-%d")
