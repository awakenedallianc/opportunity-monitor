"""规则引擎：把三篇报告里的"入场条件 / 失效信号 / 触发日历 / 敏感关键词"变成可机读规则。

规则定义在 config/rules.yaml，字段：
  id, report, title, level(opportunity|warning|invalidation|info|event), action, source
  when: 单个条件或 all:[...] / any:[...]
条件类型（type）：
  compare   : metric OP value|ref_metric            (OP: gt gte lt lte between)
  change    : metric 在 lookback 天内的百分比变化 OP value
  streak    : 子条件连续 n 天为真（需要历史）
  drawdown  : metric 相对 lookback 天内最高值的回撤(%) OP value（value 为负数）
  date      : 距 date 事件的天数在 [min,max] 之内（用于解锁/事件日历）
  news      : 24h/48h 内命中话题 topic 的独立来源数 >= n
  missing   : metric 缺失或过期 > days 天（数据质量告警）
所有条件在缺数据时返回 None（不触发、不报错），并在结果里记录原因。
"""
from __future__ import annotations

import operator
from datetime import datetime
from typing import Any

from .store import Store
from .utils import log, now_bkk, today_str

OPS = {"gt": operator.gt, "gte": operator.ge, "lt": operator.lt, "lte": operator.le,
       "eq": operator.eq, "ne": operator.ne}


class RuleContext:
    def __init__(self, store: Store, latest: dict[str, dict], news_topic_sources: dict[str, dict[str, int]],
                 today: str | None = None):
        self.store = store
        self.latest = latest  # key -> {value, date, meta, ...}
        self.news_topic_sources = news_topic_sources  # topic -> {"24h": n_sources, "48h": n}
        self.today = today or today_str()

    def value(self, key: str) -> float | None:
        m = self.latest.get(key)
        return None if m is None else m.get("value")

    def date_of(self, key: str) -> str | None:
        m = self.latest.get(key)
        return None if m is None else m.get("date")


def _fmt(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        if abs(v) >= 1000:
            return f"{v:,.0f}"
        return f"{v:.4g}" if abs(v) < 1 else f"{v:,.2f}"
    return str(v)


def eval_condition(c: dict, ctx: RuleContext) -> tuple[bool | None, str]:
    """返回 (是否成立/None=无数据, 说明文本)。"""
    if "all" in c:
        parts = [eval_condition(x, ctx) for x in c["all"]]
        if any(p[0] is None for p in parts):
            return None, "; ".join(p[1] for p in parts)
        return all(p[0] for p in parts), "; ".join(p[1] for p in parts)
    if "any" in c:
        parts = [eval_condition(x, ctx) for x in c["any"]]
        if all(p[0] is None for p in parts):
            return None, "; ".join(p[1] for p in parts)
        return any(p[0] is True for p in parts), "; ".join(p[1] for p in parts)

    t = c.get("type", "compare")
    if t == "compare":
        v = ctx.value(c["metric"])
        if v is None:
            return None, f"{c['metric']} 无数据"
        op = c.get("op", "gt")
        if op == "between":
            lo, hi = c["value"]
            ok = lo <= v <= hi
            return ok, f"{c.get('label', c['metric'])}={_fmt(v)} ∈ [{_fmt(lo)},{_fmt(hi)}]" if ok else f"{c.get('label', c['metric'])}={_fmt(v)} ∉ [{_fmt(lo)},{_fmt(hi)}]"
        if "ref_metric" in c:
            ref = ctx.value(c["ref_metric"])
            if ref is None:
                return None, f"{c['ref_metric']} 无数据"
            ref = ref * float(c.get("ref_mult", 1.0))
            ok = OPS[op](v, ref)
            return ok, f"{c.get('label', c['metric'])}={_fmt(v)} {op} {c.get('ref_label', c['ref_metric'])}={_fmt(ref)}"
        ref = float(c["value"])
        ok = OPS[op](v, ref)
        return ok, f"{c.get('label', c['metric'])}={_fmt(v)} {op} {_fmt(ref)}"

    if t == "change":
        key = c["metric"]
        lookback = int(c.get("lookback", 30))
        cur = ctx.value(key)
        if cur is None:
            return None, f"{key} 无数据"
        from datetime import timedelta
        d0 = (now_bkk() - timedelta(days=lookback)).strftime("%Y-%m-%d")
        prev = ctx.store.value_on_or_before(key, d0)
        if prev in (None, 0):
            return None, f"{key} {lookback}天前无数据"
        if prev < 0 or cur < 0:  # 可为负的指标（价差、净流入等）不用百分比变化
            return None, f"{key} 为负值，百分比变化无意义"
        ch = (cur / prev - 1) * 100
        ok = OPS[c.get("op", "gt")](ch, float(c["value"]))
        return ok, f"{c.get('label', key)} {lookback}天变化 {ch:+.1f}% {c.get('op','gt')} {c['value']}%"

    if t == "drawdown":
        key = c["metric"]
        lookback = int(c.get("lookback", 365))
        cur = ctx.value(key)
        s = ctx.store.series(key, lookback)
        if cur is None or not s:
            return None, f"{key} 无数据"
        peak = max(v for _, v in s)
        if c.get("peak_override") and float(c["peak_override"]) > peak:
            peak = float(c["peak_override"])
        dd = (cur / peak - 1) * 100 if peak else None
        if dd is None:
            return None, f"{key} 无峰值"
        ok = OPS[c.get("op", "lt")](dd, float(c["value"]))
        return ok, f"{c.get('label', key)} 较峰值回撤 {dd:.1f}% {c.get('op','lt')} {c['value']}%"

    if t == "streak":
        # 连续 n 个日期都满足子条件 —— 用历史序列近似（仅支持 compare 子条件）
        sub = c["condition"]
        n = int(c.get("n", 2))
        key = sub["metric"]
        s = ctx.store.series(key, n + 5)
        if len(s) < n:
            return None, f"{key} 历史不足 {n} 天"
        vals = [v for _, v in s[-n:]]
        if "ref_metric" in sub:
            refs = ctx.store.series(sub["ref_metric"], n + 5)
            if len(refs) < n:
                return None, f"{sub['ref_metric']} 历史不足"
            refv = [v for _, v in refs[-n:]]
            oks = [OPS[sub.get("op", "gt")](a, b) for a, b in zip(vals, refv)]
        else:
            oks = [OPS[sub.get("op", "gt")](a, float(sub["value"])) for a in vals]
        return all(oks), f"{sub.get('label', key)} 连续{n}天 {sub.get('op')} : {sum(oks)}/{n}"

    if t == "date":
        ev = datetime.strptime(c["date"], "%Y-%m-%d").date()
        today = datetime.strptime(ctx.today, "%Y-%m-%d").date()
        delta = (ev - today).days
        lo, hi = c.get("range", [0, 7])
        ok = lo <= delta <= hi
        return ok, f"距 {c['date']} 还有 {delta} 天"

    if t == "news":
        topic = c["topic"]
        window = c.get("window", "24h")
        n = int(c.get("min_sources", 2))
        hits = ctx.news_topic_sources.get(topic, {}).get(window, 0)
        return hits >= n, f"话题「{topic}」{window} 内 {hits} 家独立来源（阈值 {n}）"

    if t == "missing":
        key = c["metric"]
        m = ctx.latest.get(key)
        days = int(c.get("days", 3))
        if m is None:
            return True, f"{key} 从未获取"
        try:
            d = datetime.strptime(m["date"], "%Y-%m-%d").date()
            today = datetime.strptime(ctx.today, "%Y-%m-%d").date()
            age = (today - d).days
            return age > days, f"{key} 最近数据 {m['date']}（{age} 天前）"
        except Exception:
            return None, f"{key} 日期无法解析"

    return None, f"未知条件类型 {t}"


def evaluate_rules(rules: list[dict], ctx: RuleContext) -> list[dict]:
    """返回所有规则的评估结果（含未触发与无数据），供前端展示"条件仪表盘"。"""
    out = []
    for r in rules:
        try:
            ok, why = eval_condition(r["when"], ctx)
        except Exception as e:  # 单条规则出错不影响其他
            log.warning("rule %s error: %s", r.get("id"), e)
            ok, why = None, f"评估错误: {e}"
        out.append({
            "rule_id": r["id"],
            "report": r.get("report"),
            "title": r.get("title"),
            "level": r.get("level", "info"),
            "action": r.get("action"),
            "source": r.get("source"),
            "assets": r.get("assets", []),
            "fired": ok is True,
            "status": "fired" if ok is True else ("nodata" if ok is None else "idle"),
            "why": why,
            "priority": int(r.get("priority", 3)),
            "when": r.get("when"),              # 原始条件（仅供前端展示阈值/画条，不参与评估）
            "metric_keys": _metric_keys(r.get("when")),
        })
    return out


def _metric_keys(cond: Any) -> list[str]:
    """收集条件里引用的指标键（前端抽屉据此画曲线）。"""
    keys: list[str] = []
    if isinstance(cond, dict):
        for k in ("metric", "ref_metric"):
            if cond.get(k):
                keys.append(cond[k])
        for k in ("all", "any"):
            for sub in cond.get(k, []) or []:
                keys += _metric_keys(sub)
        if cond.get("condition"):
            keys += _metric_keys(cond["condition"])
    return list(dict.fromkeys(keys))
