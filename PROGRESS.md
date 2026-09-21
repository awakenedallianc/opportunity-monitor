# 进度与断点记录（PROGRESS.md）

> 目的：会话中断、token 受限、换电脑后都能从这里接上，**不要重跑已完成的工作**。

## 断点（2026-09-20 23:20 曼谷）— 本地与云端均已上线；当前任务：前端全面重设计（数据/规则链条不动）

### 已完成：UI 重设计（2026-09-20 23:30）
- 调研工作流 `wf_7ae863b7-7ab`（6 个视角 + 设计总监合成 brief），journal 在 `...\subagents\workflows\wf_7ae863b7-7ab\journal.jsonl`
- 已落地：新模板 `src/monitor/templates/index.html.j2` + `templates/assets/app.css|app.js`（构建时复制到 docs/assets）；`config/static.yaml: logic_chains`；rules.py 结果新增 `when`/`metric_keys` 字段（仅供前端画阈值条与抽屉曲线，不改评估逻辑）
- 设计 brief 全文在 `data/raw/design_brief.json`（design-brief 键）；未实现的次要项：Inter 字体子集、数值 count-up 动画、CSV 下载、日期滑块、Full-Coverage 二级抽屉、列表虚拟化
- 已在桌面/手机/深色三种视图下检查：无控制台错误、无横向溢出
- 数据、规则、抓取、payload 结构一律不改；只改呈现

### 已完成（不要重做）
- 三篇报告通读与规则化：config/ 下 rules(115)、calendar、baseline、static、topics、feeds、watchlist 全部就绪
- 抓取层 + 规则引擎 + 站点生成全部可用；本机完整运行成功（logs/run4.out 为最近一次全量）
- 开机计划任务 `OpportunityMonitor-Daily` 已注册（scripts/install_task.ps1）
- 断点续跑：抓取器逐个落库 + data/checkpoint.json；`python run.py --resume`
- 部署脚本复核修正已落地（publish_github.ps1 / daily.yml / local_boot.py / .gitignore / store.is_empty / CoinGecko 兜底）

### 后台工作流结果（已生成，直接读 journal，不要重跑）
- 研究工作流 `wf_e5a3ad7e-89e`：`C:\Users\33010\.claude\projects\D------\8135a533-7761-47a6-ba9a-40120117470a\subagents\workflows\wf_e5a3ad7e-89e\journal.jsonl`
  - 7 个 research 结果已全部合并进 config/ 与 fetchers；`extract:*`（三篇报告结构化提取）与 `verify:*`、critic、gapfill 结果**尚未合并**——读 journal 中 type=result 的 claims，对照 config/rules.yaml / baseline.yaml / calendar.yaml 补遗漏项即可
- 复核工作流 `wf_8f6bbf46-54e`：`...\subagents\workflows\wf_8f6bbf46-54e\journal.jsonl`
  - review:deployment（DEP-01…12）已全部修复
  - review:data-sanity（DS-01…11）：修复状态见下表
  - review:rules-vs-reports / backend / frontend 与 Verify 阶段：结果待读取合并

| 发现 | 状态 |
|---|---|
| DS-01…11（数据）| 已修复：PortWatch 分页 1000 + 战前基线；稳定币按 id；期货 chg1d 用 previousClose；Yahoo 按 asof 入库/剔周末 bar/交易所时区；plavis 空值跳过；KOSPI 锚点；HYPE FDV 口径；USX 单位 |
| B1–B5, B12（后端）| 已修复：FX 日期、30 日滚动含当日、sub_status 透传、first_fired 按上次运行日连续、Http timeout/Retry-After、负值不算百分比 |
| FE-01…06（前端）| 已修复：PLA/GPR 分图、'all' 规则进各页仪表盘、警告色只在暗色生效、HTML 实体反转义、天数取整 |
| B6–B11, B13–B14, FE-07…16, DEP-*（低）| DEP 已修；其余低优先级未处理，清单在复核 journal（review:backend / review:frontend 的 findings） |
| review:rules-vs-reports | **未完成**（agent 因会话限额失败）；下次可单独跑：对照 data/raw/*_text.txt 检查 config/rules.yaml 阈值 |

### 待办
- [x] 研究工作流全部 22 个 agent 已完成（限额恢复后自动跑完）：三篇报告结构化提取 + 校验版（crypto 122 / ai 121 / war 111 条 claims）、完整性 critic（覆盖 59 / 部分 46 / 缺失 8，缺失项全是需人工年度更新的静态锚点）已保存到 `data/raw/extracted_claims.json`（本地，未入库）
- [ ] 增量合并：把 extracted_claims.json 中 automatable=yes 且 rules.yaml 尚无的条件补进规则/日历/基线（46 项 partial 覆盖见 critic.coverage_matrix）；rules-vs-reports 逐条核对仍未跑
- [ ] 修完后：`python run.py --only yahoo,defillama,extras` → `python run.py --build-only` → 浏览器检查（本地 http://localhost:8791，服务由 .claude/launch.json 的 site 配置启动）
- [x] 已发布（用户确认）：仓库 https://github.com/awakenedallianc/opportunity-monitor ，站点 https://awakenedallianc.github.io/opportunity-monitor/ ；Pages 来源 = GitHub Actions；首个工作流运行 35519872649 结果见 `gh run list --workflow daily.yml`
- [ ] 若云端首跑失败：`gh run view <id> --log-failed`；常见原因 CoinGecko 429（已有 Binance 兜底）、Yahoo 限流


### 简明模式（2026-09-21，用户反馈"字太多、看不懂、图太多"后新增，默认开启）
- 右上角「简明 / 专业」切换（localStorage 记忆）。简明模式：总览 = 一句话结论 + 三张状态卡（每张：状态灯、一句白话、2 个大数字带"报告写作时"对比、"报告怎么说"一句）+ 今天最重要 5 条（白话）+ 关键日子 + 5 条新闻；报告页 = 状态卡（4 个数字）+ 唯一一张图 + 买入/放弃信号进度（白话）+ 接下来 + 新闻。
- 89 条关键规则加了 `plain` 白话解释（config/rules.yaml），其余用术语替换表兜底（app.js GLOSS）。
- 专业模式保留原全部页面；`docs/assets/app.*` 改为构建产物不再跟踪。


### 已完成（2026-09-21 09:40 曼谷）：按"顶尖金融分析网站 10 大核心功能"重做简明模式 —— 已验证（1280/375、深浅色、点击/搜索/热力图）并推送
- 调研工作流 `wf_59399caf-edf` 已完成（不要重跑），结果在 `data/raw/top10_features.json`（inventories / editor Top10 / skeptic / feasibility）
- 已实现（app.js `// ---------- 简明模式（按顶尖金融分析网站 10 大核心功能重做）` 段 + app.css `十大核心功能` 段 + index.html.j2 搜索框）：
  1 首屏状态条 `headline()`（8 个价格 + 3 个赌盘，▲▼ + 绝对变化 + 更新日期，可点开抽屉）
  2 综合判定卡 `verdictCard()`（阶段标签 `phaseLabel`、3 组进度条 `GROUPS`、一句话、利好/风险各 3 条）
  3+5 今日触发列表 `alertsBlock()` + 「查看全部」展开 `rulesTableFull()`（现值/阈值/距离，按报告筛）+ 自昨日变化 chips
  4 催化剂日历 `calendarTabs()`（上周/本周/下周/90 天 + 重要度 ■■□ + 关联规则数）
  6 基线定位 `baselineList()` + 2 年区间条 `rangeBar()`（百分位、报告基线 ▽）
  7 分层新闻 `newsTabs()`（48h、T1/T2、按主线、触发话题置顶）
  8 故事图 `storyChart()`（每主线一张，FT 式标题 `storyTitle`，总览折叠、报告页展开）
  9 一句话结论（总览 `.s-verdict`）
  10 全市场热力图 `marketMapBlock()/initMarketMap()`（ECharts treemap，尺寸=IMPORTANCE 权重）+ 异动前十
  + 搜索框 `buildSearch()`（Ctrl+K，资产/规则/指标/新闻）；指标白话定义表 `DEFS`（~50 条）
- 顺手修的数据 bug：`fetchers/yahoo.py` 连续期货 chg1d 用 Yahoo previousClose 出现 +67%/+131% 假值 → 偏离 >15% 判无效回退日线
- 可能的后续（等用户反馈）：DEFS 白话定义只覆盖 ~50 个指标，其余回退到 labelOf；催化剂重要度暂按类别静态打分（无共识/实际值）；热力图尺寸权重 IMPORTANCE 是手工表。

## 已知限制（泰国网络）
- FRED 不可达（熔断，财政部曲线兜底）；Farside/ISW 原站/Metaculus 403；GDELT 429；Stooq 需 JS 挑战
- Binance 主站在 GitHub 美国运行器 451 → 已回退 data-api.binance.vision；CoinGecko 失败时主流币价格由 Binance 兜底（降级标记）
- 本机全局 pandas 与 numpy 2.4 不兼容 → 项目运行不依赖 pandas；已建项目 venv（`.venv`，numpy 1.26.4 / pandas 3.0.6 / xlrd 2.0.2 / openpyxl / lxml），计划任务已改用 `.venv\Scripts\pythonw.exe`；run.py 与 local_boot.py 强制 UTF-8 输出（GBK 控制台泰文/© 报错已解决）

## 提交须知
- 本机手动提交代码时只 `git add src config scripts docs/assets README.md PROGRESS.md .github`，不要 `git add -A`：data/snapshots 与 data/news_archive 由云端 Actions 提交，本地生成的同名文件会冲突（冲突时以云端为准：`git checkout --ours -- data/...`）

## 常用命令
```
python run.py                 # 全量（首轮回填约 400 天历史，约 8 分钟）
python run.py --resume        # 断点续跑（跳过 3 小时内已完成的抓取器）
python run.py --only extras,polymarket
python run.py --build-only    # 只重建页面
python run.py --import-only   # 从 data/snapshots + data/news_archive 重建历史库
python scripts/local_boot.py --skip-run --no-open
powershell -ExecutionPolicy Bypass -File scripts\setup_venv.ps1   # 新机器：建 .venv（然后重跑 install_task.ps1）
powershell -ExecutionPolicy Bypass -File scripts\install_task.ps1
```

## 变更日志
- 2026-09-21：简明模式按 Top-10 核心功能重写（app.js/app.css/index.html.j2 搜索框）；yahoo 连续期货 chg1d 假值修复；store.py 云端重建库后 first_fired 延续（此前云端每次把全部触发标成"新"）
- 2026-09-20 项目创建；报告→规则；首轮运行；计划任务；断点续跑；部署修正；数据复核修正（进行中）
