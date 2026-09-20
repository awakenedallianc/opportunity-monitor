"""开机任务（Windows 任务计划程序调用）：
1. 若项目是 git 仓库且有远端：丢弃本地生成物 → git pull --ff-only（云端 Actions 是权威数据）
2. 本地运行一次完整抓取与生成（离线也能用，且比云端更新鲜）
3. 用默认浏览器打开 docs/index.html
4. 若云端快照超过 20 小时未更新且 gh 可用：触发 workflow_dispatch 让云端补跑

日志：logs/local.log（轮转 5×1MB）。
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
import subprocess
import sys
import time
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)

LOG = ROOT / "logs" / "local.log"
LOG.parent.mkdir(exist_ok=True)
h = logging.handlers.RotatingFileHandler(LOG, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
logging.basicConfig(handlers=[h, logging.StreamHandler(sys.stdout)], level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("boot")


def sh(cmd: list[str], timeout: int = 120) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace",
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return 1, str(e)


def has_remote() -> bool:
    rc, out = sh(["git", "remote"])
    return rc == 0 and "origin" in out


def wait_network(max_wait: int = 180) -> bool:
    import socket
    t0 = time.time()
    while time.time() - t0 < max_wait:
        try:
            socket.create_connection(("api.coingecko.com", 443), timeout=5).close()
            return True
        except OSError:
            time.sleep(10)
    return False


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-open", action="store_true", help="不打开浏览器")
    ap.add_argument("--skip-run", action="store_true", help="跳过本地抓取（仅拉取/触发云端）")
    a = ap.parse_args()
    global _open
    if a.no_open:
        _open = lambda: log.info("skip opening browser")  # noqa: E731
    log.info("=== boot start ===")
    if not wait_network():
        log.warning("network not available; opening cached page only")
        _open()
        return 0
    if (ROOT / ".git").exists() and has_remote():
        # 生成物可重建：丢弃本地改动与未跟踪的本地快照，确保 ff-only 拉取不被阻塞
        sh(["git", "checkout", "--", "data"])
        sh(["git", "clean", "-fdq", "--", "data/snapshots", "data/news_archive"])
        rc, out = sh(["git", "pull", "--ff-only"], timeout=180)
        log.info("git pull rc=%s %s", rc, out[-300:])
        if rc != 0:
            log.warning("git pull failed; continuing with local data")
        else:
            # 把云端新拉下来的快照并入本地历史库（幂等）
            rc_i, out_i = sh([sys.executable, str(ROOT / "run.py"), "--import-only"], timeout=600)
            log.info("import-only rc=%s %s", rc_i, out_i[-200:])
    # 本地运行完整流程
    if not a.skip_run:
        # --resume：若今天已有近 3 小时内完成的抓取器（例如上次开机被中断/刚跑过），跳过它们
        rc, out = sh([sys.executable, str(ROOT / "run.py"), "--resume"], timeout=1500)
        log.info("run.py rc=%s tail=%s", rc, out[-600:])
    _open()
    # 云端是否需要补跑
    try:
        latest = ROOT / "docs" / "data" / "latest.json"
        if has_remote():
            rc2, out2 = sh(["gh", "run", "list", "--workflow", "daily.yml", "--limit", "1", "--json", "createdAt,status,conclusion"], timeout=60)
            stale = True
            if rc2 == 0 and out2.strip():
                runs = json.loads(out2)
                if runs:
                    created = datetime.fromisoformat(runs[0]["createdAt"].replace("Z", "+00:00"))
                    stale = datetime.now(created.tzinfo) - created > timedelta(hours=20)
            if stale:
                # 公开仓库 60 天无活动会被自动停用计划；先确保启用再触发
                rc_v, out_v = sh(["gh", "workflow", "view", "daily.yml", "--json", "state", "--jq", ".state"], timeout=60)
                if rc_v == 0 and "disabled" in out_v:
                    sh(["gh", "workflow", "enable", "daily.yml"], timeout=60)
                    log.info("re-enabled disabled workflow")
                rc3, out3 = sh(["gh", "workflow", "run", "daily.yml"], timeout=60)
                log.info("triggered cloud workflow rc=%s %s", rc3, out3[-200:])
    except Exception as e:
        log.warning("cloud check skipped: %s", e)
    log.info("=== boot done ===")
    return 0


def _open():
    page = ROOT / "docs" / "index.html"
    if page.exists():
        webbrowser.open(page.as_uri())


if __name__ == "__main__":
    sys.exit(main())
