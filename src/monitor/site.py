"""静态站点生成：把 payload 内联进单文件 index.html（双击即可离线打开，也可托管在 GitHub Pages）。"""
from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .utils import DOCS_DIR, log

TEMPLATES = Path(__file__).resolve().parent / "templates"


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
    log.info("site written: %s (%.1f KB)", out, len(html.encode("utf-8")) / 1024)
    return out
