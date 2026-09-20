# 进度与断点记录（PROGRESS.md）

> 目的：会话中断、token 受限、换电脑后都能从这里接上，**不要重跑已完成的工作**。

## 断点（2026-09-20 22:05 曼谷）— 本地版本已完成并可用；仅剩"发布到 GitHub Pages"待用户确认

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
- [ ] 运行 rules-vs-reports 核对（会话限额恢复后）；合并 data/raw/extracted_claims.json（extract:crypto 108 条已保存；ai/war 提取因限额未完成）
- [ ] 合并三篇报告的结构化提取结果（补规则/日历/基线遗漏）
- [ ] 修完后：`python run.py --only yahoo,defillama,extras` → `python run.py --build-only` → 浏览器检查（本地 http://localhost:8791，服务由 .claude/launch.json 的 site 配置启动）
- [ ] **待用户确认后**发布：`powershell -ExecutionPolicy Bypass -File scripts\publish_github.ps1 -Repo opportunity-monitor`（公开仓库 = 站点公开；原报告默认不上传）

## 已知限制（泰国网络）
- FRED 不可达（熔断，财政部曲线兜底）；Farside/ISW 原站/Metaculus 403；GDELT 429；Stooq 需 JS 挑战
- Binance 主站在 GitHub 美国运行器 451 → 已回退 data-api.binance.vision；CoinGecko 失败时主流币价格由 Binance 兜底（降级标记）
- 本机 pandas 与 numpy 2.4 不兼容 → 项目不依赖 pandas

## 常用命令
```
python run.py                 # 全量（首轮回填约 400 天历史，约 8 分钟）
python run.py --resume        # 断点续跑（跳过 3 小时内已完成的抓取器）
python run.py --only extras,polymarket
python run.py --build-only    # 只重建页面
python run.py --import-only   # 从 data/snapshots + data/news_archive 重建历史库
python scripts/local_boot.py --skip-run --no-open
powershell -ExecutionPolicy Bypass -File scripts\install_task.ps1
```

## 变更日志
- 2026-09-20 项目创建；报告→规则；首轮运行；计划任务；断点续跑；部署修正；数据复核修正（进行中）
