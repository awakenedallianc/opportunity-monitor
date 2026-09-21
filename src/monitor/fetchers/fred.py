"""FRED（圣路易斯联储）：优先官方 API（需免费注册 FRED_API_KEY），无密钥时退回 fredgraph.csv。

2026-09-21 实测 fredgraph.csv 从 GitHub 运行器也连不上（此前只有泰国本机不可达），
所以无密钥时 FRED 系列大概率缺数：利率类有财政部曲线兜底（extras.py + derived.py），
CCC/HY 利差与电气设备订单（BAMLH0A3HYC / A34SUO / A34SNO）暂无兜底，等用户注册密钥后自动恢复。
注册（免费）：https://fred.stlouisfed.org/docs/api/api_key.html → GitHub secret + .env 加 FRED_API_KEY。
"""
from __future__ import annotations

import csv
import io
import os

from ..utils import Http, log

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
API = "https://api.stlouisfed.org/fred/series/observations"


def fetch_series(http: Http, sid: str, key: str) -> list[dict]:
    api_key = os.environ.get("FRED_API_KEY")
    pairs: list[tuple[str, float]] = []
    if api_key:
        d = http.get_json(API, params={"series_id": sid, "api_key": api_key, "file_type": "json",
                                       "sort_order": "desc", "limit": 450}, timeout=60)
        for o in reversed(d.get("observations") or []):
            try:
                pairs.append((o["date"], float(o["value"])))
            except (KeyError, TypeError, ValueError):
                continue
    else:
        txt = http.get_text(URL, params={"id": sid}, timeout=60)
        for r in list(csv.reader(io.StringIO(txt)))[1:]:
            if len(r) < 2 or r[1] in (".", ""):
                continue
            try:
                pairs.append((r[0], float(r[1])))
            except ValueError:
                continue
    out = [{"key": key, "value": v, "source": "fred", "date": d0, "_backfill": True} for d0, v in pairs]
    if pairs:
        out.append({"key": key, "value": pairs[-1][1], "source": "fred", "asof": pairs[-1][0], "meta": {"series": sid}})
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
