"""学习页渲染：learning/*.yaml + learning/log.md + learning/inbox/digest.json → docs/learn.html（纯静态、无 LLM）。"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .utils import DOCS_DIR, log

LEARN_DIR = DOCS_DIR.parent / "learning"
TEMPLATES = Path(__file__).parent / "templates"
STATUS_LABEL = {"candidate": "候选", "planned": "下期做", "building": "在做", "done": "已上线", "dropped": "放弃"}
APPLIES_LABEL = {"ai": "AI 产品", "product": "互联网产品", "ux": "体验", "monitor": "本站", "dataviz": "图表", "growth": "增长"}
TOPIC_LABEL = {"product": "产品", "ai": "AI", "ux": "体验/设计", "growth": "增长", "design": "设计", "china": "中文圈",
               "finance": "金融产品", "dataviz": "数据新闻", "crypto": "加密研究", "macro": "宏观研究", "forecasting": "预测市场",
               "changelog": "产品更新", "engineering": "工程", "other": "其他"}


def feature_score(f: dict) -> int:
    """功能候选打分：价值×2 − 工作量 − (需要大模型?2) − 字多风险 + (免费数据可得?1)。"""
    try:
        return int(round(2 * float(f.get("value", 0)) - float(f.get("effort", 0)) - (2 if f.get("needs_llm") else 0)
                         - float(f.get("risk_words", 0)) + (1 if f.get("data_ok", True) else 0)))
    except Exception:
        return 0


def _yaml(name: str) -> dict:
    p = LEARN_DIR / name
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def md_to_html(md: str) -> str:
    """极简 Markdown：# 标题、- 列表、**粗体**、[文](url)、段落。够用即可，不引新依赖。"""
    out, in_list = [], False
    def inline(s: str) -> str:
        s = html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
        s = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
        return s
    for line in md.splitlines():
        if line.startswith("- ") or line.startswith("* "):
            if not in_list:
                out.append("<ul>"); in_list = True
            out.append(f"<li>{inline(line[2:])}</li>")
            continue
        if in_list:
            out.append("</ul>"); in_list = False
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            lvl = min(len(m.group(1)) + 1, 5)
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
        elif line.strip():
            out.append(f"<p>{inline(line)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def log_entries(limit: int = 3) -> list[dict]:
    p = LEARN_DIR / "log.md"
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8")
    parts = re.split(r"^## ", text, flags=re.M)[1:]
    entries = []
    for part in parts:
        title, _, body = part.partition("\n")
        entries.append({"title": title.strip(), "html": md_to_html(body)})
    return entries[-limit:][::-1]


def render(out: Path | None = None) -> Path:
    kb, bl, src = _yaml("knowledge.yaml"), _yaml("backlog.yaml"), _yaml("sources.yaml")
    lessons = [l for l in (kb.get("lessons") or []) if l.get("title")]
    lessons.sort(key=lambda l: (l.get("rank") or 999, l.get("added") or ""))
    by_area: dict[str, list[dict]] = {}
    for l in lessons:
        by_area.setdefault(APPLIES_LABEL.get(l.get("applies_to"), l.get("applies_to") or "其他"), []).append(l)
    feats = [f for f in (bl.get("features") or []) if f.get("name")]
    for f in feats:
        f["score"] = feature_score(f)
        f["status_label"] = STATUS_LABEL.get(f.get("status"), f.get("status") or "候选")
    order = {"building": 0, "planned": 1, "candidate": 2, "done": 3, "dropped": 4}
    feats.sort(key=lambda f: (order.get(f.get("status"), 2), -f["score"]))
    digest = {}
    try:
        digest = json.loads((LEARN_DIR / "inbox" / "digest.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    groups = [{"key": k, "label": TOPIC_LABEL.get(k, k), "entries": v} for k, v in (digest.get("groups") or {}).items()]
    groups.sort(key=lambda g: -len(g["entries"]))
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(["html", "j2"]))
    tpl = env.get_template("learn.html.j2")
    html_out = tpl.render(
        generated=datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M"),
        lessons_by_area=by_area, n_lessons=len(lessons), feats=feats, done=[f for f in feats if f.get("status") == "done"],
        groups=groups, digest=digest, n_sources=len(src.get("sources") or []), logs=log_entries(),
        kb_updated=kb.get("updated"), bl_updated=bl.get("updated"),
    )
    out = out or (DOCS_DIR / "learn.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_out, encoding="utf-8")
    log.info("learn page written: %s (%.0f KB)", out, len(html_out) / 1024)
    return out
