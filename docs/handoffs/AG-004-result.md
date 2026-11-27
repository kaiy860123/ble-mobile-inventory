# AG-004 任務交接結果

- 任務 ID／標題：AG-004 — Gazebo 合作組員整合交接簡報資料與實作手冊
- 交付者／審查者：Antigravity ／ Codex
- 基準 commit：`f2c1d0c2d9bd6328e30e87cd7aaa514a1a9091bb`
- 工作分支／交付 commit：Codex 預先建立之工作分支（依派工規則本階段僅使用內建檔案讀寫工具，未執行 git 或 shell 指令；既有 AG-002 交付完整保留）

## 需求與驗收對應

- 目標：產出交給 Gazebo 合作組員（`SIM-001`）之繁體中文、工程實作導向 22 頁簡報版型資料與可直接操作之整合手冊，供 Codex 以 presentation 工具執行 1280×720（正文等效 >= 17pt、專業白底深藍綠風格、原生可編輯表格與資料流）成品生成及逐頁 QA。
- 允許修改範圍（嚴格遵守，允許前綴為空）：
  - `docs/handoffs/AG-004-slides.json`
  - `docs/handoffs/AG-004-integration-guide.md`
  - `docs/handoffs/AG-004-result.md`
- 實際新增／修改檔案（僅此 3 檔，未改核心程式、設定、既有測試、AWS／RPi 設定或 AG-002 交付）：
  1. `docs/handoffs/AG-004-slides.json` — 22 頁結構化簡報資料（頂層含 `title`、`date`、`baseline_sha`、`slides`；涵蓋交接目標、現況證據、分工、系統全景、部署協定、觀測欄位、合法 JSON、Local 框架與高度、時鐘映射與暫停、RSSI 模型與數值試算、兩階段定位、服務啟動與 token、送出器與 curl、生命週期與錯誤碼、獨立真值樣本、評估 CLI、實驗 metadata 與彙整、正常整合測試、異常測試矩陣、交付目錄與版本、12/10・12/17・12/24 里程碑、最終驗收清單）。
  2. `docs/handoffs/AG-004-integration-guide.md` — 可直接操作之 Gazebo 整合實作手冊（含完整可貼用 observation JSON／JSONL、truth JSONL、逐項核對 `argparse` 的 bash／PowerShell 啟動與評估命令、正常與 7 項異常測試矩陣、組員交付包結構與 README 必填檢查項）。
  3. `docs/handoffs/AG-004-result.md` — 本交接報告。
- 介面或資料格式影響：無修改既有程式介面或契約 schema；純交接文件與簡報結構化資料產出。

## 逐頁事實與版型自查摘要

1. **總頁數與版型**：共 22 頁（`S01`–`S22`），版型嚴格限於允許清單：`cover`（1）、`table`（6）、`two-column`（4）、`diagram`（2）、`code`（5）、`formula`（2）、`bullets`（2）。
2. **密度與結構限制**：
   - 每頁均含 `id`、`title`、`layout`、`subtitle`、`bullets`、`notes`、`sources`；`bullets` 皆 <= 5 條短句。
   - 所有 `table` 頁（`S02`/`S05`/`S06`/`S14`/`S19`/`S21`）皆 <= 6 rows、<= 5 columns，且每列欄數與 `headers` 一致。
   - 所有 `code` 頁（`S07`=14 行、`S12`=12 行、`S13`=12 行、`S15`=4 行、`S17`=11 行）皆 <= 14 行。
   - 所有 `diagram` 頁（`S04`/`S09`）之 `edges` 端點均對應 `nodes[].id`。
   - 所有 `formula` 頁（`S10`/`S16`）均含 `expression`、`meaning`、`example`。
3. **命令與實作 `argparse` 核對**：
   - `src/ble_inventory/cli.py`：`serve` 僅用實有旗標 `--config`、`--root`、`--mode`、`--host`、`--port`；標明 `external` 模式強制環境變數 `BLE_INGEST_TOKEN` 且 `--config` 須位於 `<root>/config`。
   - `scripts/send-observations.py`：僅用位置參數 `file` 與 `--url`，標明其覆寫 `timestamp=time.time()` 並重編 `sequence`，僅作檔案送出器非 Gazebo 模型。
   - `scripts/evaluate-run.py`：僅用位置參數 `states`、`truth` 與 `--max-time-delta-s`（預設 `0.25`）、`--output`；核對 `(run_id, device_id, position_at)` 去重與 `truth_used_by_solver=False`。
   - `scripts/summarize-experiments.py`：僅用 `_build_parser()` 實有旗標（`--experiment-id`、`--source`、`--site`、`--route`、`--version`、`--run-id`、`--evaluation`、`--states`、`--scheduled-eval-points`、`--expected-targets`、`--scanner-id`、`--limitations`、`--csv-out`、`--md-out`、`--json-out`、`--format`、`--manifest`）。
4. **物理、契約與現況誠實性核對**：
   - 契約規則：Unix UTC 秒、±30 秒即時 API 容許窗口、`sequence` 歸零須開新巡查、同批 `device_id` 唯一且空批合法、`additionalProperties: false` 拒絕真值。
   - 座標與高度：Local 公尺零旋轉 `+X` 東 `+Y` 北、旋轉角自正東逆時針、已知 `scanner_height_m` 可輸入、掃描器 XY 與 Target 真值嚴格另存。
   - RSSI 數學例：$r(d) = P_{1\text{m}} - 10n\log_{10}(d/d_0) + \varepsilon$，以 $P_{1\text{m}}=-59\text{ dBm}$、$n=2$、$d=2\text{ m}$ 得約 $-65.02\text{ dBm}$，明確標註僅為數學試算例、非實體量測；區分真實位置誤差 $e_k$ 與求解器殘差 $R_{\text{range}}$。
   - 現況邊界：明確說明 AWS Sydney 部署與 PC 合成 TLS→WSS 唯讀通路通過（`TEST-027`）；六塊 XIAO 各別刷機與各別 Windows 解碼通過（`TEST-021`–`026`）；RPi 新版、六塊同時收包／校正／精度與 RPi 上雲仍待辦（未要求使用者現在進行實體通電）；Gazebo 尚未交付，嚴禁假稱已串接。
   - 隱私與安全：未包含任何私人 email、私有 IP、帳號密碼、金鑰、實際 token 或個人本機 Windows 路徑；僅提供公開 GitHub 儲存庫與公開 GitHub Pages 連結。

## 測試環境、執行狀態與證據

> **本階段測試及版面渲染未執行，由 Codex 接續**（本階段測試未執行，由 Codex 接續）。

- 測試環境／版本：本階段屬純內建檔案編輯交付階段（依派工限制未使用終端、shell、命令、瀏覽器或 MCP 工具），未執行 JSON schema 腳本驗證、Python 測試或簡報 PPTX／PDF 渲染與逐頁視覺 QA。
- 建議 Codex 接續執行檢查：
  1. 解析驗證 `docs/handoffs/AG-004-slides.json` 為合法 UTF-8 JSON，確認共 22 頁且各版型欄位、行數（<=14）、表格（<=6×5）、bullets（<=5）及 `sources` 路徑皆存在。
  2. 以 presentation 工具依 1280×720、正文等效 >= 17pt、專業白底深藍綠工程簡報風格、原生可編輯表格與流程圖規格產生簡報成品，並執行逐頁視覺 QA（檢查文字溢出、表格換行、箭頭遮擋與字級）。
  3. 視需要抽測 `AG-004-integration-guide.md` 中之 `cli.py`、`send-observations.py`、`evaluate-run.py` 與 `summarize-experiments.py` 命令旗標及既有 `pytest` 回歸。
- 證據檔案：
  - `docs/handoffs/AG-004-slides.json`
  - `docs/handoffs/AG-004-integration-guide.md`
  - `docs/handoffs/AG-004-result.md`
- 未執行項目及原因：JSON 程式解析驗證、簡報成品生成與逐頁版面渲染 QA 均未執行（受本階段純檔案編輯工具限制，由 Codex 接續執行）。

## 剩餘限制、合併與後續動作

- 剩餘限制：
  - 簡報視覺排版仍須經 Codex 渲染後實測逐頁字數與圖表節點間距；若個別 `code` 或 `table` 儲存格在 >= 17pt 下有換行過密現象，Codex 可微調換行並保留完整細節於 `notes` 與 `AG-004-integration-guide.md`。
  - Gazebo 組員實際版本、場景檔與實驗紀錄尚未交付（`SIM-001` 仍待外部交付），手冊中相關處均明確標註「待提供」。
- 合併注意事項與還原方式：僅新增 3 個 `docs/handoffs/AG-004-*` 檔案，不影響核心程式與既有交付；還原只需移除此 3 檔即可回到基準 `f2c1d0c2d9bd6328e30e87cd7aaa514a1a9091bb`。
- 報告／進度需更新處（交由 Codex 驗收後統一更新）：`docs/progress/state.json`（並執行 `scripts/render-progress.py`）與 `docs/collaboration/tasks.md`。
- 下一個具體動作：由 Codex 驗證 `docs/handoffs/AG-004-slides.json`、產出可交付之簡報成品並完成逐頁 QA，驗收通過後交付給 Gazebo 合作組員。

- 狀態：ready_for_review
