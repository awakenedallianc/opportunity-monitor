"""主流程：抓取 → 入库 → 派生 → 规则评估 → 基线对比 → 生成静态站点。

用法：
  python run.py                 # 全量
  python run.py --only crypto,yahoo
  python run.py --skip news
  python run.py --build-only    # 不抓取，仅用库中数据重新生成页面
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone

from . import derived, fetchers, site
from .rules import RuleContext, evaluate_rules
from .store import Store
from .utils import (BKK, CONFIG_DIR, DATA_DIR, DOCS_DIR, log, now_iso, read_yaml, setup_logging, today_str,
                    write_json)


def load_config() -> tuple[dict, dict]:
    settings = read_yaml(CONFIG_DIR / "settings.yaml") or {}
    watch = read_yaml(CONFIG_DIR / "watchlist.yaml") or {}
    cfg = dict(watch)
    cfg["feeds"] = read_yaml(CONFIG_DIR / "feeds.yaml") or {}
    cfg["topics"] = (read_yaml(CONFIG_DIR / "topics.yaml") or {}).get("topics", {})
    cfg["rules"] = (read_yaml(CONFIG_DIR / "rules.yaml") or {}).get("rules", [])
    cfg["calendar"] = (read_yaml(CONFIG_DIR / "calendar.yaml") or {}).get("events", [])
    p = CONFIG_DIR / "baseline.yaml"
    cfg["baseline"] = ((read_yaml(p) or {}).get("claims", []) if p.exists() else [])
    p = CONFIG_DIR / "static.yaml"
    cfg["static"] = read_yaml(p) if p.exists() else {}
    p = CONFIG_DIR / "lines.yaml"
    cfg["lines"] = ((read_yaml(p) or {}).get("lines", []) if p.exists() else [])
    return settings, cfg


CHECKPOINT = DATA_DIR / "checkpoint.json"


def load_checkpoint() -> dict:
    from .utils import read_json
    # 不按日期作废：--resume 的判断本来就按条目时间戳的小时数算，按日作废会让跨午夜的中断续跑失效
    cp = read_json(CHECKPOINT, {}) or {}
    cp.setdefault("fetchers", {})
    cp["date"] = today_str()
    return cp


def save_checkpoint(cp: dict) -> None:
    write_json(CHECKPOINT, cp, indent=1)


def run_fetchers(cfg: dict, settings: dict, only: set[str] | None, skip: set[str], store: Store,
                 resume_within_h: float | None = None) -> tuple[int, dict, dict]:
    """逐个抓取并**立即落库**（断点记录）：中断后用 --resume 跳过近 N 小时内已完成的抓取器。"""
    status, extra = {}, {}
    news_new_total = 0
    cp = load_checkpoint()
    for name in fetchers.FETCHERS:
        if (only and name not in only) or name in skip:
            status[name] = {"ok": None, "skipped": True}
            continue
        done_at = (cp.get("fetchers") or {}).get(name)
        if resume_within_h and done_at:
            try:
                age_h = (datetime.now(BKK) - datetime.fromisoformat(done_at)).total_seconds() / 3600
            except Exception:
                age_h = 1e9
            if age_h <= resume_within_h:
                status[name] = {"ok": None, "skipped": True, "resumed_from": done_at}
                log.info("fetcher %s skipped (checkpoint %.1fh ago)", name, age_h)
                continue
        t0 = time.time()
        try:
            mod = fetchers.load(name)
            res = mod.fetch(cfg, settings)
            m = res.get("metrics", [])
            n = res.get("news", [])
            m.sort(key=lambda r: 0 if r.get("_backfill") else 1)  # 先回填后当前值
            stored = store.put_metrics(m)
            new_n, _ = store.put_news(n)
            news_new_total += new_n
            status[name] = {"ok": True, "metrics": len([x for x in m if not x.get("_backfill")]),
                            "backfill": len([x for x in m if x.get("_backfill")]), "news": len(n), "news_new": new_n,
                            "stored_rows": stored, "seconds": round(time.time() - t0, 1), "notes": res.get("notes", "")}
            if res.get("feed_status"):
                extra["feed_status"] = res["feed_status"]
            if res.get("sub_status"):
                status[name]["sub_status"] = res["sub_status"]
            cp.setdefault("fetchers", {})[name] = now_iso()
            save_checkpoint(cp)
            log.info("fetcher %s ok: %s", name, {k: v for k, v in status[name].items() if k != "sub_status"})
        except Exception as e:
            status[name] = {"ok": False, "error": str(e)[:300], "seconds": round(time.time() - t0, 1)}
            log.exception("fetcher %s failed", name)
    return news_new_total, status, extra


def news_topic_source_counts(store: Store) -> dict[str, dict[str, int]]:
    now = datetime.now(timezone.utc)
    out: dict[str, dict[str, set]] = {}
    for it in store.news_since((now - timedelta(hours=48)).isoformat()):
        pub = it.get("published") or it.get("first_seen")
        try:
            d = datetime.fromisoformat(pub)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        age_h = (now - d).total_seconds() / 3600
        for t in it.get("topics", []):
            s = out.setdefault(t, {"24h": set(), "48h": set()})
            s["48h"].add(it.get("source"))
            if age_h <= 24:
                s["24h"].add(it.get("source"))
    return {t: {"24h": len(v["24h"]), "48h": len(v["48h"])} for t, v in out.items()}


def build_baseline(cfg: dict, latest: dict) -> list[dict]:
    out = []
    for c in cfg.get("baseline", []):
        m = latest.get(c.get("metric", ""))
        now_v = None if m is None else m.get("value")
        base = c.get("baseline_value")
        chg = pts = None
        try:
            if now_v is not None and base is not None:
                if c.get("fmt") in ("pct", "num"):
                    pts = float(now_v) - float(base)
                elif float(base) != 0:
                    chg = (float(now_v) / float(base) - 1) * 100
        except Exception:
            chg = pts = None
        out.append({**c, "now": now_v, "now_date": None if m is None else m.get("date"), "change_pct": chg, "change_pts": pts})
    return out


def build_calendar(cfg: dict) -> list[dict]:
    today = datetime.strptime(today_str(), "%Y-%m-%d").date()
    out = []
    for e in cfg.get("calendar", []):
        try:
            d = datetime.strptime(e["date"], "%Y-%m-%d").date()
        except Exception:
            continue
        out.append({**e, "days_to": (d - today).days})
    out.sort(key=lambda x: x["date"])
    return out


def build_series(store: Store, latest: dict, settings: dict) -> dict[str, list]:
    prefixes = settings.get("series_prefixes", ["px.", "crypto.", "stable.", "fees30d.", "rev30d.", "tvl.", "pm.",
                                                "fred.", "ust.", "chainrev30d.", "chainfees30d.", "ratio.", "dd_ath."])
    days = int(settings.get("series_days", 400))
    series = {}
    for key in latest:
        if any(key.startswith(p) for p in prefixes):
            s = store.series(key, days)
            if len(s) >= 2:
                series[key] = [[d, round(v, 6) if abs(v) < 1 else round(v, 3)] for d, v in s]
    return series


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--skip", default="")
    ap.add_argument("--build-only", action="store_true")
    ap.add_argument("--import-only", action="store_true", help="仅从 data/snapshots 与 data/news_archive 重建历史库")
    ap.add_argument("--resume", action="store_true", help="断点续跑：跳过 data/checkpoint.json 中近 N 小时内已完成的抓取器")
    args = ap.parse_args(argv)
    setup_logging()
    t0 = time.time()
    settings, cfg = load_config()
    store = Store()
    snap_dir, arch_dir = DATA_DIR / "snapshots", DATA_DIR / "news_archive"
    if args.import_only or store.is_empty():
        if snap_dir.exists() and any(snap_dir.glob("*.json")):
            stats = store.import_from_files(snap_dir, arch_dir)
            log.info("imported history from tracked files: %s", stats)
        if args.import_only:
            print(json.dumps({"ok": True, "imported": True}))
            return 0
    only = set(x for x in args.only.split(",") if x) or None
    skip = set(x for x in args.skip.split(",") if x)

    status, extra, news_new = {}, {}, 0
    if not args.build_only:
        news_new, status, extra = run_fetchers(cfg, settings, only, skip, store,
                                               resume_within_h=float(settings.get("resume_within_hours", 3)) if args.resume else None)
        if extra.get("feed_status") and status.get("news"):
            status["news"]["feed_status"] = extra["feed_status"]
    # 被跳过 / 未运行的抓取器：沿用最近一次实际运行的状态（页面"数据"页据此显示）
    prev_runs = store.last_runs(20)
    for name in fetchers.FETCHERS:
        if status.get(name, {}).get("ok") is None:
            for r in prev_runs:
                s = (r.get("status") or {}).get(name)
                if s and s.get("ok") is not None:
                    status[name] = {**s, "stale_from": r.get("run_at")}
                    break
            else:
                status.setdefault(name, {"ok": None, "skipped": True})
    if not extra.get("feed_status"):
        fs = (status.get("news") or {}).get("feed_status")
        if fs:
            extra["feed_status"] = fs
    # 派生指标（build-only 也重算，便于改公式后直接重建页面）
    latest = store.latest_all()
    d = derived.compute(latest, cfg)
    store.put_metrics(d)
    ds = derived.compute_series(store)
    ds.sort(key=lambda r: 0 if r.get("_backfill") else 1)
    store.put_metrics(ds)
    log.info("derived %d metrics + %d series rows", len(d), len(ds))

    latest = store.latest_all()
    topic_counts = news_topic_source_counts(store)
    ctx = RuleContext(store, latest, topic_counts)
    results = evaluate_rules(cfg["rules"], ctx)
    fired = [r for r in results if r["fired"]]
    store.put_alerts(fired)
    today = today_str()
    for r in results:
        r["first_fired"] = store.alert_first_fired(r["rule_id"], today) if r["fired"] else None
        r["is_new"] = bool(r["fired"] and r["first_fired"] == today)
    log.info("rules: %d fired / %d total", len(fired), len(results))

    since = (datetime.now(timezone.utc) - timedelta(days=int(settings.get("news_keep_days", 7)))).isoformat()
    news_items = store.news_since(since, limit=int(settings.get("news_max_items", 600)))
    news_items.sort(key=lambda x: (x.get("published") or x.get("first_seen") or ""), reverse=True)
    calendar_rows = build_calendar(cfg)
    # 可选：Jev（判断模型，只回概率）给新闻打信号分、给日历事件打重要度；未配置密钥时完全不生效
    try:
        from . import jev
        ctx = "三条推演主线：加密三年周期（BTC/ETH/稳定币/监管）、AI 时代十年（算力/电力/半导体/估值）、大国战争风险（台海/中东/俄乌/能源与航运），以及宏观（美联储/财政/美元体系）。"
        cand = [n for n in news_items if (n.get("tier") or 3) <= 2 and n.get("topics")][:40]
        scores = jev.score_news(cand, ctx)
        if scores:
            for n in news_items:
                if n["id"] in scores:
                    n["jev_score"] = round(scores[n["id"]], 3)
        upcoming = [e for e in calendar_rows if 0 <= e.get("days_to", -1) <= 90][:30]
        imps = jev.score_events(upcoming, ctx)
        if imps:
            for i, e in enumerate(upcoming):
                if i in imps:
                    e["jev_imp"] = round(imps[i], 3)
    except Exception as e:
        log.warning("jev scoring skipped: %s", e)

    # 页面用的 fetchers 视图去掉内嵌的 feed_status（前端只读顶层 run.feed_status；不去重会在页面/快照里重复两份）
    fetchers_view = {k: ({kk: vv for kk, vv in v.items() if kk != "feed_status"} if isinstance(v, dict) else v)
                     for k, v in status.items()}
    payload = {
        "generated_at": now_iso(),
        "date": today,
        "run": {"fetchers": fetchers_view, "feed_status": extra.get("feed_status", {}), "news_new": news_new,
                "duration_s": round(time.time() - t0, 1)},
        "metrics": latest,
        "series": build_series(store, latest, settings),
        "rules": results,
        "alerts_history": store.alerts_history(120),
        "calendar": calendar_rows,
        "baseline": build_baseline(cfg, latest),
        "news": news_items,
        "topic_counts": topic_counts,
        "watch": {k: cfg.get(k) for k in ("crypto", "yahoo", "groups", "polymarket", "anchors")},
        "topics": {k: {"label": v.get("label", k), "report": v.get("report"), "weight": v.get("weight", 1)}
                   for k, v in cfg["topics"].items()},
        "reports": settings.get("reports", []),
        "static": cfg.get("static", {}),
        "lines": cfg.get("lines", []),
        # 可用 K 线清单（docs/data/kline/*.json，抓取时生成）：前端只对清单内的标的发请求
        "kline_keys": sorted(p.stem for p in (DOCS_DIR / "data" / "kline").glob("*.json")) if (DOCS_DIR / "data" / "kline").exists() else [],
        # 运行记录只留前端用到的字段（内嵌 30 次完整状态会把 feed_status/sub_status 重复 30 份塞进页面）
        "runs": [{"run_at": r.get("run_at"), "duration_s": r.get("duration_s"),
                  "status": {k: {"ok": v.get("ok"), "skipped": v.get("skipped", False)}
                             for k, v in (r.get("status") or {}).items() if isinstance(v, dict)}}
                 for r in store.last_runs(30)],
    }
    # 输出
    write_json(DOCS_DIR / "data" / "latest.json", payload)
    snap = {k: payload[k] for k in ("generated_at", "date", "metrics", "rules", "calendar", "baseline", "topic_counts", "run")}
    # 每日提交的快照不需要 146 个新闻源的状态：去掉后每个每日提交小一大截
    snap["run"] = {**payload["run"], "feed_status": {}}
    write_json(DATA_DIR / "snapshots" / f"{today}.json", snap)
    try:
        store.export_news_archive(arch_dir)
    except Exception as e:
        log.warning("news archive export failed: %s", e)
    site.render(payload)
    try:
        from . import learn_page
        learn_page.render()
    except Exception as e:  # 学习页缺失不影响主站
        log.warning("learn page skipped: %s", e)
    store.put_run(time.time() - t0, status)
    log.info("done in %.1fs", time.time() - t0)
    print(json.dumps({"ok": True, "date": today, "fired": len(fired), "news_new": news_new,
                      "duration_s": round(time.time() - t0, 1)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
