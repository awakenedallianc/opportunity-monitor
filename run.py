"""项目入口：python run.py [--only a,b] [--skip c] [--build-only] [--import-only]

--only/--skip   只跑/跳过某些抓取器（crypto, defillama, yahoo, fred, polymarket, news, extras）
--build-only    不抓取，用库中数据重建页面
--import-only   仅从 data/snapshots 与 data/news_archive 重建历史库（云端/新机器首次运行会自动做）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from monitor.run import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
