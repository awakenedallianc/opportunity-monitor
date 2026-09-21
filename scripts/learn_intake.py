"""学习摄入（无 LLM 车道）。

从 learning/sources.yaml 抓 RSS/Atom → 去重 → 追加到 learning/inbox/YYYY-MM.jsonl
→ 生成 learning/inbox/digest.json（近 N 天按主题分组）与 status.json（各源健康度）
→ 渲染 docs/learn.html（学习页）。

用法：
  python scripts/learn_intake.py              # 抓取 + 渲染
  python scripts/learn_intake.py --no-render  # 只抓取
  python scripts/learn_intake.py --render-only
  python scripts/learn_intake.py --max-age-days 60 --window-days 14
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import feedparser  # noqa: E402
import requests  # noqa: E402
import yaml  # noqa: E402

from monitor.utils import clean_text, log, setup_logging  # noqa: E402

LEARN = ROOT / "learning"
INBOX = LEARN / "inbox"
UA = "Mozilla/5.0 (compatible; OpportunityMonitor-Learn/1.0; +https://github.com/awakenedallianc/opportunity-monitor)"

# 关键词打标（小写匹配；命中即加 tag）——刻意保持小而稳，避免"看起来聪明"的误标
KEYWORDS: dict[str, list[str]] = {
    "onboarding": ["onboarding", "first-run", "empty state", "新手", "引导"],
    "retention": ["retention", "churn", "habit", "streak", "留存", "复购", "活跃"],
    "notification": ["notification", "digest", "newsletter", "push", "推送", "通知", "邮件"],
    "dashboard": ["dashboard", "chart", "visualization", "visualisation", "看板", "图表", "可视化"],
    "ai-product": ["ai product", "llm", "agent", "copilot", "prompt", "evals", "evaluation", "大模型", "智能体"],
    "ux": ["ux", "usability", "accessibility", "design system", "typography", "体验", "可用性", "设计"],
    "growth": ["growth", "acquisition", "pricing", "monetiz", "增长", "定价", "转化"],
    "finance-product": ["fintech", "brokerage", "trading app", "portfolio", "watchlist", "券商", "行情", "投资"],
    "forecasting": ["forecast", "prediction market", "polymarket", "kalshi", "superforecast", "预测"],
    "data": ["data pipeline", "etl", "api", "open data", "数据源", "数据集"],
}


def _iso(entry) -> str | None:
    for k in ("published_parsed", "updated_parsed", "created_parsed"):
        t = entry.get(k)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc).isoformat()
            except Exception:
                pass
    for k in ("published", "updated"):
        s = entry.get(k)
        if s:
            try:
                return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
            except Exception:
                pass
    return None


def _tags(text: str) -> list[str]:
    t = (text or "").lower()
    return [tag for tag, kws in KEYWORDS.items() if any(k in t for k in kws)]


def load_sources() -> list[dict]:
    d = yaml.safe_load((LEARN / "sources.yaml").read_text(encoding="utf-8")) or {}
    return [s for s in (d.get("sources") or []) if s.get("feed_url") and s.get("enabled", True)]


def existing_ids() -> set[str]:
    ids: set[str] = set()
    for p in INBOX.glob("*.jsonl"):
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                ids.add(json.loads(line)["id"])
            except Exception:
                continue
    return ids


def fetch_one(src: dict, max_age_days: int) -> tuple[dict, list[dict]]:
    name, url = src["name"], src["feed_url"]
    status = {"name": name, "feed_url": url, "ok": False, "items": 0, "new": 0, "last_item": None, "error": None}
    items: list[dict] = []
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"}, timeout=25)
        r.raise_for_status()
        feed = feedparser.parse(r.content)
        if feed.bozo and not feed.entries:
            raise ValueError(f"not a feed ({getattr(feed, 'bozo_exception', '')})")
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        newest = None
        undated = 0
        for e in feed.entries[:80]:
            link = (e.get("link") or "").strip()
            title = clean_text(e.get("title") or "", 200)
            if not title:
                continue
            when = _iso(e)
            if when and (newest is None or when > newest):
                newest = when
            if when and datetime.fromisoformat(when) < cutoff:
                continue
            if not when:
                # 无日期条目绕过时效截断且会被记成"今天"：新启用的源最多收 5 条，避免旧文灌满近 14 天摘要
                undated += 1
                if undated > 5:
                    continue
            summary = clean_text(e.get("summary") or (e.get("content") or [{}])[0].get("value", "") or "", 300)
            iid = hashlib.sha1((link or title).encode("utf-8")).hexdigest()[:16]
            items.append({"id": iid, "date": (when or datetime.now(timezone.utc).isoformat())[:10], "published": when,
                          "source": name, "title": title, "link": link, "summary": summary,
                          "topics": list(src.get("topics") or []), "tags": _tags(title + " " + summary),
                          "lang": src.get("language", "en")})
        status.update(ok=True, items=len(feed.entries), last_item=(newest or "")[:10] or None)
    except Exception as ex:  # 单个源失败不影响其他
        status["error"] = str(ex)[:160]
    return status, items


def intake(max_age_days: int) -> dict:
    INBOX.mkdir(parents=True, exist_ok=True)
    sources = load_sources()
    seen = existing_ids()
    statuses, fresh = [], []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch_one, s, max_age_days): s for s in sources}
        for f in as_completed(futs):
            st, items = f.result()
            new = [it for it in items if it["id"] not in seen]
            for it in new:
                seen.add(it["id"])
                it["first_seen"] = datetime.now(timezone.utc).isoformat()
            st["new"] = len(new)
            statuses.append(st)
            fresh.extend(new)
            log.info("learn %-28s %s items=%s new=%s %s", st["name"][:28], "ok " if st["ok"] else "ERR", st["items"], st["new"], st["error"] or "")
    # 按 first_seen 月份追加
    by_month: dict[str, list[dict]] = {}
    for it in fresh:
        by_month.setdefault(it["first_seen"][:7], []).append(it)
    for month, arr in by_month.items():
        with (INBOX / f"{month}.jsonl").open("a", encoding="utf-8") as fh:
            for it in sorted(arr, key=lambda x: x["date"]):
                fh.write(json.dumps(it, ensure_ascii=False) + "\n")
    statuses.sort(key=lambda s: (not s["ok"], s["name"]))
    summary = {"generated_at": datetime.now(timezone.utc).isoformat(), "sources": len(sources),
               "ok": sum(1 for s in statuses if s["ok"]), "new_items": len(fresh),
               "duration_s": round(time.time() - t0, 1), "status": statuses}
    (INBOX / "status.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("learn intake: %s/%s sources ok, %s new items, %.1fs", summary["ok"], summary["sources"], len(fresh), summary["duration_s"])
    return summary


def build_digest(window_days: int) -> dict:
    """近 window_days 天的条目，按主题分组（一个条目只进第一个主题），供学习页与学习循环使用。"""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).strftime("%Y-%m-%d")
    items: list[dict] = []
    for p in sorted(INBOX.glob("*.jsonl"))[-3:]:
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                it = json.loads(line)
            except Exception:
                continue
            if it.get("date", "") >= cutoff:
                items.append(it)
    items.sort(key=lambda x: (x.get("date", ""), x.get("published") or ""), reverse=True)
    groups: dict[str, list[dict]] = {}
    for it in items:
        key = (it.get("topics") or ["other"])[0]
        groups.setdefault(key, []).append(it)
    for k in groups:
        groups[k] = groups[k][:40]
    tag_counts: dict[str, int] = {}
    for it in items:
        for t in it.get("tags") or []:
            tag_counts[t] = tag_counts.get(t, 0) + 1
    status = {}
    try:
        status = json.loads((INBOX / "status.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    digest = {"generated_at": datetime.now(timezone.utc).isoformat(), "window_days": window_days, "total": len(items),
              "groups": groups, "tag_counts": dict(sorted(tag_counts.items(), key=lambda kv: -kv[1])),
              "sources_ok": status.get("ok"), "sources_total": status.get("sources"),
              "failed_sources": [s["name"] for s in status.get("status", []) if not s.get("ok")]}
    (INBOX / "digest.json").write_text(json.dumps(digest, ensure_ascii=False, indent=1), encoding="utf-8")
    return digest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--render-only", action="store_true")
    ap.add_argument("--max-age-days", type=int, default=60)
    ap.add_argument("--window-days", type=int, default=14)
    a = ap.parse_args()
    setup_logging()
    if not a.render_only:
        intake(a.max_age_days)
    digest = build_digest(a.window_days)
    if not a.no_render:
        from monitor import learn_page
        out = learn_page.render()
        log.info("learn page: %s (%s items in %s days)", out, digest["total"], a.window_days)
    return 0


if __name__ == "__main__":
    sys.exit(main())
