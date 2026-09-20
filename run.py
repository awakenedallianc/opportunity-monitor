"""项目入口：python run.py [--only a,b] [--skip c] [--build-only] [--import-only]

--only/--skip   只跑/跳过某些抓取器（crypto, defillama, yahoo, fred, polymarket, news, extras）
--build-only    不抓取，用库中数据重建页面
--import-only   仅从 data/snapshots 与 data/news_archive 重建历史库（云端/新机器首次运行会自动做）
"""
import os
import sys
from pathlib import Path

for _k, _v in (("PYTHONIOENCODING", "utf-8"), ("PYTHONUTF8", "1")):
    if not os.environ.get(_k):
        os.environ[_k] = _v
for _s in (sys.stdout, sys.stderr):
    if _s is not None and hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

# 读取项目根目录 .env（API 密钥等；文件已被 gitignore）
_env = Path(__file__).resolve().parent / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8").splitlines():
        if "=" in _line and not _line.strip().startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from monitor.run import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
