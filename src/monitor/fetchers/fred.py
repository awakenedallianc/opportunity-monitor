"""FRED（圣路易斯联储）：无需密钥的 fredgraph.csv 通道。本机曾出现超时，故设长超时并允许失败。

备用：美国财政部每日收益率曲线 XML（extras.py）。
"""
from __future__ import annotations

import csv
import io

from ..utils import Http, log

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def fetch_series(http: Http, sid: str, key: str) -> list[dict]:
    txt = http.get_text(URL, params={"id": sid}, timeout=60)
    rows = list(csv.reader(io.StringIO(txt)))
    out = []
    last = None
    for r in rows[1:]:
        if len(r) < 2 or r[1] in (".", ""):
            continue
        try:
            v = float(r[1])
        except ValueError:
            continue
        out.append({"key": key, "value": v, "source": "fred", "date": r[0], "_backfill": True})
        last = (r[0], v)
    if last:
        out.append({"key": key, "value": last[1], "source": "fred", "asof": last[0], "meta": {"series": sid}})
    return out[-450:]


def fetch(cfg: dict, settings: dict) -> dict:
    """带熔断：第一条序列在 25s 内拿不到就判定 FRED 不可达（泰国网络常见），跳过其余序列。"""
    http = Http(timeout=25, retries=0, min_interval=1.0)
    metrics: list[dict] = []
    notes = []
    failures = 0
    for i, s in enumerate(cfg.get("fred", [])):
        try:
            metrics += fetch_series(http, s["id"], s["key"])
            failures = 0
        except Exception as e:
            failures += 1
            notes.append(f"{s['id']}: {str(e)[:60]}")
            log.warning("fred %s: %s", s["id"], e)
            if failures >= 2 or (i == 0):
                notes.append("FRED 不可达，已熔断（财政部曲线兜底）")
                break
    return {"metrics": metrics, "news": [], "notes": "; ".join(notes)}
