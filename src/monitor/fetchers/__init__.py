"""抓取器注册表。每个抓取器实现 fetch(cfg, http_factory) -> dict:
    {"metrics": [ {key, value, meta, source, asof} ... ],
     "news":    [ {id, published, source, feed, title, link, summary, lang, tier} ... ],
     "notes":   str}
抓取器彼此独立，任何一个失败不影响其他。
"""
from importlib import import_module

FETCHERS = [
    "crypto",        # CoinGecko / Binance / Alternative.me
    "defillama",     # 协议费用、TVL、稳定币、解锁
    "yahoo",         # 股票、商品、汇率、利率、波动率
    "fred",          # 美联储经济数据（利率、利差、流动性）
    "polymarket",    # 预测市场概率
    "news",          # RSS / Google News
    "extras",        # 其他专项源（PortWatch、Treasury、Cameco 等）
]


def load(name: str):
    return import_module(f"{__package__}.{name}")
