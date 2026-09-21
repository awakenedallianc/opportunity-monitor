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
