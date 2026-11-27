# AG-005 任務交接結果

- 任務 ID／標題：AG-005 — 六 Anchor 與原四 Anchor 公平離線比較工具及實驗說明
- 交付者／審查者：Antigravity ／ Codex
- 基準 commit：`e353b3579a7f9b33af637eb365f8937bdb2b8d3c`（保留先前 AG-002 等既有交付）
- 工作分支／交付 commit：Codex 預先建立之 AG-005 工作分支（依派工規則本階段僅使用內建檔案讀寫工具，未執行任何 git／終端指令）

---

## 一、需求與驗收對應

- 背景與邊界：
  - 上輪四點校正候選模型於 TEST-037 導致 `T01` 有效位置由 156 降至 19，已由 Codex 拒絕並回退原模型；本交付不復用候選模型，亦不宣告任何實機精度改善。
  - 目前實機僅有 A01–A04，A05／A06 尚未刷機與量測；本交付僅提供純離線比較工具、合成單元測試與未來實機實驗說明，未觸碰 RPi、AWS、帳號設定、核心程式或實測原始檔。
- 允許修改範圍（嚴格遵守，允許前綴為空）：
  - `scripts/compare-anchor-subsets.py`
  - `tests/test_anchor_comparison.py`
  - `docs/testing/six-anchor-experiment.md`
  - `docs/handoffs/AG-005-result.md`
- 實際新增／修改檔案（僅此 4 檔）：
  1. `scripts/compare-anchor-subsets.py` — 六 Anchor 與原四 Anchor 公平離線消融比較工具（CLI 與可匯入函式庫）。
  2. `tests/test_anchor_comparison.py` — 獨立幾何合成資料與邊界條件單元測試（全部明確標註為 synthetic／`simulation`，絕不冒充 `physical`）。
  3. `docs/testing/six-anchor-experiment.md` — 白話版六 Anchor 與四 Anchor 公平比較實驗指南。
  4. `docs/handoffs/AG-005-result.md` — 本交接報告。
- 介面或資料格式影響：無修改 `src/`、`firmware/`、`config/`、`infra/` 或既有 schema；新增純離線比較腳本與 JSON 輸出格式（`schema_version: "1.0"`, `comparison_kind: "anchor-subset-ablation"`）。

---

## 二、實作重點摘要

### 2.1 `scripts/compare-anchor-subsets.py`
- **CLI 參數**：
  - 位置參數：`observations`（原始觀測 JSONL）、`config`（場地設定 JSON）
  - 選用參數：`--baseline-anchors`（預設 `A01,A02,A03,A04`）、`--expanded-anchors`（預設 `A01,A02,A03,A04,A05,A06`）、`--truth`（選用獨立真值 JSONL）、`--max-time-delta-s`（預設 `0.25`）、`--output`（選用輸出 JSON 路徑，並檢查不可覆寫任何輸入檔）、`--version`（選用版本／commit 標記，省略時採用 `ble_inventory.__version__`）。
- **嚴格前段校驗（先驗證完整原始 batch 再過濾）**：
  - 使用 `normalize_config` 校驗設定檔；對每一批完整原始觀測呼叫 `validate_batch`（並額外拒絕以 `bool` 混充數值／序號），在任何 Anchor 過濾之前即拒絕非法欄位、內嵌真值、單批重複設備、超出範圍 RSSI、空檔、混合 `source`、混合或與設定不符的 `scanner_id`、重複或倒序 `sequence` 與倒序 `timestamp`。
  - 驗證 `baseline` 必須含至少 3 個不重複 ID、為 `expanded` 的真子集；所有 `expanded` ID 均須存在設定檔且 `role == "anchor"`，且**實際出現於原始觀測中**，缺 `A05`/`A06` 明確拒絕，避免將四 Anchor 資料標成六 Anchor。
- **公平冷啟動消融重播**：
  - 兩組各自以 `copy.deepcopy` 複製同一份正規化設定並建立冷啟動 `InventoryEngine`，僅移除不屬該組的 Anchor 設定與 Anchor 觀測；完整保留同批 Target 觀測、`timestamp`、`sequence`、`source`、`scanner_height_m`、RSSI 模型與濾波參數，並以 `snapshot(now=batch["timestamp"])` 取得確定性狀態。
  - 真值檔僅在兩組重播完成後於離線評估階段使用，絕不進入任一 `InventoryEngine`（輸出固定 `truth_used_by_solver: false`）。
- **去重與統計指標**：
  - 每組各設備（掃描器與各 Target）有效位置數嚴格依 `position_at` 去重，僅計算 `quality == "valid"` 且出現新 `position_at` 的解算，快取沿用的舊位置記入 `duplicate_valid_positions_ignored` 而不重複計分。
  - 若提供 `--truth`，依 `position_at` 對齊最近真值且不超過 `--max-time-delta-s`，僅計算水平（XY）歐氏誤差（忽略 Z）；缺 scanner 真值時不報 RPi 誤差（`error_metrics: null`）。
  - 每組分別輸出 `samples`（N）、`mae_m`、`rmse_m`、`p50_m`、`p95_m`；另於 `common_valid` 輸出兩組共同有效同 `position_at` 的 `common_valid_positions`、`matched_samples`、`baseline_rmse_m`、`expanded_rmse_m`、`baseline_mae_m`、`expanded_mae_m` 與 `rmse_delta_m`。
  - 無真值時 `error_metrics` 皆為 `null`，有效位置數仍照實回報；未提供預先定義評估時點時 `formal_success_rate` 一律為 `null`，不以原始批數充當分母。
  - 輸出記錄 `schema_version`、`observations_sha256`、`config_sha256`、`truth_sha256`、兩組 ID、輸入批數、`source`、版本與 `limitations`，完全排除 `cloud` 私密設定、憑證路徑與主機資訊，且不修改輸入檔。

### 2.2 `tests/test_anchor_comparison.py`
全部使用獨立歐氏距離與對數距離公式產生的合成幾何資料（`source="simulation"`，註明不可冒充 `physical`），涵蓋 10 組測試函式：
1. `test_synthetic_independent_geometry_and_hand_calculated_errors`：12 批無噪聲合成軌跡驗證精確回復，加上已知水平偏移 `[1.0, 3.0, 5.0, 7.0]`（含 `+50 m` Z 偏移驗證忽略高度差）對照手算 `N=4`、`MAE=4.0`、`RMSE=sqrt(21)`、`P50=4.0`、`P95=6.7`。
2. `test_baseline_and_expanded_use_different_anchors_but_identical_targets`：攔截兩個 `InventoryEngine` 實例，驗證設定獨立 deepcopy、Anchor 子集確實不同，但 Target 觀測、時間戳、序號、高度、模型與濾波參數完全相同。
3. `test_cold_start_reproducibility_and_no_private_config_leak`：連續執行兩次輸出完全一致（冷啟動可重現），且輸出不含 `cloud` endpoint、憑證／金鑰路徑或本地路徑。
4. `test_cached_position_deduplication_counts_only_new_valid_position_at`：在 `T01` 成為 `valid` 後省略後續兩批 `T01` 觀測（仍在 `stale_after_s` 內保持 `quality="valid"` 與舊 `position_at`），驗證 `valid_positions == 3`、`duplicate_valid_positions_ignored == 2`，絕不重複計分。
5. `test_common_valid_vs_own_valid_samples_and_anchor_difference`：4 批隔離測試（第 0 批僅 expanded 有效、第 1–2 批共同有效且第 2 批含 `A01` 擾動使六 Anchor RMSE 低於四 Anchor、第 3 批 `A05` 離群使僅 baseline 有效），驗證各自有效樣本 `N=3` 與共同有效樣本 `N=2` 明確區分且 RMSE 正確分離計算。
6. `test_without_truth_and_target_only_truth`：驗證無真值時所有 `error_metrics` 為 `null` 但有效數照報；僅 Target 真值（`scanner: null`）時不報 RPi 誤差而正常報 Target 誤差；以及 `--max-time-delta-s` 容差邊界。
7. `test_rejects_missing_expanded_anchors_and_invalid_subsets`：驗證缺 `A05`/`A06` 或缺 `A06` 之原始觀測明確拒絕，以及少於 3 個基準 Anchor、非真子集、非子集、重複 ID、Target 冒充 Anchor、設定檔缺少 Anchor 皆拋出 `ValueError`。
8. `test_rejects_empty_mixed_duplicate_out_of_order_and_invalid_raw_before_filtering`：驗證空檔、混合 `source`、混合／不符 `scanner_id`、重複／倒序 `sequence`、倒序 `timestamp`、被過濾 Anchor（`A05`/`A06`）之非法 RSSI／重複 ID 於過濾前即被拒絕，以及非法 `max_time_delta_s`。
9. `test_truth_never_enters_solver_and_embedded_truth_rejected`：驗證內嵌真值被拒，且離線真值絕不進入 `InventoryEngine.ingest`。
10. `test_cli_end_to_end_and_input_overwrite_guard`：驗證 CLI 端到端參數解析、JSON 輸出與 stdout 一致，且禁止覆寫任一輸入檔。

### 2.3 `docs/testing/six-anchor-experiment.md`
白話說明現況（`A05`/`A06` 僅候選未刷機未量測、上輪候選模型已拒絕回退）、實體固定方向與高度要求、先六 Anchor 錄製再用同資料做四／六消融流程、新保留靜態點與至少三條不同轉折路徑設計、預先定義評估時點與容許新鮮度才算正式成功率、分開檢視 RPi 誤差／Target 誤差／可用性、禁止夾邊界與放寬門檻，以及參數校正／演算法改動另開實驗之單一變因原則。

---

## 三、測試與驗證狀態

> **本階段測試未執行，由 Codex 接續。**

- 測試環境／版本：本階段屬純編輯交付階段（依派工規則未使用命令、終端、shell、MCP 或瀏覽器工具），因此未執行 `pytest` 或 CLI 實跑；所有語法、輸入輸出欄位與手算數值均已人工逐行核對，不宣稱測試通過。
- 預計由 Codex 執行之命令：

```powershell
# 1. 執行本次新增 AG-005 測試
python -X utf8 -m pytest -v tests/test_anchor_comparison.py

# 2. 全專案 Python 回歸測試
python -X utf8 -m pytest -q

# 3. 檢查 CLI --help 可正常載入（確認 src/ 匯入路徑正常）
python -X utf8 scripts/compare-anchor-subsets.py --help
```

- 未執行項目及原因：
  - `pytest` 單元測試、全專案回歸與 CLI 實跑均未執行（編輯交付階段禁止使用終端／命令工具，由 Codex 接續執行與驗收）。
  - 六 Anchor 實體 BLE 測試未執行（`A05`／`A06` 尚未刷機、擺放與量測，且禁止登入 RPi／AWS 或碰觸實測原始檔）。

---

## 四、限制、合併注意事項與後續動作

- 剩餘限制／阻塞：
  1. 本階段測試未執行，須待 Codex 執行 `tests/test_anchor_comparison.py` 與全專案回歸確認無誤。
  2. 現有實測資料僅涵蓋 `A01–A04`，尚未有真實六 Anchor 觀測資料；所有測試皆為 `simulation` 合成幾何資料，不得冒充實機結果。
  3. 本工具目前未接收預先定義的評估時點格點，因此 `formal_success_rate` 固定輸出 `null`，避免以原始批數事後充當分母。
- 合併注意事項與還原方式：
  - 僅新增 4 個檔案，不影響核心定位引擎、韌體、設定檔、既有測試或 AG-002 交付，亦不涉及 RPi／AWS 部署。
  - 還原方式：刪除新增的 4 個檔案即可完整回到基準 `e353b3579a7f9b33af637eb365f8937bdb2b8d3c`。
- 報告／進度需更新處（交由 Codex 驗收後統一處理）：
  - `docs/progress/state.json`（並執行 `scripts/render-progress.py`）
  - `docs/test-log.md`（補記 Codex 執行 AG-005 測試與回歸結果）
- 下一個具體動作：
  - Codex 於工作分支執行 `tests/test_anchor_comparison.py` 與全專案回歸，審查四份交付檔案並決定後續整合；待 `A05`/`A06` 完成刷機、量測與六 Anchor 實體錄製後，再依 `docs/testing/six-anchor-experiment.md` 執行正式實機消融比較。

狀態：ready_for_review
