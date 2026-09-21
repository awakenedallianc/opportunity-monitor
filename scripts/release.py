"""一键发布：自检 → 更新交接证书版本戳 → 提交白名单 → 拉取变基 → 推送 → 打标签 → GitHub Release。

用法：
  python scripts/release.py "一句话说明"          # 完整发布
  python scripts/release.py --check              # 只自检（node --check、编译、构建）
  python scripts/release.py "说明" --no-release  # 不创建 GitHub Release（只推送 + 标签）
  python scripts/release.py "说明" --no-push     # 只本地提交与标签

原则：永远不 add data/（由云端生成并提交）；本地生成物在 .gitignore 里；标签 vYYYY.MM.DD[.n]。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WHITELIST = ["src", "config", "scripts", "tests", "run.py", "requirements.txt", "README.md", "PROGRESS.md", "HANDOVER.md",
             "CLAUDE.md", ".gitignore", ".github", "learning/sources.yaml", "learning/knowledge.yaml", "learning/backlog.yaml",
             "learning/knowledge_archive.yaml", "learning/backlog_archive.yaml", "learning/log.md", "learning/LOOP.md",
             "learning/inbox", "docs/assets/echarts.min.js", "docs/.nojekyll"]
AUTO_BEGIN, AUTO_END = "<!-- AUTO:BEGIN -->", "<!-- AUTO:END -->"


def sh(cmd: list[str], check: bool = True, timeout: int = 300) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    out = (p.stdout or "") + (p.stderr or "")
    if check and p.returncode != 0:
        raise SystemExit(f"命令失败 ({p.returncode}): {' '.join(cmd)}\n{out[-1500:]}")
    return p.returncode, out


def self_check() -> dict:
    res = {}
    js = ROOT / "src/monitor/templates/assets/app.js"
    if shutil.which("node"):
        sh(["node", "--check", str(js)])
        res["node_check"] = "ok"
    else:
        res["node_check"] = "skipped (no node)"
    sh([sys.executable, "-m", "compileall", "-q", "src", "scripts", "run.py"])
    res["compile"] = "ok"
    rc, out = sh([sys.executable, "run.py", "--build-only"], check=False, timeout=600)
    if rc != 0 or '"ok": true' not in out:
        raise SystemExit(f"构建失败:\n{out[-1500:]}")
    res["build"] = "ok"
    return res


def counts() -> dict:
    import yaml
    c = {}
    try:
        c["rules"] = len(yaml.safe_load((ROOT / "config/rules.yaml").read_text(encoding="utf-8")).get("rules", []))
    except Exception:
        c["rules"] = "?"
    try:
        c["sources"] = len(yaml.safe_load((ROOT / "learning/sources.yaml").read_text(encoding="utf-8")).get("sources", []))
        c["lessons"] = len(yaml.safe_load((ROOT / "learning/knowledge.yaml").read_text(encoding="utf-8")).get("lessons") or [])
        bl = yaml.safe_load((ROOT / "learning/backlog.yaml").read_text(encoding="utf-8")).get("features") or []
        c["features"] = len(bl)
        c["features_done"] = sum(1 for f in bl if f.get("status") == "done")
    except Exception:
        pass
    try:
        latest = json.loads((ROOT / "docs/data/latest.json").read_text(encoding="utf-8"))
        c["metrics"] = len(latest.get("metrics") or {})
        c["news"] = len(latest.get("news") or [])
        c["data_date"] = latest.get("date")
    except Exception:
        pass
    return c


def next_tag() -> str:
    base = "v" + datetime.now().strftime("%Y.%m.%d")
    _, out = sh(["git", "tag", "--list", f"{base}*"], check=False)
    existing = set(out.split())
    if base not in existing:
        return base
    n = 2
    while f"{base}.{n}" in existing:
        n += 1
    return f"{base}.{n}"


def update_handover(tag: str, msg: str, c: dict) -> None:
    p = ROOT / "HANDOVER.md"
    if not p.exists():
        return
    _, head = sh(["git", "rev-parse", "--short", "HEAD"], check=False)
    lines = [AUTO_BEGIN,
             f"| 项目 | 值 |", "|---|---|",
             f"| 版本 | **{tag}** |",
             f"| 签发时间 | {datetime.now().strftime('%Y-%m-%d %H:%M')} 本机时间 |",
             f"| 基于提交 | `{head.strip()}` + 本次发布提交 |",
             f"| 本次说明 | {msg} |",
             f"| 规则数 | {c.get('rules', '?')} |",
             f"| 指标数 / 新闻数（最近构建） | {c.get('metrics', '?')} / {c.get('news', '?')}（数据日 {c.get('data_date', '?')}） |",
             f"| 学习来源 / 方法论 / 功能候选(已上线) | {c.get('sources', '?')} / {c.get('lessons', '?')} / {c.get('features', '?')}({c.get('features_done', 0)}) |",
             f"| Release | https://github.com/awakenedallianc/opportunity-monitor/releases/tag/{tag} |",
             AUTO_END]
    s = p.read_text(encoding="utf-8")
    if AUTO_BEGIN in s and AUTO_END in s:
        s = s[: s.index(AUTO_BEGIN)] + "\n".join(lines) + s[s.index(AUTO_END) + len(AUTO_END):]
    else:
        s = s.replace("\n", "\n" + "\n".join(lines) + "\n", 1)
    p.write_text(s, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("message", nargs="?", default="")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--no-release", action="store_true")
    a = ap.parse_args()
    print("[1/6] 自检…")
    print("      ", self_check())
    if a.check:
        print("状态：", json.dumps(counts(), ensure_ascii=False))
        return 0
    if not a.message:
        raise SystemExit("需要一句话说明：python scripts/release.py \"说明\"")
    tag = next_tag()
    c = counts()
    print(f"[2/6] 更新交接证书版本戳 → {tag}")
    update_handover(tag, a.message, c)
    print("[3/6] 提交白名单文件…")
    existing = [w for w in WHITELIST if (ROOT / w).exists()]
    sh(["git", "add", "--"] + existing)
    rc, _ = sh(["git", "diff", "--cached", "--quiet"], check=False)
    if rc == 0:
        print("       没有可提交的改动（仍会打标签）")
    else:
        sh(["git", "commit", "-q", "-m", f"release {tag}: {a.message}\n\nCo-Authored-By: Claude <noreply@anthropic.com>"])
    if not a.no_push:
        print("[4/6] 丢弃本地生成数据、拉取变基、推送…")
        sh(["git", "checkout", "--", "data", "learning/inbox"], check=False)
        rc, out = sh(["git", "pull", "--rebase", "-q", "origin", "main"], check=False, timeout=180)
        if rc != 0:
            # 数据文件冲突：以远端（云端生成）为准
            _, files = sh(["git", "diff", "--name-only", "--diff-filter=U"], check=False)
            for f in files.split():
                if f.startswith("data/") or f.startswith("learning/inbox/"):
                    sh(["git", "checkout", "--theirs", "--", f], check=False)
                    sh(["git", "add", "--", f], check=False)
            rc2, out2 = sh(["git", "-c", "core.editor=true", "rebase", "--continue"], check=False)
            if rc2 != 0:
                sh(["git", "rebase", "--abort"], check=False)
                raise SystemExit(f"变基冲突无法自动解决，请手工处理：\n{out[-800:]}\n{out2[-800:]}")
        sh(["git", "push", "-q", "origin", "main"], timeout=180)
    print(f"[5/6] 打标签 {tag}")
    sh(["git", "tag", "-a", tag, "-m", a.message])
    if not a.no_push:
        sh(["git", "push", "-q", "origin", tag], timeout=120)
        if not a.no_release and shutil.which("gh"):
            print("[6/6] 创建 GitHub Release…")
            notes = f"{a.message}\n\n站点：https://awakenedallianc.github.io/opportunity-monitor/\n交接证书：HANDOVER.md（版本 {tag}）"
            rc, out = sh(["gh", "release", "create", tag, "--title", f"{tag} · {a.message[:40]}", "--notes", notes], check=False, timeout=120)
            print("       ", out.strip()[-200:])
        else:
            print("[6/6] 跳过 GitHub Release")
    print(json.dumps({"tag": tag, "pushed": not a.no_push, **c}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
