"""生成每日推送正文（纯文本，≤ 6 行）：一句话结论 + 今天新触发的规则（白话，最多 5 条）。

用法：python scripts/push_text.py            # 打印到 stdout（daily.yml 用 curl 发到 ntfy）
      python scripts/push_text.py --json     # 附带 JSON（调试）
无新触发时只输出一行「今天没变化」。运行时不用大模型。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build() -> str:
    p = ROOT / "docs" / "data" / "latest.json"
    if not p.exists():
        return "今天没有生成数据"
    d = json.loads(p.read_text(encoding="utf-8"))
    rules = d.get("rules") or []
    fired = [r for r in rules if r.get("fired")]
    new = [r for r in fired if r.get("is_new")]
    opp = sum(1 for r in fired if r.get("level") == "opportunity")
    risk = sum(1 for r in fired if r.get("level") in ("warning", "invalidation"))
    inv = [r for r in fired if r.get("level") == "invalidation"]
    if inv:
        head = f"注意：报告的 {len(inv)} 个判断出了问题"
    elif opp:
        head = f"今天 {opp} 个买入信号、{risk} 个风险提示"
    else:
        head = f"今天没有买入信号，{risk} 个风险提示"
    lines = [head]
    if not new:
        lines.append("规则没有新变化")
    for r in new[:5]:
        tag = {"opportunity": "利好", "warning": "风险", "invalidation": "失效", "event": "事件", "info": "提示"}.get(r.get("level"), "")
        lines.append(f"{tag}：{r.get('plain') or r.get('title')}")
    if len(new) > 5:
        lines.append(f"另有 {len(new) - 5} 条新触发")
    return "\n".join(lines)


if __name__ == "__main__":
    text = build()
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)
    if "--json" in sys.argv:
        print(json.dumps({"lines": text.count("\n") + 1, "chars": len(text)}, ensure_ascii=False))
