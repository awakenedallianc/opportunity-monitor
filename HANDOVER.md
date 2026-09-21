# 交接证书 · 机会监控（opportunity-monitor）

这份文件的目的：**任何 Claude Code 账户、任何电脑**，拿到这个仓库后 10 分钟内接手继续开发，不依赖原账户的记忆。每次 `python scripts/release.py` 发布都会刷新下面的版本戳。

<!-- AUTO:BEGIN -->
| 项目 | 值 |
|---|---|
| 版本 | **v2026.09.21.8** |
| 签发时间 | 2026-09-21 18:01 本机时间 |
| 基于提交 | `ba842b5` + 本次发布提交 |
| 本次说明 | 扩展第 2 批 12 条线（67 规则、16 数据源）+ 全站标的点击看 3 年 K 线 |
| 规则数 | 225 |
| 指标数 / 新闻数（最近构建） | 2715 / 600（数据日 2026-09-21） |
| 学习来源 / 方法论 / 功能候选(已上线) | 65 / 25 / 19(5) |
| Release | https://github.com/awakenedallianc/opportunity-monitor/releases/tag/v2026.09.21.8 |
<!-- AUTO:END -->

## 一句话
把三篇深度推演报告（加密三年 / AI 时代十年 / 大国战争风险）里的判断变成 115 条机读规则，每天用免费公开数据自动评估、抓新闻、算变化，生成一个白话的静态网页；**运行时不用任何大模型**。站点：https://awakenedallianc.github.io/opportunity-monitor/

## 接手清单

### A. 同一台电脑换 Claude Code 账户（最常见，2 分钟，不用下载）
1. 在新账户的 Claude Code 里直接打开本地文件夹 `D:\机会监控`（Code 页签 → 选择目录）。仓库根目录的 `CLAUDE.md` 会被自动加载，它会让新会话先读本文件和 `PROGRESS.md`。
2. 本地已有的东西都不用重做：git 仓库与远端、`.env`（EIA 密钥）、历史库 `data/history.sqlite`、开机任务 OpportunityMonitor-Daily、`.claude/launch.json` 预览配置。
3. 只有两样是"账户私有"的，需要在新账户里重建：
   - 学习循环计划任务：在 Claude 桌面 App 新建计划任务，提示词一句话——"进入 D:\机会监控，按 learning/LOOP.md 执行一期"（周期你定）。
   - Claude 的记忆文件：不需要迁移，本文件 + PROGRESS.md 就是全部上下文。
4. 验收：`python scripts/release.py --check` 全绿；`gh auth status` 确认新账户能推送（不能就 `gh auth login`）。

### B. 换一台电脑（10 分钟）
1. `git clone https://github.com/awakenedallianc/opportunity-monitor.git`（路径任意；`scripts/install_task.ps1` 与计划任务用绝对路径，需重新注册）。
2. `pip install -r requirements.txt`（Python 3.12；Windows 上 pandas 与 numpy 2.4 不兼容，项目不依赖 pandas）。
3. 仓库根目录建 `.env`，一行 `EIA_API_KEY=...`（向用户要；也已存在 GitHub Actions secrets 里）。**不要提交 .env。**
4. `python run.py --import-only` 从 `data/snapshots` + `data/news_archive` 重建本地历史库（约 1 分钟）。
5. `python run.py --build-only` 生成 `docs/index.html`，用 `.claude/launch.json` 的 `site`（端口 8791）或 `python -m http.server 8791 -d docs` 预览。
6. 读 `PROGRESS.md`（断点、待办、已知问题）——这是工作状态的唯一真相。
7. 学习循环：读 `learning/LOOP.md`；新建计划任务（同 A.3）。
8. 可选：`powershell -ExecutionPolicy Bypass -File scripts/install_task.ps1` 注册开机自动刷新。
9. GitHub：需要仓库 push 权限并 `gh auth login`；云端 Actions 每天 06:17 / 18:17 曼谷时间自动抓数据、提交快照、部署 Pages。
10. 验收：`python scripts/release.py --check` 全绿即接手成功。

## 架构一页
```
config/*.yaml（规则、监控清单、新闻源、话题、日历、基线、静态文案）
   └─ src/monitor/run.py ─ fetchers/*（免费 API + 146 个 RSS）─ store.py（SQLite，可由快照重建）
        ├─ derived.py（派生指标）─ rules.py（规则引擎：compare/change/drawdown/streak/date/news/missing）
        └─ site.py（Jinja 单页 + 内联 JSON）→ docs/index.html（简明/专业两种模式，app.js 渲染）
learning/（学习循环）：sources.yaml → scripts/learn_intake.py（每天，无 LLM）→ inbox/*.jsonl → digest.json
   └─ 学习周期（Claude 按 LOOP.md）→ knowledge.yaml / backlog.yaml / log.md → src/monitor/learn_page.py → docs/learn.html
scripts/release.py：自检 → 版本戳 → 提交白名单 → 推送 → 标签 → Release
```
- 两条部署车道：云端 GitHub Actions（权威数据、Pages 部署）；本机开机任务 `scripts/local_boot.py`（git pull → 本地刷新 → 打开页面）。
- 断点续跑：每个抓取器抓完立刻入库 + `data/checkpoint.json`；`python run.py --resume` 跳过 3 小时内完成的抓取器。

## 约定（违反会出事）
- **提交只加白名单**：src、config、scripts、learning/*.yaml|md、PROGRESS/HANDOVER/CLAUDE/README、.github。**永远不 `git add -A`、不提交 data/**（云端提交数据；冲突时以远端为准：`git checkout --theirs -- data/...`）。
- 生成物不入库：docs/index.html、docs/data/、docs/assets/app.*、docs/learn.html、data/history.sqlite、.env、data/raw/。
- 用户偏好：**白话、少字、少图**；金融数字用 万/亿、▲▼、日期；涨跌色可切换（默认绿涨红跌，可设红涨绿跌）。
- 运行时不用大模型；研究与迭代用 Claude。
- 每做一步更新 PROGRESS.md（用户明确要求断点记录，token 受限时不能从头来）。
- 网络限制（泰国本机）：FRED 不可达（有熔断与财政部曲线兜底）、Farside/ISW/Metaculus 403、GDELT 429、Binance 主站从美国运行器 451（有备用域名）。

## 用户画像
在泰国工作的中国电力工程师、投资者、非程序员。用中文。想要：每天开机自动更新、任何电脑能看、识别机会、能读长文和推演变化、信息准确。对界面的反馈史：第一版"专业但字太多"→ 简明模式 → 按顶尖金融网站 10 大核心功能重做。

## 验证方式
- `git tag` 列出所有版本；每个版本对应 GitHub Release，说明写在 Release notes。
- 本证书由 `scripts/release.py` 在每次发布时自动盖版本戳；手工修改只改"约定 / 架构 / 画像"三节。
