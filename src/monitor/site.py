"""静态站点生成：把 payload 内联进单文件 index.html（双击即可离线打开，也可托管在 GitHub Pages）。"""
from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .utils import DOCS_DIR, log

TEMPLATES = Path(__file__).resolve().parent / "templates"


def _fmt_big(x, unit=""):
    # 与 app.js fmtBig 同一套舍入，避免 now.html 与主站显示不一致
    if x is None:
        return "—"
    a = abs(x)
    if a >= 1e12:
        return f"{unit}{x / 1e12:.2f} 万亿"
    if a >= 1e8:
        return f"{unit}{x / 1e8:.0f} 亿" if a >= 1e10 else f"{unit}{x / 1e8:.1f} 亿"
    if a >= 1e4:
        return f"{unit}{x / 1e4:.0f} 万" if a >= 1e6 else f"{unit}{x / 1e4:.2f} 万"
    if a >= 1000:
        return f"{unit}{x:.0f}"
    if a >= 100:
        return f"{unit}{x:.1f}"
    if a >= 1:
        return f"{unit}{x:.2f}"
    return f"{unit}{x:.4f}"


def write_ics(payload: dict, out_dir: Path) -> Path:
    """未来 90 天的关键日子 → docs/calendar.ics（全天事件，前一天 09:00 提醒）。"""
    import hashlib
    from datetime import datetime, timedelta

    def _esc(s):
        # RFC 5545 §3.3.11：TEXT 值须转义 \ ; , 换行
        return str(s).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    def _fold(line):
        # RFC 5545 §3.1：每行 ≤75 字节，续行以一个空格开头（按 UTF-8 字符边界切）
        b = line.encode("utf-8")
        parts = []
        while len(b) > (75 if not parts else 74):
            cut = 75 if not parts else 74
            while cut > 0 and (b[cut] & 0xC0) == 0x80:
                cut -= 1
            parts.append(b[:cut].decode("utf-8"))
            b = b[cut:]
        parts.append(b.decode("utf-8"))
        return "\r\n ".join(parts)

    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//opportunity-monitor//CN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             "X-WR-CALNAME:机会监控 · 关键日子", "X-WR-TIMEZONE:Asia/Bangkok"]
    rep = {"crypto": "加密", "war": "地缘", "ai": "AI", "all": "宏观"}
    # DTSTAMP 跟数据日走：订阅端不会每次构建都把全部事件当作"有更新"
    stamp = f"{str(payload.get('date') or '1970-01-01').replace('-', '')}T000000Z"
    for e in payload.get("calendar") or []:
        try:
            d = datetime.strptime(e["date"], "%Y-%m-%d")
        except Exception:
            continue
        if not (0 <= int(e.get("days_to", -1)) <= 90):
            continue
        uid = hashlib.sha1((e["date"] + e.get("title", "")).encode("utf-8")).hexdigest()[:12]
        summary = _esc(f"[{rep.get(e.get('report'), '')}] {str(e.get('title', ''))[:24]}{'（约）' if e.get('approx') else ''}")
        desc = _esc(str(e.get("note") or "").replace("\n", " ")[:120])
        lines += ["BEGIN:VEVENT", f"UID:{uid}@opportunity-monitor", f"DTSTAMP:{stamp}",
                  f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}", f"DTEND;VALUE=DATE:{(d + timedelta(days=1)).strftime('%Y%m%d')}",
                  f"SUMMARY:{summary}", f"DESCRIPTION:{desc}", "URL:https://awakenedallianc.github.io/opportunity-monitor/",
                  "BEGIN:VALARM", "TRIGGER:-PT15H", "ACTION:DISPLAY", f"DESCRIPTION:{summary}", "END:VALARM", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    out = out_dir / "calendar.ics"
    # newline=""：阻止 Windows 把 \n 再翻译成 \r\n（否则本地生成的 .ics 是 \r\r\n，解析器读不了）
    with open(out, "w", encoding="utf-8", newline="") as f:
        f.write("\r\n".join(_fold(l) for l in lines) + "\r\n")
    return out


def write_now(payload: dict, env, out_dir: Path) -> Path:
    """极简「三个数字」页 now.html（无 JS、无图）。"""
    rules = payload.get("rules") or []
    m = payload.get("metrics") or {}
    def val(k):
        x = (m.get(k) or {}).get("value")
        return None if x is None else float(x)
    rows = []
    for rep, name in (("crypto", "加密"), ("war", "地缘"), ("ai", "AI 时代")):
        rs = [r for r in rules if r.get("report") == rep and r.get("fired")]
        inv = any(r.get("level") == "invalidation" for r in rs)
        opp = sum(1 for r in rs if r.get("level") == "opportunity")
        risk = sum(1 for r in rs if r.get("level") in ("warning", "invalidation"))
        dot = "red" if inv else ("green" if opp else ("amber" if risk else "grey"))
        if rep == "crypto":
            number, label = _fmt_big(val("px.BTC"), "$"), "比特币"
        elif rep == "war":
            number, label = _fmt_big(val("px.BRENT"), "$"), "布伦特原油"
        else:
            dd = val("dd52w.SOXX")
            number, label = (f"{dd:+.0f}%" if dd is not None else "—"), "半导体 vs 一年高点"
        sentence = "报告判断失效，别动" if inv else f"{opp} 个买入信号、{risk} 个风险提示"
        rows.append({"name": name, "dot": dot, "number": number, "number_label": label, "sentence": sentence})
    fired = [r for r in rules if r.get("fired")]
    inv_n = sum(1 for r in fired if r.get("level") == "invalidation")
    opp_n = sum(1 for r in fired if r.get("level") == "opportunity")
    risk_n = sum(1 for r in fired if r.get("level") == "warning")
    verdict = f"注意：报告的 {inv_n} 个判断出了问题" if inv_n else (f"今天有 {opp_n} 个买入信号、{risk_n} 个风险提示" if opp_n else f"今天没有买入信号，有 {risk_n} 个风险提示")
    html = env.get_template("now.html.j2").render(date=payload.get("date"), rows=rows, verdict=verdict)
    out = out_dir / "now.html"
    out.write_text(html, encoding="utf-8")
    return out


def render(payload: dict, out: Path | None = None) -> Path:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(["html"]))
    tpl = env.get_template("index.html.j2")
    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    # 防止 JSON 内出现 </script> 提前闭合
    data_json = data_json.replace("</", "<\\/")
    html = tpl.render(data_json=data_json, date=payload.get("date"), generated_at=payload.get("generated_at"))
    out = out or (DOCS_DIR / "index.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    # 静态资源（样式/脚本）随模板一起发布，保证 file:// 与 Pages 都能加载
    assets_src = TEMPLATES / "assets"
    if assets_src.exists():
        import shutil
        dst = out.parent / "assets"
        dst.mkdir(parents=True, exist_ok=True)
        for p in assets_src.iterdir():
            if p.is_file():
                shutil.copy2(p, dst / p.name)
    # PWA 文件放站点根目录（Service Worker 作用域必须是根）
    pwa = TEMPLATES / "pwa"
    if pwa.exists():
        import shutil
        (out.parent / "icons").mkdir(parents=True, exist_ok=True)
        for p in pwa.iterdir():
            if p.suffix in (".js", ".webmanifest"):
                shutil.copy2(p, out.parent / p.name)
            else:
                shutil.copy2(p, out.parent / "icons" / p.name)
    # 附属页面各自兜底：ics 失败不应连累 now.html（云端 now.html 缺失会让页脚/PWA 快捷方式 404）
    try:
        write_ics(payload, out.parent)
    except Exception as e:
        log.warning("ics skipped: %s", e)
    try:
        write_now(payload, env, out.parent)
    except Exception as e:
        log.warning("now skipped: %s", e)
    log.info("site written: %s (%.1f KB)", out, len(html.encode("utf-8")) / 1024)
    return out
