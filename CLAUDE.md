# 机会监控 · 给 Claude Code 的项目说明（任何账户都会自动加载）

1. 先读 `HANDOVER.md`（交接证书：接手清单、架构、约定）和 `PROGRESS.md`（断点与待办），再动手。同一台电脑换账户：直接打开这个文件夹即可，不用从 GitHub 重新下载；只需重建学习循环的计划任务（见 HANDOVER.md A.3）。
2. 运行时不用大模型；界面白话、少字、少图；数据与规则链条不动（除非修 bug 并记日志）。
3. 每做一步更新 `PROGRESS.md`；每完成一版用 `python scripts/release.py "说明"` 发布（自动提交白名单、推送、打标签、刷新交接证书、建 Release）。
4. 永远不 `git add -A`、不提交 `data/`；冲突时数据以远端为准。
5. 学习循环的 SOP 在 `learning/LOOP.md`；学习页在 `docs/learn.html`（由 `scripts/learn_intake.py` 与 `src/monitor/learn_page.py` 生成）。
6. 本机预览：`.claude/launch.json` 的 `site`（端口 8791）。浏览器面板隐藏时先 `resize_window` 再截图/量 DOM。
