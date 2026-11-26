# AG-002 任務交接結果

- 任務 ID／標題：AG-002 — 報告四層圖與公式對照
- 交付者／審查者：Antigravity ／ Codex
- 狀態：ready_for_review
- 基準 commit：`51648b7bb00ed5841931c4bebc805aa36c6e2520`（程式交付基準 `9225d6be262071ab8ad31d6fb1f8b76526a5b04e`）
- 工作分支／交付 commit：`antigravity/AG-002-diagram-formula-review`（交付 commit 為本分支最新提交，尚未推送或合併至 `main`）

## 需求與驗收

- 對應需求：R27、R28；任務範圍見 `docs/collaboration/tasks.md`（AG-002）。
- 驗收要點：
  1. 四層架構圖一致、每條連線具備資料／協定語意、現有與待部署／外部整合標示一致。
  2. 逐式核對 `docs/report/methods.md` 符號、單位、旋轉方向、測距殘差與真實誤差之區別，並對照 `src/ble_inventory/` 與 `scripts/` 實作。
  3. 產出修正後圖檔、圖說、審查與勘誤清單；沒有實測資料的圖表維持空位，不代填數字。
  4. 不直接修改 `docs/report/methods.md`、定位核心程式或 `docs/progress/state.json`。

## 允許修改範圍與實際修改檔案

- 允許修改範圍：`docs/report/diagrams/`、新增 `docs/report/diagram-review.md` 與 `docs/handoffs/AG-002-result.md`。
- 實際修改檔案（嚴格限於允許範圍）：
  - `docs/report/diagrams/01-context.md`（更新第一層系統全景圖、補齊虛線狀態與 AWS→Viewer 路徑、補圖例與部署差異圖說）
  - `docs/report/diagrams/02-deployment.md`（更新第二層部署圖、明確區分 RPi `0bdeea4` 與新版 `9225d6b` 狀態、補齊全部內部與外部連線協定／資料標籤與 OSM 選用底圖）
  - `docs/report/diagrams/03-software.md`（更新第三層軟體模組圖、修正 `server.py` 與 `engine.py` 相依方向、補入 `config.py`/`site_settings.py`/`web/site-settings.js`/`calibrate-rssi.py` 與全部連線語意）
  - `docs/report/diagrams/04-sequence.md`（更新第四層兩張序列圖、補上非法／含真值批次拒收分支、兩階段條件與參數、`GET /api/settings` 初始讀取及 `400`/`409`/`507`＋`aborted.txt` 回復路徑）
  - `docs/report/diagram-review.md`（新增完整四圖審查修正表、14 項公式／文件／程式對照勘誤 F-01～F-14、以及待補實測表位查核）
  - `docs/handoffs/AG-002-result.md`（本交接檔）
- 介面或資料格式影響：無（僅文件與 Mermaid 架構圖；未改動任何程式碼、schema 或設定檔）。

## 測試環境、執行命令與驗證結果

- 測試環境／版本：Windows；獨立 clone 目錄 `C:\Users\user\.gemini\antigravity\scratch\ble-mobile-inventory`；Python 3.14.3（含 NumPy）。
- 執行命令：
  1. `git rev-parse HEAD && git status --short --branch`
  2. `python scripts/evaluate-run.py web/public/demo.json tests/fixtures/truth.jsonl --output <scratch>/eval-check.json`
  3. 獨立數學、座標與圖檔檢查腳本（於本機 scratch 執行，未寫入儲存庫）：驗證 §2 濾波手算值、§3 範例測距、§4 高度差與拒絕邊界、§5–§6 多邊定位與離群測試、§8 旋轉矩陣正交性／行列式／旋轉方向／台北多角度往返、F-06 邊界重現、四份圖檔 Mermaid 連線標籤完整性，以及 `docs/report/` 本地 Markdown 連結檢查。
- 預期／實際結果：
  - **合成基準重現（`TEST-005` 對照）**：`skipped_unmatched = 0`；`RPi01` 90 筆（MAE `1.043 m`、RMSE `1.106 m`、P50 `1.029 m`、P95 `1.734 m`）、`T01` 85 筆（MAE `0.464 m`、RMSE `0.802 m`、P50 `0.305 m`、P95 `1.809 m`）、`T02` 65 筆（MAE `0.220 m`、RMSE `0.349 m`、P50 `0.116 m`、P95 `1.029 m`）。與 `methods.md` §11 數值完全一致，僅 §11 表格缺 P50 欄（記為 F-13）。
  - **公式獨立數值驗證**：
    - §2 濾波手算 `[-70.0, -76.5, -73.575, -72.55125]` 與 `RssiFilter(0.65, 3)` 誤差 `< 1e-12`；同時確認 `RssiFilter()` 預設值仍為 `(0.4, 5)`（記為 F-03）。
    - §3 `rssi_to_distance(-79, -59, 2) = 10.0 m`；§4 `horizontal_distance(5, 3) = 4.0 m` 且 `slant == |dh|` 正確拋出 `ValueError`。
    - §5–§6 無噪四點求解誤差 `8.88e-16 m`；`A01` 單點 `+6.0 m` 離群實驗中真實位置誤差 `5.110 m`、未加權殘差 `1.796 m`（記為 F-09）。
    - §8 ENU 旋轉矩陣正交誤差 `1.11e-16`、`det(R) = 1.0`、`0°` 時 +X 向東、`90°` 時 +X 向北且 +Y 向西；台北原點六組角度（`0/25/37/90/-135/360°`）往返最大誤差 `1.39e-9 m`。
    - F-06 重現：傳入 `{"device_id": "A01", "rssi_dbm": -70.0, "rssi_at_1m_dbm": None}` 通過 `validate_batch` 後於 `InventoryEngine.ingest` 觸發 `TypeError: must be real number, not NoneType`。
  - **圖檔與連結檢查**：4 份圖檔共 5 個 Mermaid 區塊；所有 `flowchart` 連線均具資料／協定標籤（無標籤數 `0`）；`docs/report/` 本地 Markdown 連結失效數 `0`。
- 證據：
  - `docs/report/diagram-review.md`
  - `docs/report/diagrams/01-context.md`～`04-sequence.md`
  - `git diff` 於分支 `antigravity/AG-002-diagram-formula-review`
- 未執行項目及原因：
  - 未重跑 `pytest`、`npm test`、`npm run build` 或 PlatformIO：依 `docs/collaboration/test-matrix.md`（只改報告／圖檔不為計算進度重跑所有程式與硬體流程），本次未修改任何程式碼或前端檔案。
  - 未進行實體 BLE、Gazebo 或 AWS 實測：硬體尚未刷機（`HW-001`）、Gazebo 待組員交付（`SIM-001`）、AWS 尚未部署（`CDX-CLOUD`）。

## 問題重現與修正

- **圖檔問題（已於本分支修正）**：D1-1～D1-4、D2-1～D2-3、D3-1～D3-3、D4-1～D4-2，詳見 `docs/report/diagram-review.md` 第二節。
- **公式與文件／程式對照勘誤（依範圍未直接修改核心或 `methods.md`，交 Codex 審查）**：F-01～F-14，詳見 `docs/report/diagram-review.md` 第三節。其中較需優先考量者為：
  - **F-01**：`methods.md` §6 與 §10 重用符號 $e$ 分別表示有號測距殘差與非負真實位置誤差。
  - **F-06**：`engine.py:59` 在 `obs["rssi_at_1m_dbm"]` 為 `None` 時觸發 `TypeError`（已重現）。
  - **F-07**：WGS84 Anchor 橢球高與 Local 高度基準對齊須於操作與報告明確強調。
  - **F-11**：`docs/design/coordinates.md` L18 殘留舊 wording「相對正北旋轉角」，與正式約定「Local +X 相對正東逆時針角」矛盾。

## 剩餘限制／阻塞

- 實體 BLE（`HW-001`）、Gazebo 整合（`SIM-001`）、AWS 部署（`CDX-CLOUD`）及 RPi 新版座標設定部署（`ISSUE-010`）仍未完成；所有圖檔與審查表已如實標示待部署／待實測狀態，未以軟體或合成結果冒充實測完成。
- Mermaid 語法已依儲存庫既有慣例與規則靜態檢查，待 Codex 合併後於 GitHub／Markdown 檢視器抽查最終渲染版面。

## 合併注意事項

- 本分支僅修改 `docs/report/diagrams/*.md` 與新增 `docs/report/diagram-review.md`、`docs/handoffs/AG-002-result.md`，不與 Codex 程式模組衝突。
- 若 Codex 採納 F-01～F-14 勘誤，建議另開 commit 修訂 `docs/report/methods.md`、`docs/report/report-draft.md`、`docs/design/coordinates.md` 及 `src/ble_inventory/engine.py`（F-06），並視需要補充單元測試。

## 部署與還原方式

- 不涉及 RPi 或 AWS 部署。
- 如需還原四份圖檔，直接 `git checkout 51648b7bb00ed5841931c4bebc805aa36c6e2520 -- docs/report/diagrams/` 並移除新增的 `docs/report/diagram-review.md` 與 `docs/handoffs/AG-002-result.md`。

## 報告／進度需更新處

- 請 Codex 審查合併後更新：
  - `docs/progress/state.json`（將 `AG-002` 更新為 `ready_for_review` 或 `verified`）並執行 `scripts/render-progress.py`。
  - `docs/report/methods.md`（依採納之 F-01～F-13 勘誤修訂，含 §11 補入 P50 欄）。
  - `docs/issues.md`（若決定追蹤 F-06 `rssi_at_1m_dbm: null` 防禦修補）。

## 下一個具體動作

1. Codex 審查分支 `antigravity/AG-002-diagram-formula-review` 之四圖更新與 `docs/report/diagram-review.md` 勘誤清單。
2. Antigravity 依指示接續執行 **AG-001（本地座標設定獨立驗證）**（於獨立分支 `antigravity/AG-001-settings-review` 建立 `tests/test_settings_independent.py` 與 `docs/handoffs/AG-001-result.md`），完成後再進入 **AG-003（實驗彙整工具開發，先提交設計與輸入格式再實作）**。
