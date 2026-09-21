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

### 已完成（2026-09-21 14:10 曼谷）：学习循环系统（定期自动学习 → 新功能模块 + AI/互联网产品方法论）
- 用户指令："继续在网络学习研究相关信息，做成一个定期自动化学习的系统（时间我来调控），不断循环更新、接收新信息、增加亮点功能模块，同时学习如何做 AI 产品和互联网产品，提升用户全方位体验感。"
- 设计（两条车道）：
  1. 无 LLM 车道（免费、每日随云端/本机跑）：`scripts/learn_intake.py` 从 `learning/sources.yaml` 抓 RSS → 去重写入 `learning/inbox/YYYY-MM.jsonl` → 关键词打标 → 渲染 `docs/learn.html`（学习页，任何电脑可读）
  2. LLM 车道（用户定周期，桌面 App 计划任务 `learning-loop`）：按 `learning/LOOP.md` 执行：读 inbox 新条目 + 现有站点 + backlog → agent 联网研究 → 更新 `learning/knowledge.yaml`（方法论/教训）与 `learning/backlog.yaml`（功能模块，打分排序）→ 视情况实现 1 个小模块 → 写 `learning/log.md` 周期日志 → 提交推送
- 研究工作流（首轮内容）：`wf_54965116-677`（journal 在 subagents/workflows/wf_54965116-677/journal.jsonl），结果要写到 data/raw/learning_seed.json 再填入 learning/*.yaml
- 若中断：先看 data/raw/learning_seed.json 是否已生成；已生成则直接填 learning/*.yaml 并渲染；未生成则读 journal.jsonl 拼接
- 步骤状态：[x] 工作流（15 agents 完成，结果 data/raw/learning_seed.json） [x] learning/ 骨架 [x] intake 脚本（首跑 19/24 源 ok，368 条） [x] 学习页 docs/learn.html（主站导航「学习 ↗」） [x] daily.yml + local_boot 接入 [x] 计划任务 `learning-loop`（默认每周日 20:00，用户可改） [x] scripts/release.py 一键发布 + HANDOVER.md 交接证书 + CLAUDE.md [x] 已填入：来源 65（64 可抓）、方法论 25、功能候选 19（F003「自上次访问以来」标为下期做）；LOOP.md 追加研究补充（坑/打分/空白主题）
- 用户追加要求（2026-09-21）："每更新一版自动上传 GitHub，同时完成一个交接证书，可在其他 Claude Code 账户里衔接继续开发" → 已由 release.py（自动推送+标签+Release+刷新 HANDOVER.md 版本戳）与 CLAUDE.md（任何账户自动加载）满足

### 已完成（2026-09-21 新账户接手复核修正，发布 v2026.09.21.5）：学习循环第 1 期复核
- 新账户直接读到了旧复核工作流 journal（wf_aa2cbd15-c30，同一台电脑路径可达）：4 个审查员 37 条发现 + 13 条已核实结论，全部逐条对照源码核实后修复；另有 1 条 high 误报被证伪（「推送早晚颠倒」——daily.yml 第 27-28 行 job 级 TZ=Asia/Bangkok，date +%H 本来就是曼谷时，不改）
- 修复清单（22 处，全在呈现/推送/PWA 层，数据与规则链条未动）：
  - PWA：两个 PNG 图标文件头是字面文本导致 Chrome 判损坏、安装按钮永不出现 → 修字节并 CRC 校验；sw.js 统一 ./ 与 ./index.html 缓存 key（om-v3）+ 导航 8 秒弱网竞速；manifest/theme-color 改浅色默认 + applySettings 同步 meta；iOS 显示「分享 → 添加到主屏幕」提示
  - 自上次访问（catchUp）：UTC 日期改本地日期（曼谷早上不再多算 1 天）；历史只有 2 天时钳制到首日并标注「记录从 X 起」（原来任何老访客都显示「变了 28 件事」，现在只报真实的 6 件）；NaN 守卫；unread 小圆点与横幅同根因一并修
  - 判定卡：「把握：高」改「数据：齐/缺/旧」（原指标只量数据齐不齐，不量判断强弱，会在报告说「别追」时显示高把握可动）；actionOf 要求 ≥2 个买入信号且至少 1 个非新闻规则才说「可以按报告分批动」；关键指标过期阈值 >3 改 >4（周一休市后周二不再误报）；conf 色去红绿（与涨跌色冲突）；大卡不再误跳回顶部；robo/反馈只在报告页大卡显示（首屏字数 823→635）
  - 手机：? 提示锚定整行不再半截出屏、触区 28px、加 aria；规则表真 3 列（规则/现值/距离）不横滚；反馈按钮 32px、文案改「已记在本机，设置里可复制给我」（不再暗示已发出）
  - calendar.ics：RFC 5545 转义 + 75 字节折行 + 稳定 DTSTAMP（订阅端不再每天全量「有更新」）+ Windows 本地生成不再是 \r\r\n + 提醒改前一天 09:00；ICS 链接只对 Apple 用 webcal://（安卓 Chrome 无处理程序会死链）
  - 推送：push_text 按 first_fired≥昨天 选取（晚班首触发的规则不再永远漏报）；ntfy 步骤移到 deploy-pages 之后且失败不拖垮 job；代码 push 不再触发手机推送；定时班次无新变化时静默（L018）；三处结论措辞统一为「今天有 N 个买入信号、N 个风险提示」；now.html 数字舍入对齐 fmtBig、跟随站内主题
- 发布前自审已完成：工作流 wf_e6d5a424-a00（3 视角审查 + 逐条对抗核实我这轮 diff）→ 确认 5 条 low 全部修复（catchUp 钳制边界、「数据：矛盾」标签、_fold 末行 76 字节、_fmt_big <1 分支、专业模式补「怎么算」节）、1 条证伪（push_text TypeError 场景在真实数据契约下不存在）
- 学习循环计划任务已在新账户重建：「机会监控 · 学习循环」每周日 20:00（桌面 App → Scheduled 可改）
- 剩余已知（下期）：首屏 635 字仍超 L002 的 400 字目标（再减要动头条条/判定卡结构，等用户反馈）；「加到手机日历」的安卓可见说明只放在了按钮 title 里
### 上轮记录（2026-09-21 16:30 曼谷，原账户 token 用尽，转其他 Claude Code 账户继续）：学习循环第 1 期 —— 把首轮方法论用到应用上
- 用户指令："我也需要结合最新学习的知识来更新迭代机会监控应用"（用户主动触发，不等周日计划任务）
- 本期范围（按 backlog 分数 + 方法论）：
  功能：F003 自上次访问以来变化条 · F002 关键日子 .ics 订阅 · F005 极简 now.html · F004 PWA 离线/安装 · F001 每日 ntfy 推送（需用户加 secret NTFY_TOPIC）
  方法论落地：L002 首屏字数预算 · L003 判定卡高/中/低把握+动作 · L004 空状态三段式 · L006 数字带来源与时间 · L008 好处优先+「怎么算」· L009「固定规则算的，不是 AI 猜的」· L011 手机表格只留 3 列 · L013 具体的不确定说明 · L014 情境帮助 ? · L015 看懂了/没看懂反馈
- 步骤：[x] 前端改动 [x] site.py 生成 calendar.ics + now.html + pwa [x] push_text.py + daily.yml [x] 构建+浏览器验证（1280/375） [x] 复核工作流已启动后被中断（wf_aa2cbd15-c30，journal：C:/Users/33010/.claude/projects/D------/8135a533-7761-47a6-ba9a-40120117470a/subagents/workflows/wf_aa2cbd15-c30/journal.jsonl，type=result 行是各审查员发现；新账户看不到该目录就自审 git diff v2026.09.21.3..v2026.09.21.4） [x] backlog/log 更新 [x] release v2026.09.21.4 已推送（未经复核修正） [x] 新账户接手：读 journal → 修正 → 发布 v2026.09.21.5（见上一节）
- 接手方法：新账户直接打开 D:/机会监控（HANDOVER.md 清单 A）。已知待查点：帮助 ? 提示在 iOS 触屏；首屏字数 ≈745（目标 ≤400）；confidence() 三条主线全"高"的阈值是否太宽；write_ics 的 RFC 5545 折行/转义；daily.yml 推送步骤未在云端验证（需 secret NTFY_TOPIC）
- 若中断：git status 看改了哪些文件；node --check + python run.py --build-only 能过就继续未勾的步骤

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
- 2026-09-21：学习循环第 1 期复核修正 22 处（PWA 图标/缓存、catchUp 本地日期与钳制、判定卡「数据：齐/缺/旧」、手机 ?/表格/反馈、ics 转义折行、推送漏报与静默）；新账户重建计划任务
- 2026-09-21：学习循环系统 v1（learn_intake / learn_page / LOOP.md / release.py / HANDOVER.md / CLAUDE.md / 计划任务 learning-loop）；首轮研究填入 65 源 / 25 方法论 / 19 候选
- 2026-09-21：简明模式按 Top-10 核心功能重写（app.js/app.css/index.html.j2 搜索框）；yahoo 连续期货 chg1d 假值修复；store.py 云端重建库后 first_fired 延续（此前云端每次把全部触发标成"新"）
- 2026-09-20 项目创建；报告→规则；首轮运行；计划任务；断点续跑；部署修正；数据复核修正（进行中）
