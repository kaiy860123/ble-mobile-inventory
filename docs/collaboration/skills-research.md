# 進度呈現工具評估

查核：2026-11-26。目標是在 Codex 直接查看整體進度、證據、負責人與阻塞原因。

- [project-map](https://github.com/ShlomiPorush/agent-skills/blob/main/project-map/SKILL.md)：有文件／程式／驗證證據與缺口盤點的概念；但其預設輸出語言、專屬目錄及驗證流程不直接符合本專題。此次僅查閱評估，未安裝、未啟用其指令或代理流程。
- [agent-progress](https://github.com/AlexDM0/agent-progress)：主要面向 Claude Code 與 Bun 的獨立追蹤工作流，為本需求增加額外維護；未安裝。
- 採用既有 visualize 能力，進度資料以 `docs/progress/state.json` 保存，執行 `python scripts/render-progress.py` 產生 Codex 內可互動檢視。只依實際證據更新，不推估完成百分比，不假設可背景讀取 Antigravity 私人對話。

範本位於 `docs/progress/template.html`；日期為快照日期，非即時監控。其他開發者透過交接回報，Codex 作整合更新。
