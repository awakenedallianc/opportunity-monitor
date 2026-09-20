# 机会监控（Opportunity Monitor）

基于三篇深度推演报告（《加密三年测评图鉴》《AI时代交融十年推演》《大国战争风险与资产机会推演》，基准日 2026-09-20）搭建的**每日自动更新的信息可视化与机会监控站点**。

- **纯规则驱动，不调用任何大模型**：报告里的入场条件 / 失效信号 / 触发日历 / 敏感话题被翻译成 100+ 条机读规则（`config/rules.yaml`），每天用免费公开数据评估。
- **免费数据源**：CoinGecko、Binance/OKX、DefiLlama、Yahoo Finance、美国财政部/纽约联储/BLS/EIA/LBMA、Coin Metrics、SoSoValue、Polymarket、Kalshi、Google News RSS 与 90+ 个 RSS 源（清单见 `config/feeds.yaml`、`config/watchlist.yaml`）。
- **单文件站点**：`docs/index.html` 内联全部数据，双击即可离线打开；推到 GitHub Pages 后手机/任何电脑都能看。
- **推演追踪**：报告写下的每个关键数字（`config/baseline.yaml`）与今日读数逐日对照；每日触发的规则形成"推演变化日志"。

## 目录

```
run.py                 入口：python run.py [--only crypto,yahoo] [--skip news] [--build-only] [--import-only]
config/
  settings.yaml        全局设置、三篇报告摘要
  watchlist.yaml       43 个加密标的、110+ 个股票/商品/汇率/利率标的、预测市场、FRED 序列、专项源开关
  rules.yaml           机读规则（机会/风险/失效/事件/信息）
  calendar.yaml        触发日历（解锁、升级、法案生效、选举、FOMC、IPO、EEC 变电站投运…）
  topics.yaml          新闻话题关键词（中英）与权重
  feeds.yaml           RSS 源 + Google News 查询
  baseline.yaml        报告基线数字
  static.yaml          报告结构化内容（七大热点概率、情景×资产矩阵、起点表、AI 三阶段、路径矩阵、EEC 交付点）
src/monitor/
  run.py               主流程：抓取 → 入库 → 派生 → 规则 → 基线 → 生成站点
  fetchers/            crypto / defillama / yahoo / fred / polymarket / news / extras
  rules.py             规则引擎（compare / change / drawdown / streak / date / news / missing）
  derived.py           派生指标（ETH/BTC、回撤、P/S、回购收益率、期现价差…）
  store.py             SQLite 历史库 + 快照/新闻归档互转
  site.py + templates/ 站点生成（ECharts，浅/深色，手机适配）
data/
  history.sqlite       本地历史库（git 忽略，可由下面两项重建）
  snapshots/日期.json   每日指标与规则快照（git 跟踪）
  news_archive/月.jsonl 新闻归档（git 跟踪）
docs/                  生成的静态站点（index.html、data/latest.json、assets/echarts.min.js、reports/ 原报告）
scripts/
  local_boot.py        开机任务：拉取 → 本地运行 → 打开页面 → 云端过期则触发 Actions
  install_task.ps1     注册 Windows 计划任务（登录后 2 分钟 + 每日 08:30）
  publish_github.ps1   一键创建 GitHub 仓库、开启 Pages、推送
.github/workflows/daily.yml  云端每日两次（曼谷 06:17 / 18:17）抓取 + 部署 Pages
```

## 本机使用

```bash
pip install -r requirements.txt
python run.py
```

生成 `docs/index.html`，双击打开。首轮会回填约 400 天历史（Binance/Yahoo/DefiLlama/财政部），耗时 5–10 分钟；之后每天 3–6 分钟。

开机自动更新：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_task.ps1
```

## 任何电脑访问（GitHub Pages）

```powershell
powershell -ExecutionPolicy Bypass -File scripts\publish_github.ps1 -Repo opportunity-monitor
```

脚本会创建仓库、推送、启用 Pages（来源 = GitHub Actions）并触发首次工作流。之后云端每天两次自动更新；本机开机任务会先 `git pull` 再本地刷新，并在云端超过 20 小时未更新时触发补跑。站点地址：`https://<你的用户名>.github.io/<仓库名>/`。

> 隐私提示：GitHub Pages 站点是公开可访问的。`docs/reports/`（三篇原报告）默认被 `.gitignore` 排除，托管版只包含从报告提取的结构化内容；若要连原报告一起托管，删除 `.gitignore` 中的 `docs/reports/` 一行。

## 页面结构

| 页 | 内容 |
|---|---|
| 总览 | 16 个核心读数（带 30 日走势）、机会雷达（今日触发的规则，按机会/失效/风险/事件分组，新触发带"新"标）、三条主线相对报告基准的位置、未来 45 天日历、今日要闻 |
| 加密 | 条件仪表盘（全部规则的状态与读数）、BTC 与 50/200 周线、ETH/BTC、稳定币、恐惧贪婪、主导率、USDe、协议费用、链收入、43 标的五档表、解锁表、预测市场 |
| 地缘 | 七大热点概率（报告区间 + Polymarket 实时）、资产雷达（能源/航运/避险/军工/亚洲/铀矿化肥）、布伦特/黄金/10Y/VIX/莱茵金属/台股-KOSPI/预测市场/TTF 走势、情景×资产矩阵 A/B、报告起点表、八条纪律 |
| AI 时代 | 四把尺子读数、两段式机会分布、卖铲人与瓶颈层表、走势（NVDA/SOXX/NDX、SPY vs RSP、信用利差、电力设备、新云与矿企、韩国）、泰国 EEC 电网与东南亚数据中心新闻、个人路径矩阵 |
| 推演追踪 | 三篇报告摘要与原文链接、基线 vs 现在表、推演变化日志、完整触发日历、运行记录 |
| 阅读 | 最近 7 天全部新闻，按报告/话题/语言/敏感度筛选，研读模式显示摘要，已读状态存本机 |
| 数据 | 抓取器与新闻源状态、过期指标、来源等级约定、报告自述的数据缺口、指标字典 |

## 准确性约定

- 每个指标都带来源与时间戳；规则在数据缺失时显示"无数据"，不猜测。
- 来源分三级：T1 官方/一手（美联储、财政部、SEC、交易所、协议链上）、T2 主流媒体与成熟聚合、T3 二级聚合/博客（仅线索）。
- 价格交叉：BTC 用 CoinGecko + Binance；黄金用 Yahoo 期货 + LBMA 定盘价；美债用 Yahoo + 财政部曲线；FRED 在泰国网络不可达时以财政部曲线兜底。
- 新闻不做任何改写：只按关键词打标签、按"关键词权重 × 来源等级 × 新鲜度"排序，全部保留原标题与原摘要链接。

## 可选：大模型摘要

默认关闭，整套系统不依赖任何 LLM。若日后想要每日一段 AI 摘要，可以另写一个小脚本读取 `docs/data/latest.json` 调用 Claude Haiku，成本约每天几美分；本仓库刻意不内置。
