# 学习循环 SOP（每期的 Claude 会话按此执行）

目标：让「机会监控」持续学习——每期吸收新信息，沉淀成方法论，把值得做的功能排进榜单并做出一个，同时把"如何做 AI 产品 / 互联网产品 / 全方位体验"的心得写给用户看。

## 硬约束（每期开头默读一遍）
1. **站点运行时不用大模型**。新功能必须能用规则、模板、免费公开数据实现；需要 LLM 的只能进候选榜并注明"需大模型"。
2. **白话、少字、少图**。用户是非程序员，反复反馈"字太多、看不懂、图太多"。任何新界面先问：能不能砍掉一半字。
3. **数据与规则链条不动**：不改 config/rules.yaml 的语义、不改 fetchers 的数据口径，除非是修 bug 并写进日志。
4. **每期只实现一个小模块**（工作量 effort ≤ 2），做不完就写清规格放回榜单，不留半成品。
5. **可回滚**：所有改动走 `python scripts/release.py "说明"` 发布（自动打标签、推送、更新交接证书）；出问题 `git revert` 到上一个标签。
6. **不重复研究**：先读 log.md 最近 4 期的主题，已经研究过的主题除非有新证据不再研究。
7. **知识库不膨胀**：knowledge.yaml ≤ 60 条、backlog.yaml 未完成项 ≤ 30 条，超了就归档（*_archive.yaml）或删除并写原因。
8. **断点**：开始时把本期计划写进 PROGRESS.md「学习循环」小节，每完成一步更新状态；中断后从那里续。

## 步骤（约 60–90 分钟的工作量；时间到就收尾，不硬撑）
0. **准备**：`cd D:\机会监控`；`git pull --ff-only`；读 HANDOVER.md 顶部、PROGRESS.md 断点、learning/log.md 最近 4 期、learning/backlog.yaml、learning/knowledge.yaml；运行 `python scripts/learn_intake.py`。
1. **看收件箱**：读 learning/inbox/digest.json（近 14 天）与 status.json。抓不到的来源连续 3 期失败就在 sources.yaml 里 `enabled: false` 并写 why。挑出 ≤ 3 个本期主题（优先：用户体验、AI 产品方法、可以直接变成本站功能的做法）。
2. **联网研究**：对每个主题用 WebSearch/WebFetch 找一手来源（官方博客、原始研究、真实产品页面）。每个结论必须附 URL。可以用多个 agent 并行，但最后由你合并去重。
3. **沉淀方法论**：写进 learning/knowledge.yaml，每期 ≤ 5 条新 lesson。每条：title（≤ 15 字）、takeaway（一句白话）、action（本站具体怎么用，指明页面/模块）、applies_to、source_name、url、added、rank。合并同义条目。
4. **更新候选榜**：learning/backlog.yaml 每期 ≤ 5 条新候选；给所有未完成项重新估 value/effort/needs_llm/risk_words/data_ok；把分最高且 effort ≤ 2 的一条设为 `planned`。
5. **实现一个**：把 planned 改 building → 改代码（前端在 src/monitor/templates/assets/app.js、app.css；后端在 src/monitor/）→ `node --check` → `python run.py --build-only` → 用浏览器工具检查 1280 与 375 宽、深浅色、无 console 报错 → 改 done 并写 notes（上线日期、怎么验收）。做不完：改回 planned，并把规格写进 notes。
6. **体验巡检**（10 分钟）：打开 docs/index.html 简明模式，从首屏往下数字数：首屏可见文字 ≤ 150 字；任何段落 > 40 字就改短。检查数字格式（万/亿、▲▼、日期）、对比度、移动端不横向滚动。发现问题小的当场修，大的进候选榜。
7. **写日志**：在 learning/log.md 末尾追加一期（格式见文件头），四个小节各 ≤ 3 条，每条 ≤ 40 字。
8. **发布**：`python scripts/release.py "第 N 期：主题"`。它会：自检 → 更新 HANDOVER.md 版本戳 → 提交白名单文件 → 推送 → 打标签 → 创建 GitHub Release。失败就修到能过为止；推送失败按 HANDOVER.md 的冲突处理。
9. **通知用户**（最终消息，≤ 200 字）：学到的 3 句话、本期上线了什么（附站点链接）、下期打算做什么、如何调整周期（"在 Claude 桌面 App 的计划任务里改时间或暂停"）。

## 输出模板（log.md 一期）
```
## 2026-10-05 · 第 3 期 · 通知节奏与每日简报
- **学到**：一句话 ×≤3（每句带来源名）
- **新增候选**：名称（分数）×≤3
- **本期实现**：模块名 + 一句验收方法 + Release 标签
- **下期**：一句话
```

## 进阶（当基础稳定后可选）
- 把候选榜里 needs_llm 的项目改造成"规则 + 模板"版本。
- 用 learning/inbox 里的文章做"用户可读的周刊"（每周一段 5 句话）。
- 邀请用户在最终消息里回一句"最想要的功能"，写进 backlog.yaml 的 `user_votes`。

## 研究补充（2026-09-21 首轮工作流 wf_54965116-677 的结论，供每期参考）
### 循环设计的坑（研究者与怀疑者共识）
- 编译出的知识页会自信地写错（幻觉）：每条结论必须带来源引用才可入库，高风险 claim（会改规则）要两个独立来源。
- 要分开「事实生效时间」valid_from 和「我们核实的时间」last_verified，否则旧答案无法复现、旧结论无法被新源正确取代。
- LLM 默认倾向新建文件而不是合并（Anthropic Memory Tool 官方也提醒），必须靠 kb_lint 的行数/总数上限和「先 grep 再新建」兜底。
- 让 LLM 决定 DELETE 有误删风险（Mem0 教训）：只改 status: superseded/archived 与移动目录，永不物理删。
- inbox 积压是知识库死亡的头号原因（「一个月 200 条没处理系统就废了」）：deferred 不进 backlog，Shape Up 式「重要的想法会自己回来」，但过期要可见（expired + 日志），否则用户会以为系统丢了东西。
- agent 会试图一口气做完整个项目留下半成品（Anthropic harness 教训）：一次只做一个功能、端到端验证通过才算完成、上期没验证不开新工。
- 「自动滚入下期」会让没做完的模块无限续命（Linear cycles）：采纳 Shape Up 断路器，同一候选失败两次即 declined。
- 单纯按分排序会全选低成本小改（Reforge 指出的 RICE 渐进主义）：用配比规则强制每 4 期至少 1 期数据/规则类、1 期清理期。
- 单人+AI 没有多方赌桌，会退化成拍脑袋：用「写下 3 个不选的理由」代替讨论；用户提想法时 Claude 必须先给反方（防 sycophancy）。
- 记忆/规则写在文档里只是「上下文」不是强制（Claude Code 文档明说）：行数上限、禁止 LLM 调用、禁止物理删除都要写成 Python 校验脚本并作为合并门禁。
### 知识库结构建议
目录 D:\机会监控\learn\（与站点 data/ 分开，整目录进 git，raw/ 的 zip 不追踪）。
learn/SOP.md：固定 11 步流程，改它需单独 commit。
learn/STATE.md：唯一常驻上下文，硬上限 200 行/25KB；段落固定：current_cycle、current_bet{id,branch,status}、last_cycle_result{id,tag}、pending_verification[]、budget{fetch_left,hours_left}、kb_metrics{pages,index_lines,claims,stale,candidates}、user_prefs（白话/少字/少图/只看结论）、do_not_research_again[{slug,date,reason}]、pm_acceptance（用户定的 3 条验收标准）。
learn/inbox/sources.yaml：RSS 源清单（本 JSON 的 sources 即种子），每条 {name,url,category,weight 1-3,user_agent(可选),retry(可选),last_ok,fail_count}；fail_count≥7 自动 enabled:false。
learn/inbox/<YYYY-WW>.jsonl：车道 1 每日追加，一行一条 {id:sha1(url)[:12],url,title,source,published,fetched,lang,tags[],status:new|accepted|declined|duplicate|snoozed|deferred,reason}。
learn/raw/<id>.md：不可变原文（frontmatter id,url,fetched,
### 打分规则说明
五项各 0–3 分，任一项为 0 直接淘汰。
1. value 价值（×2）：3=用户明确反馈过的痛点或直接改变「今天该怎么看」；2=让用户更快看懂现有判定（减字/减步骤/减滚动）；1=好看但不改变理解；0=用户没提过且对判定无影响（淘汰）。若 value 来自「我猜用户会喜欢」而非用户原话/行为 → 总分×0.8 并标 guess_penalty:true。
2. effort 成本（反向）：3=一个会话 ≤2 小时，只改一个前端区块或一个 Python 脚本；2=一个会话可完成但前后端都改；1=需两期；0=需接新数据源+前后端一起改（淘汰，先拆成「只接数据」候选）。只有 effort=3 才允许下注，effort=2 必须先拆。
3. needs_llm：3=纯规则/纯静态，线上零 LLM；2=需一次性人工整理的词表或映射；1=需每期由 Claude 会话手动更新的内容；0=站点运行时调用 LLM（一票否决，validate_site.py grep 拦截）。
4. plain_language 白话风险（反向）：3=新增可见文字 ≤20 字、无新术语、无新图；2=≤60 字或引入 1 个术语但有白话解释；1=需新增一张图或一个新交互（3 秒内能看懂）；0=用户需先学一个新概念（淘汰）。验证：validate_site.py 统计 diff 新增可见中文字数；glossary.md 未收录的英文缩写视为新术语。
5. data 数据可得：3=现有 data/*.json 字段直接可算；2=现有免费源可抓且本期 WebFetch 验证 200；1=免费但不稳定（限流/无 API/解析 HTML）；0=付费或需登录（淘汰）。
总分 = value×2 + effort + needs_llm + plain + data，满分 18。≥12 可下注，≥15 优先。同分裁决：
### 研究者建议的 SOP（与上面的步骤对照，取长补短）
1. S1 开工门禁（≤5 分钟）：只读三样——learn/SOP.md、learn/STATE.md（≤200 行：当前赌注/上期结果/待验证/指标/用户偏好/「不再研究」清单）、git log -5 与 git status。若 pending_verification 非空 → 先在浏览器跑上期验收标准；通过则 tag 并合并，不通过走 S8 断路器。本期硬预算写进 STATE：1 个模块、≤40 次 WebFetch、≤2 小时。
2. S2 读 inbox 并去重：读 learn/inbox/<本期>.jsonl（车道 1 每日追加，id=url sha1 前 12 位）；用 id 对比 wiki/sources.yaml 与 STATE.do_not_research_again，命中即标 duplicate/declined 不打开；剩余按 source.weight 排序取前 20，其余标 deferred（不进 backlog，下期 RSS 再出现就重新排队）。
3. S3 分诊：20 条逐条打四态——accept / decline（一行原因）/ duplicate（指向已有 claim id）/ snooze（只允许一次）。accept 上限 8 条，每条必须写一句「它可能改进站点的哪一块」（首屏/判定卡/规则表/日历/新闻/热力图/产品方法论），写不出就 decline。
4. S4 定向研究（固定三视角）：每条 accept 先 grep wiki/claims/ 看是否已有同 slug，有则只 UPDATE/NOOP 禁止新建；无则 WebFetch 原文存 learn/raw/<id>.md（不可变），按 3 个固定问题作答：①对「在泰国的非程序员投资者」，它能让哪个页面更快看懂？②需要的数据是否免费可得、URL 是什么？③能否不用 LLM 纯规则实现？产出 1 张 claim card（结论≤40 字、引文≤15 字+URL、confidence 0.3/0.5/0.7/0.9、valid_from、review_after=+90 天）。另记「检索到但没用上」≤3 条到本期日志 unused 段。每条 ≤8 次 WebFetch。用户提的功能想法，先写「不做的理由/复杂度」再写方案。
5. S5 更新知识库（四操作+硬上限）：每张 claim 走 ADD / UPDATE / SUPERSEDE（不物理删，status: superseded + superseded_by）/ NOOP；同步簿记：wiki/index.md 加或改一行、wiki/log.md 追加 `## [日期] ingest | 标题`、相关 topics/ 页更新（每页≤120 行）。然后跑 python learn/scripts/kb_lint.py：index≤200 行、STATE≤200 行、claims 总数≤300、frontmatter schema、断链、孤儿页、review_after 过期标 stale、连续两期 stale 且无引用 → archive/。lint 只自动修 ≤3 处。会改动 115 条规则中任一条的高风险 claim 必须两个独立来源才可 active。
6. S6 生成/刷新功能候选：本期新 claim 推导出的候选写入 learn/candidates.yaml（id、一句白话、from_claims、created、expires=created+3 期、pitch 三行：问题/方案/不做什么、acceptance 三条可验证标准）。既有候选到期未下注 → expired 并在日志列出（可见地消失）；续命必须重写 pitch。候选总数上限 15。
7. S7 打分与下注（单人赌桌）：按 scoring_rubric 给所有 open 候选打分，任一项 0 直接淘汰，总分≥12 才可下注；只选 1 个且 effort 档必须=3（单会话可完成）。配比：最近 4 期若已有 3 期是纯前端，本期强制选数据/规则类；每 4 期至少 1 期清理期（只 lint/去重/压缩 raw/，不加功能）。把选中 id 写入 STATE.current_bet，并写下 3 个落选者各一行不选理由。同时读上期用户反馈（看懂了/没看懂、对/错）按模块统计，归 <10 类只做第一名。
8. S8 实现（分支+验收+断路器）：git checkout -b cycle/<YYYY-WW>；先把 acceptance 三条写进本期日志再动代码；改动限制在一个模块；本地跑数据脚本与 python learn/scripts/validate_site.py（JSON schema、新增可见文字字数、术语表比对、grep 禁止 LLM 调用、用户的 3 条 PM 验收标准）；浏览器打开本地页面在 375px/1280px 截图核对。会话内未全部通过 → 不合并，分支保留，候选标 failed_once；第二次失败 → declined。绝不为了「做完」扩大时间或范围。每期只改一个变量（阈值/数据源/文案三选一）。
9. S9 写日志：learn/cycles/<YYYY-WW>.md 固定模板——做了什么（≤3 行）、学到什么（≤5 条，链 claim id）、unused（≤3 条）、下期明确不做什么、指标一行（inbox 条数/accept/新 claim/KB 页数/index 行数/stale 数/候选数）、changed_files（KB 与代码分开）、三个落选理由。重写 STATE.md：current_bet 结果、pending_verification、指标、do_not_research_again 追加本期 declined slug+日期。
10. S10 提交与可回滚发布：两次 commit——`kb: <YYYY-WW> ingest N claims` 与 `feat(<模块>): <一句白话>`；合并前再跑 kb_lint + validate_site；打 tag cycle-<YYYY-WW>。回滚：用户反馈「看不懂/页面坏了」→ 只 git revert 代码 commit（KB 保留）；KB 回退按日志 changed_files 逐文件 git checkout <上一 tag> -- <文件>。raw/ 每月 zip 归档，git 不追踪 zip。同时把本期一条写进 docs/changelog.html，改了阈值必须进 changelog。
11. S11 一句话汇报（≤60 字，白话）：本期加了什么、下期最可能做什么、是否需要用户拍板（只在候选分数并列或涉及规则改动时才问）；再只问用户 3 个「讲讲上一次你…」问题，答案写入 user_needs。每条建议标把握度（高/中/低）与依赖假设。
### 首轮发现的空白（下几期的候选主题）
- 中文与本地化排版规范完全缺席：50 条经验全部搬英文来源。中文用户的数字单位是 万/亿 而不是 k/m/b，中文行长按字数（约 34–40 字），中国金融 App 惯例是红涨绿跌（站点有开关但没研究默认值该选哪边），日期/时区应「曼谷 08:00（北京 09:00）」双显。下期研究少数派/人人都是产品经理/雪球·同花顺·财联社的界面复盘，写成一条「中文金融信息产品惯例」规范。
- 学习循环的数据回流通道缺失：多条建议依赖 localStorage 计数（模块点击、visits、看懂/没看懂、对/错），但用户在手机与电脑两端看站，localStorage 互不相通，Claude 也读不到。需要免费、无后端、隐私友好的回流方案写进 LOOP.md：候选 GoatCounter（免费托管计数）、GitHub Issues 预填链接、或用户每期粘贴一段「导出反馈」给 Claude；否则观测数据都是死数据。
- 站点「静默过期」没有客户端检测：GitHub Actions 失败或限流时页面停在旧版，构建时间戳只能说明上次构建何时。需要 app.js 用内联的构建时间对比当前时间，超过 14 小时首屏红字「数据可能已过期（上次更新 X 小时前）」，并在 Actions 加失败通知。这是泰国网络+免费运行器最常见的失败模式。
- 没有真实用户任务成功率的测量方法：3 条验收标准有了但没给怎么测。每期做一次 5-second test（给用户看首屏 5 秒，问「今天该不该动、为什么」），用浏览器工具在 375px/1280px 各截一张图，记录答对/答错，作为字数预算与折叠策略的唯一量化反馈。
- 来源过度集中且缺少同行对标：NN/g 占 12/50、几乎无中文来源、没有任何金融信息产品的界面研究（Bloomberg Terminal 单屏密度、TradingView watchlist、Koyfin 仪表盘、财联社电报「一句话快讯」体例、Polymarket/Metaculus 概率呈现）。「顶尖金融分析网站 10 大功能」框架本身也没有出处。LOOP.md 规定每期 ≤3 个主题中至少 1 个是竞品对标，单一机构来源 ≤30%。
- 推送通道的真实可行性没有对比：Web Push 在 GitHub Pages 无推送服务器不可行，而 ntfy / Telegram Bot / 邮件都能由 GitHub Actions 在构建后免费直接发送，这才是「让用户定时间」的可执行路径。需要一页对比（Atom / ntfy / Telegram / 邮件 / 无）并让用户选一个。
- 泰铢换汇窗口 + 泰国持牌所溢价：用户拿泰铢工资，站点已有 px.USDTHB 580 天历史却没用上。已验证 Bitkub 公开接口 https://api.bitkub.com/api/market/ticker 免费返回 THB_BTC。第一版：derived.py 加两个指标——THB 处于 90 天区间的百分位、Bitkub 溢价 = BTC/THB ÷ (BTC/USD × USDTHB) − 1；两条规则「泰铢处于 90 天最强/最弱 10% → 换汇窗口」「溢价 >2% → 本地抢购/资本外流信号」；首屏只加一个数字。
- 泰国电力主场（用他的专业做差异化）：现有只有一条新闻规则 ai.th.datacenter 和 static.yaml 的静态锚点，没有一个会动的数字。可核验来源：ERC 每 4 个月公布 Ft 电价（https://www.nationthailand.com/news/general/40068945 ），EGAT 统计页 https://www.egat.co.th/home/en/category/business-ops/stats/ 有系统峰值。第一版：config/thai_power.yaml 人工维护（每 4 个月 1 条，用户自己最懂），calendar.yaml 加 ERC Ft 公告日、EGAT 峰值季（4–5 月）、EEC 变电站交付点；规则「Ft 上调 → 数据中心用电成本判断变化」；把「我的判断日志」优先开给这条主线。
- 曼谷时间与泰国本地日历：所有事件按曼谷时间显示并标「你睡觉时发生」（FOMC 决议是曼谷凌晨 01:00–02:00，美股开盘 20:30/21:30），推送默认曼谷 07:00 发。补 BOT 货币政策委员会一年 6 次会议（https://www.bot.or.th/en/our-roles/monetary-policy/mpc-meeting.html ）、泰国假日休市、3 月 31 日个税申报、泰国 SEC 加密新规。第一版：calendar.yaml 加 category: thai 的 ≤10 条，前端时间显示带「曼谷」二字。
- 仓位对照（报告建议 vs 我持有）：watchlist.yaml 已给每个币定了 tier（核心/卫星/期权/观察/回避），但站点从不知道用户持有什么。第一版与「我的关注」合并：星标旁多一个「我持有」开关（localStorage，不记金额），首页「我的」区加 ≤5 行对照：「你持有但报告说回避：X」「报告核心而你没有：Y」「你持有的今天触发了：Z」。无新数据、无 LLM。
- 黄金按泰铢重计价（本地避险品）：泰国人买金按「泰铢重」（1 บาททอง = 15.244 克、96.5% 成色），战争风险主线的避险判断只给美元/盎司金价，用户去金店对不上。第一版：derived.py 用已有 px.GOLD × px.USDTHB × 15.244/31.1035 × 0.965 派生「每泰铢重金价 ≈ X 泰铢」，首屏一个数字 + 与 30 天前比较的 ▲▼；不抓金店牌价，不加图。
