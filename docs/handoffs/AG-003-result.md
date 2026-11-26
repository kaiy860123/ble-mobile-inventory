# AG-003 任務交接結果

- 任務 ID／標題：AG-003 — 實驗彙整工具開發
- 交付者／審查者：Antigravity ／ Codex
- 狀態：`ready_for_review`
- 基準 commit：`291f0d13c43fd9d589e9925f447168f8cc5b00eb`（完整保留先前 AG-002／AG-001 交付）
- 工作分支／交付 commit：Codex 預先建立之 AG-003 工作分支（依派工規則本階段僅編輯工作區檔案，未執行任何 git 指令）

---

## 一、設計規格與輸入格式

### 1.1 定位與唯讀邊界

- `scripts/summarize-experiments.py` 讀取既有評估腳本 `scripts/evaluate-run.py` 的輸出 JSON（及選用之回放／狀態檔、獨立離線真值檔），結合明確填寫的實驗 metadata，產出可比較的 JSON／CSV／Markdown 實驗彙整表。
- 嚴格維持唯讀與資料分離邊界：
  - 未修改任何定位核心（`src/ble_inventory/`）、既有評估腳本（`scripts/evaluate-run.py`）或既有實驗／示範資料（`web/public/demo.json`、`tests/fixtures/truth.jsonl`）。
  - 真值僅供離線評估，絕不進入求解器；若輸入評估 JSON 標示 `truth_used_by_solver: true` 或狀態快照夾帶禁用真值欄位（`truth`、`ground_truth`、`true_position`、`scanner_truth`、`target_truth`、`scanner_position`、`target_positions`），工具立即拋出 `ValueError` 拒絕。
  - 本任務僅補足實驗彙整工具與模板缺口，**不代表已新增任何實體 BLE、Gazebo 或 AWS 實測結果**。

### 1.2 指標公式與缺值／零分母語意（對齊 `docs/report/methods.md` §9–§10 與 `tasks.md` AG-003）

| 欄位／指標 | 定義與公式 | 缺失輸入（省略／`None`） | 零分母或零樣本 |
| --- | --- | --- | --- |
| `valid_samples` | 依 `(run_id, device_id, position_at)` 去重且 `quality == "valid"` 之有效水平位置樣本數 | `未提供`（待測實驗） | `0` |
| `mae_m`／`rmse_m`／`p50_m`／`p95_m` | 條件於有效解之水平誤差統計（m）；P50／P95 採 `np.percentile(..., 50/95)` | `未提供`（若個別欄位缺值亦列 `未提供` 並加註限制） | `不適用`（`valid_samples = 0` 時不以 `0` 冒充零誤差） |
| `localization_success_rate` | `valid_samples / scheduled_eval_points`；若 `valid_samples > scheduled_eval_points` 判為異常，標 `不適用` 並加註警語 | `未提供`（不猜測預定評估時點數） | `不適用`（`scheduled_eval_points = 0`，避免除以零且不填 `0`） |
| `inventory_recall` | $\|S_R \cap G_R\| / \|G_R\|$；$S_R$ 與 $G_R$ 皆去重，且由狀態檔萃取之 $S_R$ 嚴格排除 Anchor | `未提供`（缺 $G_R$ 或缺 $S_R$） | `不適用`（$\|G_R\| = 0$，不填 `0` 或 `1`） |
| `end_to_end_latency_ms` | 僅接受明確標記實測之非負有限毫秒值；完全忽略 `publish_interval_s` | `未提供`（絕不將更新週期 1 s 填入為實測延遲） | `0.0`（僅在明確實測為 0 且非 `latency_measured=false` 時） |

### 1.3 支援之輸入格式

1. **JSON Manifest（`--manifest experiments.json`）**：接受 `{"experiments": [...]}` 或頂層清單 `[...]`，每筆 metadata 物件支援欄位：
   - 追溯與背景：`experiment_id`、`source`（限 `synthetic`／`gazebo`／`physical`／`simulation`／`aws_e2e`）、`site`、`route`、`version`、`run_id`、`missing_reason`、`limitations`。
   - 評估與選用佐證：`evaluation_path`（別名 `evaluation_file`，或內聯 `evaluation` 物件）、選用 `states_path`（別名 `states_file`，或內聯 `states`）、選用 `truth_path`（別名 `truth_file`，或內聯 `truth`，僅在省略 `evaluation_path` 時作獨立離線評估）。
   - 分母與盤點集合：`scheduled_eval_points`（非負整數或按設備對照之物件如 `{"RPi01": 90, "T01": 90, "T02": 65}`）、`expected_targets`（$G_R$ 陣列或 `;` 分隔字串，明確空集合為 `[]`／`EMPTY`）、`inventoried_targets`（$S_R$，省略時若提供 `states_path` 則自動排除 Anchor 萃取；若兩者皆提供則交叉檢核一致性）。
   - 延遲與設備名單：`end_to_end_latency_ms`（別名 `measured_latency_ms`）、`latency_measured`（若為 `false` 強制輸出 `未提供`）、選用 `devices`／`scanner_id`／`device_roles`。
2. **CSV Manifest（`--manifest docs/report/experiments-template.csv`）**：沿用 `docs/report/experiments-template.csv` 之 26 欄標題；空白／`未提供`／`待測` 解析為缺失，`[]`／`EMPTY`／`∅` 解析為空集合，`scheduled_eval_points` 支援整數、JSON 物件或 `RPi01=90;T01=90;T02=65` 格式。
3. **單次實驗 CLI 參數**：支援 `--evaluation`、`--states`、`--truth`、`--experiment-id`、`--source`、`--site`、`--route`、`--version`、`--run-id`、`--scheduled-eval-points`、`--expected-targets`、`--inventoried-targets`、`--latency-ms`、`--devices`、`--scanner-id`、`--missing-reason`、`--limitations`、`--csv-out`、`--md-out`、`--json-out`、`--format`。

### 1.4 輸出與跨來源／跨版本保護

- 輸出 26 欄 CSV（與 `docs/report/experiments-template.csv` 欄位完全對齊，並對 `=`, `+`, `@`, `\t`, `\r` 及非數值 `-` 開頭字串套用 CSV 公式防護）、GitHub Markdown 比較表與結構化 JSON（保留完整浮點數精度與 `comparison_flags`、`warnings`、`rows`）。
- 混合來源與多版本標示：
  - 單次評估檔含多種 `sources` 或與 metadata `source` 衝突時，標記 `source_status = mixed` 或 `conflict` 並輸出警語。
  - 多筆實驗跨來源（例如同時含 `synthetic`、`gazebo`、`physical`）或跨版本時，`comparison_flags.has_mixed_sources`／`has_multiple_versions` 標為 `true`，於頂層 `warnings` 與 Markdown 頂部警示區塊明確標明，且不跨來源或跨版本合併平均誤差。
- 不重複計分舊位置保護：
  - `evaluate_states_against_truth()` 依 `(run_id, device_id, position_at)` 去重，跳過 `stale`/`insufficient`/`unseen` 與 `position_at=None`（同時防禦 AG-002 F-14）。
  - 當同時提供外部 `evaluation_path` 與 `states_path` 時，額外核對 `evaluation.devices[id].samples` 是否超過狀態檔去重後有效位置數，超額時主動標示可能重複計分舊位置。

---

## 二、需求與驗收對應

- 對應任務：`docs/collaboration/tasks.md`（AG-003）、`docs/report/methods.md`（§9–§11）、`docs/report/report-draft.md`（§5–§6）。
- 允許修改範圍（嚴格遵守，允許前綴為空）：
  - `scripts/summarize-experiments.py`
  - `tests/test_experiment_summary.py`
  - `docs/report/experiments-template.csv`
  - `docs/handoffs/AG-003-result.md`
- 實際新增／修改檔案（僅此 4 檔；未動核心、既有評估腳本、實驗資料、進度檔或 AG-002／AG-001 交付）：
  1. `scripts/summarize-experiments.py` — 實驗彙整 CLI 與可匯入函式庫（JSON／CSV manifest 載入、單次模式、去重與真值分離檢查、CSV／Markdown／JSON 輸出）。
  2. `docs/report/experiments-template.csv` — 26 欄標準實驗彙整模板（含合成、實體步行、Gazebo、AWS 四條追蹤模板列，未測數據一律保留 `未提供`，無虛構數據）。
  3. `tests/test_experiment_summary.py` — 12 組（含 6 組非法輸入參數化，共 17 個案例）獨立單元測試，涵蓋手算驗算、去重不重複計分舊位置、零分母／零樣本、缺值與未量測延遲、集合交集召回率、混合來源與多版本標示、真值分離拒絕、唯讀對照 `web/public/demo.json`＋`tests/fixtures/truth.jsonl`、`experiments-template.csv` schema 驗證及 CLI＋CSV 公式防護。
  4. `docs/handoffs/AG-003-result.md` — 本交接報告。
- 介面或資料格式影響：無修改既有程式介面或 schema；新增離線彙整工具與報告 CSV 模板。

---

## 三、測試與驗證狀態

> **本階段測試未執行，由 Codex 接續。**

- 測試環境／版本：本階段屬純檔案編輯交付階段（依派工限制未使用終端／shell／命令工具），因此未於本階段執行 `pytest` 或 CLI 實跑；所有語法、欄位數與手算數字均經人工逐行核對，待 Codex 於目標 Python 環境執行驗證與回歸。
- 建議 Codex 接續執行命令：

```powershell
# 1. 執行本次新增 AG-003 測試
python -X utf8 -m pytest -v tests/test_experiment_summary.py

# 2. 全專案 Python 回歸測試
python -X utf8 -m pytest -q

# 3. 驗證模板 CSV 可直接載入彙整且不捏造數字
python -X utf8 scripts/summarize-experiments.py --manifest docs/report/experiments-template.csv --format markdown

# 4. 針對既有合成基準執行唯讀 CLI 驗證（不修改原始資料）
python -X utf8 scripts/summarize-experiments.py `
  --experiment-id TEST-005-SYN `
  --source synthetic `
  --site indoor-demo `
  --route "90s synthetic loop (T02 off after 65s)" `
  --version 9225d6be262071ab8ad31d6fb1f8b76526a5b04e `
  --states web/public/demo.json `
  --truth tests/fixtures/truth.jsonl `
  --scheduled-eval-points "RPi01=90;T01=90;T02=65" `
  --expected-targets "T01;T02"
```

- 預期／實際結果：
  - **實際結果**：本階段測試未執行，由 Codex 接續（不宣稱通過）。
  - **測試設計與手算預期值（供 Codex 核對）**：
    1. `test_hand_calculated_evaluation_json_and_metadata`：驗證 `RPi01` 成功率 `90/90 = 1.0`、`T01` `85/90`、`T02` `65/65 = 1.0`，召回率 `1.0`，延遲 `未提供`，`warnings == []`。
    2. `test_hand_calculated_states_and_separate_truth_no_duplicate_positions`：6 幀含重複 `position_at=1000.0`、`stale` 舊位置、`position_at=None` 與逾時幀；手算預期 `duplicate_positions_ignored=2`、`invalid_position_at_skipped=1`、`skipped_unmatched=1`；`RPi01` 誤差 `[1, 3, 5, 7]` → `MAE=4.0`、`RMSE=sqrt(21)`、`P50=4.0`、`P95=6.7`、成功率 `4/5=0.8`；`T01` 誤差 `[1, 3, 5]` → `MAE=3.0`、`RMSE=sqrt(35/3)`、`P50=3.0`、`P95=4.8`、成功率 `3/4=0.75`；`T02` `valid_samples=0`、誤差全為 `不適用`、成功率 `0.0`；$S_R=\{\text{T01},\text{T02}\}$（排除 Anchor `A01`）、$G_R=\{\text{T01},\text{T02},\text{T03}\}$ → 召回率 `2/3`；延遲維持 `未提供`（忽略 `publish_interval_s=1.0`）。
    3. `test_cross_check_detects_double_counted_evaluation_against_states`：評估檔宣稱 `samples=3` 但狀態檔去重僅 2 筆，觸發「重複計分舊位置」警語。
    4. `test_zero_denominators_zero_samples_and_overflow_denominator`：`scheduled_eval_points=0`、$|G_R|=0$、`samples=0` 與 `valid_samples > scheduled_eval_points` 皆正確標示 `不適用` 而不回傳 `0` 或除以零。
    5. `test_missing_metadata_missing_metrics_and_unmeasured_latency`：缺分母、缺集合、缺版本／run_id／來源、缺 P50／P95、`latency_measured=false` 皆列 `未提供`；有明確實測延遲 `245.5 ms` 時如實保留。
    6. `test_inventory_recall_uses_intersection_and_deduplicates`：$G_R=[\text{T01},\text{T02},\text{T02}]$、$S_R=[\text{T01},\text{T01},\text{T03}]$ → $|S_R \cap G_R|/|G_R| = 1/2 = 0.5$。
    7. `test_mixed_sources_conflict_and_different_versions_flagged`：單任務混合來源 `mixed`、metadata 與評估檔衝突 `conflict`、跨任務混合來源與多版本皆標於 `comparison_flags`、`warnings` 與 Markdown。
    8. `test_truth_separation_rejects_solver_truth_and_embedded_truth`：`truth_used_by_solver=True` 與狀態檔夾帶 `ground_truth` 皆拋出 `ValueError`；缺少 `truth_used_by_solver` 標為 `未提供` 並加警語。
    9. `test_invalid_numeric_or_source_inputs_rejected`（6 組參數化）：負分母、布林分母、未知來源、負延遲、`NaN` MAE、負 RMSE 皆拋出 `ValueError`。
    10. `test_repo_synthetic_fixture_matches_methods_section_11_readonly`：唯讀對照 `web/public/demo.json` 與 `tests/fixtures/truth.jsonl` 重現 `methods.md` §11 數值（容差 `1e-3`）且不填寫延遲。
    11. `test_experiments_template_csv_schema_and_no_fabricated_numbers`：確認 26 欄標題一致、4 模板列無缺欄、彙整後數值全為 `未提供`。
    12. `test_cli_manifest_outputs_and_csv_formula_protection`：確認 CLI 輸出 JSON／CSV／Markdown，且 `=SUM(A1:A2)` 於 CSV 中轉為 `'=SUM(A1:A2)`。
- 證據：
  - `scripts/summarize-experiments.py`
  - `tests/test_experiment_summary.py`
  - `docs/report/experiments-template.csv`
  - `docs/handoffs/AG-003-result.md`
- 未執行項目及原因：
  - 所有自動化測試與 CLI 實跑均未執行（本階段僅限使用內建檔案讀寫工具，禁止命令／終端／shell 執行；由 Codex 接續跑測試與回歸）。
  - 未進行實體 BLE、Gazebo 或 AWS 實測（超出 AG-003 範圍且對應硬體／模擬／雲端仍阻塞）。

---

## 四、限制、欄位對照備註與合併注意事項

### 4.1 剩餘限制與欄位語意協調事項

1. **「未提供」與「不適用」之明確區分**：依 `docs/collaboration/tasks.md`（無分母／應盤點集合輸出 `未提供`）與 `docs/report/methods.md` §10（無樣本或分母為零標 `不適用`，不能填 0 冒充量測），本實作將兩者分開：`None`／省略輸出 `未提供`，明確給定但分母或樣本數為 `0` 輸出 `不適用`。若報告版面希望統一顯示詞彙，可由 Codex 審查調整常數或於 `methods.md` §10 補註區別。
2. **既有 `scripts/evaluate-run.py` 輸出欄位限制**：`evaluate-run.py` 目前未輸出 `run_id`、$S_R$ 或分母，也未防禦 `position_at=None`（見 AG-002 F-14）。依 AG-003 唯讀邊界未改動 `evaluate-run.py`，而是於 `summarize-experiments.py` 透過 metadata 與選用 `states_path` 補足追溯與去重核對。
3. **本階段未執行實測與自動化測試**：所有行為仍待 Codex 執行 `pytest` 確認後，始可更新為 `verified`。

### 4.2 合併注意事項與還原方式

- 本任務僅新增 4 個檔案，不與核心程式、前端、既有測試或 AG-001／AG-002 交付衝突。
- 不涉及 RPi、AWS 或 GitHub Pages 部署。
- 還原方式：移除新增的 `scripts/summarize-experiments.py`、`tests/test_experiment_summary.py`、`docs/report/experiments-template.csv` 與 `docs/handoffs/AG-003-result.md` 即可回到基準 `291f0d13c43fd9d589e9925f447168f8cc5b00eb`。

### 4.3 報告／進度需更新處（交由 Codex 審查驗證後更新）

- `docs/progress/state.json`：更新 `AG-003` 狀態與測試證據，並執行 `scripts/render-progress.py`。
- `docs/test-log.md`：補記 Codex 執行 `tests/test_experiment_summary.py` 與全套回歸之 TEST 條目。
- `docs/report/report-draft.md`：後續取得實測／Gazebo／AWS 資料後，以 `scripts/summarize-experiments.py` 產表並引用 `docs/report/experiments-template.csv`。

### 4.4 下一個具體動作

1. Codex 於工作分支執行 `python -X utf8 -m pytest -v tests/test_experiment_summary.py` 與完整回歸測試 `python -X utf8 -m pytest -q`。
2. Codex 審查 `scripts/summarize-experiments.py`、`docs/report/experiments-template.csv` 與 `tests/test_experiment_summary.py`；若有任何失敗或欄位語意調整需求，依結果修正或併入主線並更新進度與測試紀錄。

---

狀態標記：`ready_for_review`
