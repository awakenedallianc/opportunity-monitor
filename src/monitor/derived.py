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

    return out
