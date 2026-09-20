"""新闻：RSS/Atom 源 + Google News 主题查询（中英）。用关键词把每条新闻打上话题标签并评分。

无 LLM：话题识别靠 config/topics.yaml 的关键词表；评分 = 关键词权重和 + 来源等级加成。
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone, timedelta

import feedparser

from ..utils import Http, clean_text, log, parse_date, sha1

GN = "https://news.google.com/rss/search"


def _compile_topics(topics: dict) -> list[tuple[str, float, list[re.Pattern]]]:
    out = []
    for tid, t in topics.items():
        pats = []
        for kw in t.get("keywords", []):
            # 英文整词匹配（不区分大小写）；中文/含空格短语直接子串匹配
            if re.search(r"[一-鿿]", kw):
                pats.append(re.compile(re.escape(kw)))
            else:
                pats.append(re.compile(r"(?<![A-Za-z0-9])" + re.escape(kw) + r"(?![A-Za-z0-9])", re.I))
        out.append((tid, float(t.get("weight", 1.0)), pats))
    return out


def tag(text: str, compiled) -> tuple[list[str], float]:
    topics, score = [], 0.0
    for tid, w, pats in compiled:
        if any(p.search(text) for p in pats):
            topics.append(tid)
            score += w
    return topics, score


def parse_feed(http: Http, url: str) -> feedparser.FeedParserDict:
    txt = http.get(url, timeout=25)
    txt.raise_for_status()
    return feedparser.parse(txt.content)


def _entry_to_item(e, feed_name: str, lang: str, tier: int, feed_url: str) -> dict | None:
    link = e.get("link") or ""
    title = clean_text(e.get("title"), 300)
    if not title:
        return None
    pub = parse_date(e.get("published") or e.get("updated") or e.get("pubDate"))
    if pub is None and e.get("published_parsed"):
        pub = datetime(*e["published_parsed"][:6], tzinfo=timezone.utc)
    src = feed_name
    if e.get("source") and isinstance(e["source"], dict) and e["source"].get("title"):
        src = e["source"]["title"]
    summ = e.get("summary") or (e.get("content") or [{}])[0].get("value") or ""
    summ = clean_text(summ, 700)
    if src != feed_name and summ.startswith(title):
        summ = summ[len(title):].strip(" -–—")
    return {
        "id": sha1((link or title).split("&utm")[0]),
        "published": pub.astimezone(timezone.utc).isoformat() if pub else None,
        "source": src, "feed": feed_name, "title": title, "link": link,
        "summary": summ, "lang": lang, "tier": tier, "feed_url": feed_url,
    }


def fetch(cfg: dict, settings: dict) -> dict:
    feeds_cfg = cfg.get("feeds", {})
    topics = cfg.get("topics", {})
    compiled = _compile_topics(topics)
    http = Http(timeout=25, retries=1, min_interval=0.4)
    items: list[dict] = []
    notes = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=int(settings.get("news_max_age_days", 10)))
    status = {}

    def ingest(name, url, lang, tier):
        try:
            fp = parse_feed(http, url)
            n = 0
            for e in fp.entries[:80]:
                it = _entry_to_item(e, name, lang, tier, url)
                if not it:
                    continue
                if it["published"] and datetime.fromisoformat(it["published"]) < cutoff:
                    continue
                text = f"{it['title']} {it['summary']}"
                it["topics"], kw_score = tag(text, compiled)
                it["score"] = kw_score + (3 - tier) * 0.5
                items.append(it)
                n += 1
            status[name] = {"ok": True, "n": n}
        except Exception as e:
            status[name] = {"ok": False, "error": str(e)[:120]}
            notes.append(f"{name}: {str(e)[:80]}")
            log.warning("feed %s: %s", name, e)

    for f in feeds_cfg.get("rss", []):
        if f.get("enabled", True):
            ingest(f["name"], f["url"], f.get("lang", "en"), int(f.get("tier", 2)))
    for q in feeds_cfg.get("google_news", []):
        if not q.get("enabled", True):
            continue
        lang = q.get("lang", "en")
        params = "hl=en-US&gl=US&ceid=US:en" if lang == "en" else "hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        from urllib.parse import quote
        url = f"{GN}?q={quote(q['q'])}&{params}"
        ingest(f"GN:{q.get('name') or q['q']}", url, lang, int(q.get("tier", 2)))
        time.sleep(0.2)

    # 去重（同 id 保留评分高者）
    best: dict[str, dict] = {}
    for it in items:
        if it["id"] not in best or it["score"] > best[it["id"]]["score"]:
            best[it["id"]] = it
    return {"metrics": [], "news": list(best.values()), "notes": "; ".join(notes[:15]), "feed_status": status}
