# Gazebo 整合實作手冊（SIM-001 交接指南）

- **對應任務**：`SIM-001`（Gazebo 觀測串接）／本交接文件為 `AG-004`
- **日期**：2026-11-27
- **基準版本**：`f2c1d0c2d9bd6328e30e87cd7aaa514a1a9091bb`
- **公開儲存庫**：`https://github.com/kaiy860123/ble-mobile-inventory`
- **公開唯讀頁面**：`https://kaiy860123.github.io/ble-mobile-inventory/`
- **簡報資料檔**：`docs/handoffs/AG-004-slides.json`（22 頁，待 Codex 產生簡報成品並逐頁 QA）

> **現況與證據聲明**：截至 2026-11-27，定位核心、離線評估與實驗彙整工具已通過軟體與合成測試（非 browser Python 149 通過、前端 3 通過）；AWS Sydney（`ap-southeast-2`）已部署並通過 PC 合成資料 TLS→WSS 唯讀通路驗證（`TEST-027`）；六塊 XIAO（`A01`–`A04`、`T01`–`T02`）已各別刷機與各別 Windows BLE 解碼（`TEST-021`–`026`）。**RPi 新版部署、六塊同時通電收包／校正／精度與 RPi 即時上雲仍待辦；Gazebo 目前尚未交付與串接**。本專案內的 `SyntheticSource` 僅為數學測試源，`scripts/send-observations.py` 僅為 JSONL 檔案送出器，均不可視為 Gazebo 已驗證。

---

## 1. 分工邊界與核心紅線

| 面向 | 我方負責（共用核心與平台） | Gazebo 組員負責（`SIM-001`） |
| --- | --- | --- |
| 定位與儲存 | `src/ble_inventory/` 兩階段定位、本地 HTTP/WS 服務、`RunStore` 原始紀錄 | Gazebo 世界／場景、SITL 飛控與巡查航線 |
| 資料契約 | `src/contracts/observation.schema.json` v1.0、`contracts.py` 嚴格檢核 | 實作 3D BLE RSSI 衰減／噪聲／漏收模型，輸出合法 v1.0 批次 |
| 真值隔離 | 拒絕含真值之觀測；提供獨立離線評估 `evaluate-run.py` 與彙整 `summarize-experiments.py` | 另存與輸入時鐘對齊之 `truth.jsonl`，**絕不將掃描器 XY 或 Target 真值送入定位 API** |
| 雲端與展示 | AWS Sydney 部署（0 元 Free Plan）與公開唯讀 GitHub Pages | 提供可重現交付包與模擬章節參數說明 |

**五條不可妥協的紅線**：
1. **真值不得進入求解器**：`/api/observations` 採 `additionalProperties: false`，任何 `scanner_position`、`targets`、`truth`、`ground_truth` 皆會回傳 HTTP `400`。
2. **飛控導航與 BLE 估計分開**：無人機飛控可使用 Gazebo 位姿或自身導航控制飛行，但該 XY 座標僅供產生 RSSI 與寫入獨立 `truth.jsonl`，不得送給 BLE 定位核心。
3. **資料來源嚴格分開**：Gazebo 實驗一律標示 `source: "gazebo"`（於 `summarize-experiments.py` metadata）與 `source: "simulation"`（於觀測批次 JSON），不得與 `synthetic` 或 `physical` 合併平均。
4. **安全與隱私邊界**：`BLE_INGEST_TOKEN` 自選長隨機字串，只放環境變數與 `Authorization: Bearer` Header；切勿放進 URL、Git 檔案或公開聊天。本手冊與交付包不得包含個人 email、私人 IP、帳號密碼、金鑰、實際 token 或個人本機路徑。
5. **缺測不代填**：尚未取得的資訊一律標註「未提供」或「待提供」；零分母／零樣本標為「不適用」，不以 `0` 或 `1 s` 更新週期冒充實測值。

---

## 2. 觀測契約 v1.0 規格與可貼用範例

規格依據：`src/contracts/observation.schema.json`、`src/ble_inventory/contracts.py`、`docs/contracts.md`。

### 2.1 欄位檢查表

| 欄位 | 必／選 | 型別與限制 | 語意與注意事項 |
| --- | --- | --- | --- |
| `schema_version` | 必填 | 常數 `"1.0"` | 固定字串 `"1.0"` |
| `timestamp` | 必填 | 有限數值 `> 0` | Unix UTC 秒（可含小數）；即時 API 要求距伺服器 UTC **±30 秒內**，且不得小於前一批 `timestamp` |
| `source` | 必填 | `"physical"` \| `"simulation"` | Gazebo 接入 `--mode external` 時必為 `"simulation"` |
| `scanner_id` | 必填 | `^[A-Za-z0-9_-]{1,64}$` | 須與啟動服務所用場地設定檔的 `scanner_id` 完全一致（範例為 `"RPi01"`） |
| `sequence` | 必填 | 非負整數 `>= 0` | 同一 `run_id` 內**嚴格遞增**；重開模擬且歸零前須先開始新巡查 |
| `scanner_height_m` | 選填 | 有限數值（m） | 同 Local `z=0` 基準的已知天線高度；省略則改用場地設定檔預設值（為相容嚴格 JSON Schema，未提供時請省略該鍵而非傳 `null`） |
| `observations` | 必填 | 陣列 `0–256` 筆 | 同批每個 `device_id` 唯一；未收到的設備省略；**空批次 `[]` 合法** |
| `observations[].device_id` | 必填 | `^[AT][0-9]{2,3}$` | 預設名單 `A01`–`A04`（Anchor）、`T01`–`T02`（Target）；角色由場地設定決定，未登錄 ID 會被略過 |
| `observations[].rssi_dbm` | 必填 | 有限數值 `[-127, 20]` | 接收訊號強度（dBm） |
| `observations[].rssi_at_1m_dbm` | 選填 | 有限數值 `[-127, 20]` | 1 公尺接收訊號校正值（非 RF TX power）；優先序：單一設備場地設定 > 封包值 > 全域場地設定（未提供請省略） |

### 2.2 可直接貼用的合法 Observation JSON（單筆）

```json
{
  "schema_version": "1.0",
  "timestamp": 1795651200.0,
  "source": "simulation",
  "scanner_id": "RPi01",
  "sequence": 0,
  "scanner_height_m": 1.2,
  "observations": [
    {"device_id": "A01", "rssi_dbm": -78.233, "rssi_at_1m_dbm": -59.0},
    {"device_id": "A02", "rssi_dbm": -72.857, "rssi_at_1m_dbm": -59.0},
    {"device_id": "A03", "rssi_dbm": -72.534, "rssi_at_1m_dbm": -59.0},
    {"device_id": "A04", "rssi_dbm": -79.194, "rssi_at_1m_dbm": -59.0},
    {"device_id": "T01", "rssi_dbm": -75.785, "rssi_at_1m_dbm": -59.0},
    {"device_id": "T02", "rssi_dbm": -65.255, "rssi_at_1m_dbm": -59.0}
  ]
}
```

### 2.3 可直接貼用的 JSONL 兩筆範例（`observations.jsonl`）

> 每行必須為單行完整 JSON，不可跨行縮排。

```jsonl
{"schema_version": "1.0", "timestamp": 1795651200.0, "source": "simulation", "scanner_id": "RPi01", "sequence": 0, "scanner_height_m": 1.2, "observations": [{"device_id": "A01", "rssi_dbm": -78.233, "rssi_at_1m_dbm": -59.0}, {"device_id": "A02", "rssi_dbm": -72.857, "rssi_at_1m_dbm": -59.0}, {"device_id": "A03", "rssi_dbm": -72.534, "rssi_at_1m_dbm": -59.0}, {"device_id": "A04", "rssi_dbm": -79.194, "rssi_at_1m_dbm": -59.0}, {"device_id": "T01", "rssi_dbm": -75.785, "rssi_at_1m_dbm": -59.0}, {"device_id": "T02", "rssi_dbm": -65.255, "rssi_at_1m_dbm": -59.0}]}
{"schema_version": "1.0", "timestamp": 1795651201.0, "source": "simulation", "scanner_id": "RPi01", "sequence": 1, "scanner_height_m": 1.2, "observations": [{"device_id": "A01", "rssi_dbm": -80.288, "rssi_at_1m_dbm": -59.0}, {"device_id": "A02", "rssi_dbm": -73.886, "rssi_at_1m_dbm": -59.0}, {"device_id": "A03", "rssi_dbm": -71.967, "rssi_at_1m_dbm": -59.0}, {"device_id": "A04", "rssi_dbm": -80.161, "rssi_at_1m_dbm": -59.0}, {"device_id": "T01", "rssi_dbm": -76.206, "rssi_at_1m_dbm": -59.0}, {"device_id": "T02", "rssi_dbm": -61.127, "rssi_at_1m_dbm": -59.0}]}
```

---

## 3. 座標框架、時鐘映射與物理模型對照

### 3.1 Local 座標系與高度基準（`docs/report/methods.md` §4、§8）

- **單位與邊界**：Local 座標單位為公尺（m），`config/site.example.json` 範例為 `bounds_m: [0, 0, 12, 9]`。
- **軸向與旋轉**：
  - `rotation_deg = 0` 時：`+X` 指向正東、`+Y` 指向正北、`+Z` 向上。
  - 旋轉角 $\theta$（`rotation_deg`）為 Local `+X` 相對正東之**逆時針**角度（$\theta = 90^\circ$ 時 `+X` 向北、`+Y` 向西）：
    $$E = x\cos\theta - y\sin\theta,\quad N = x\sin\theta + y\cos\theta,\quad U = z$$
  - 若 Gazebo 場景未對準真實經緯度，請在場地設定檔維持 `"georeference": null`。
- **高度基準**：`scanner_height_m`、Anchor `position[2]`、Target `height_m` 必須共用同一個 Local `z = 0` 基準面。已知飛行高度可透過 `scanner_height_m` 輸入，但掃描器 XY 與 Target 真值 XYZ 嚴格另存。

### 3.2 模擬時鐘映射與暫停處理

1. **即時 API 窗口限制**：`src/ble_inventory/server.py` 強制檢查 `abs(batch["timestamp"] - time.time()) <= 30`（UTC 秒），且 `engine.py` 要求 `sequence > last_sequence` 與 `timestamp >= last_batch_at`。
2. **建議映射方式**：
   - 在巡查開始當下設定牆鐘基準 $t_0$，將模擬時間映射為 $t_{\text{utc}} = t_0 + (t_{\text{sim}} - t_{\text{sim},0})$；若模擬速度 `RTF != 1`（例如慢於即時導致 $t_0 + \Delta t_{\text{sim}}$ 逐漸落後牆鐘超過 30 秒），可改為於送出當下打上單調遞增的 `time.time()` 作為輸入時鐘，並於 `clock_mapping.json` 記錄每筆 `(sequence, sim_time_s, utc_timestamp)` 對照。
   - **關鍵原則**：**`truth.jsonl` 的 `timestamp` 必須與實際送入 `/api/observations` 的 `timestamp` 使用完全相同的時鐘（input clock）**，否則離線評估的 0.25 s 時間對齊會失敗。
3. **暫停與重開模擬**：
   - Gazebo 暫停時應停止發送，切勿重複送出相同 `sequence` 或過期 `timestamp`。
   - 暫停逾 10 s 時快照會標記 stale；恢復收到新觀測時重置 RSSI 濾波器，避免混入舊訊號，狀態依新資料更新。
   - 若重開 Gazebo 導致 `sequence` 歸零，**務必先呼叫 `POST /api/control`（`{"action":"start"}`）或在本地網頁按「開始新巡查」**建立新 `run_id`，再送出 `sequence: 0`。

### 3.3 RSSI 模型與共用兩階段定位摘要（`docs/report/methods.md` §2–§7）

- **對數距離衰減模型**：
  $$r(d) = P_{1\text{m}} - 10 n \log_{10}(d / d_0) + \varepsilon \qquad (d_0 = 1\text{ m})$$
  - **具體數學試算例（非實測值）**：取 $P_{1\text{m}} = -59\text{ dBm}$、$n = 2$、$d = 2\text{ m}$、$\varepsilon = 0$，得
    $$r(2) = -59 - 10 \times 2 \times \log_{10}(2) \approx -59 - 6.0206 \approx -65.02\text{ dBm}$$
  - **求解器反解斜距**：$\widehat{d} = d_0 \cdot 10^{(P_{1\text{m}} - s_k)/(10n)}$（例：$P_{1\text{m}}=-59, s_k=-79, n=2 \Rightarrow \widehat{d}=10\text{ m}$）。
  - **斜距轉水平距離**：$\rho = \sqrt{\widehat{d}^2 - (\Delta h)^2}$，要求 $\widehat{d} > |\Delta h|$。
- **RSSI 濾波**：先因果滑動中位數（範例 `median_window = 3`），再指數移動平均（範例 `filter_alpha = 0.65`）；接收間隔超過 `stale_after_s = 10.0 s` 重置濾波器。
- **第一階段（Anchor → 掃描器）**：取 `anchor_ttl_s = 3.0 s` 內有效 Anchor（$\ge 3$ 個、SVD 最小奇異值 $\ge 10^{-5}$ 且條件數 $\le 100$），以 `np.linalg.lstsq` 求初值後進行 Huber 加權迭代（$c=1.5\text{ m}$、最多 30 次、單步上限 5 m），最後以未加權 RMS 距離殘差 $R_{\text{range}} \le 2.5\text{ m}$ 作閘門。
- **第二階段（移動掃描器 → 靜止 Target）**：僅於第一階段有效且掃描器移動距離 $\ge 0.15\text{ m}$ 時加入滑動窗口（`target_window_s = 120 s`、上限 240 筆）；達 `target_min_samples = 6` 筆、包圍盒對角基線 $B \ge 1.5\text{ m}$、SVD 非共線且殘差 $\le 2.5\text{ m}$ 時更新位置。**航線必須有轉折，單一直線會觸發共線拒絕。**

---

## 4. 一步一步操作：啟動服務、接入與控制

> 以下所有 CLI 參數均逐項核對自 `src/ble_inventory/cli.py`、`scripts/send-observations.py`、`scripts/evaluate-run.py` 與 `scripts/summarize-experiments.py`。

### 4.1 安裝與啟動 `external` 模式服務

1. 從 `config/site.example.json` 複製建立 Gazebo 專用場地設定（**必須位於 `<root>/config/` 目錄下**，例如 `config/site.gazebo.json`），將 `bounds_m`、`scanner_id`、`scanner_height_m` 與各 Anchor 座標對齊 Gazebo 世界。
2. 設定環境變數 `BLE_INGEST_TOKEN` 並啟動服務：

**Linux / macOS（bash）**：
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
npm ci
npm run build

export BLE_INGEST_TOKEN="<YOUR_LONG_RANDOM_TOKEN>"
ble-inventory serve --mode external --host 127.0.0.1 --port 8080 \
  --config config/site.gazebo.json --root .
```

**Windows（PowerShell）**：
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
npm ci
npm run build

$env:BLE_INGEST_TOKEN = "<YOUR_LONG_RANDOM_TOKEN>"
ble-inventory serve --mode external --host 127.0.0.1 --port 8080 `
  --config config/site.gazebo.json --root .
```

> 若無法直接呼叫 `ble-inventory`，可改用 `python -m ble_inventory.cli serve ...`。跨主機測試時將 `--host` 設為 `0.0.0.0`（僅限可信任實驗區域網路）。

### 4.2 驗證端到端連線（內建送出器 vs `curl`）

**方式 A：使用內建檔案送出器（僅驗證連線，非 Gazebo 模型）**
```bash
python scripts/send-observations.py tests/fixtures/observations.jsonl \
  --url http://127.0.0.1:8080
```
- 預期輸出：每 1 秒印出一行 `sequence=0 status=200`、`sequence=1 status=200` ...
- **注意**：`send-observations.py` 會將每行的 `timestamp` 覆寫為發送當下的 `time.time()` 並重編 `sequence`。若用於正式誤差評估，請改由 Gazebo 橋接腳本直接 POST 並同步寫出對齊時間戳的 `truth.jsonl`。

> A、B 擇一。若已執行 A，改用 B 的 sequence=0 前，先依 4.3 開始新巡查。送出器只印 HTTP 狀態，請另外確認 accepted 欄位與 raw 紀錄。

**方式 B：使用 `curl` 送出單批即時觀測（bash）**
```bash
NOW_UTC=$(python -c "import time; print(round(time.time(), 3))")
curl -i -X POST http://127.0.0.1:8080/api/observations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${BLE_INGEST_TOKEN}" \
  -d "{
    \"schema_version\": \"1.0\",
    \"timestamp\": ${NOW_UTC},
    \"source\": \"simulation\",
    \"scanner_id\": \"RPi01\",
    \"sequence\": 0,
    \"scanner_height_m\": 1.2,
    \"observations\": [
      {\"device_id\": \"A01\", \"rssi_dbm\": -78.2, \"rssi_at_1m_dbm\": -59.0},
      {\"device_id\": \"A02\", \"rssi_dbm\": -72.9, \"rssi_at_1m_dbm\": -59.0},
      {\"device_id\": \"A03\", \"rssi_dbm\": -72.5, \"rssi_at_1m_dbm\": -59.0},
      {\"device_id\": \"A04\", \"rssi_dbm\": -79.2, \"rssi_at_1m_dbm\": -59.0},
      {\"device_id\": \"T01\", \"rssi_dbm\": -75.8, \"rssi_at_1m_dbm\": -59.0}
    ]
  }"
```
- 預期回應：`HTTP/1.1 200 OK` 與 `{"accepted": true}`。

### 4.3 任務控制（開始新巡查／停止／匯出）

> 控制 API 需先向 `/api/bootstrap` 取得本地 `control_token`，且不可附帶跨站 `Origin` Header。

```bash
# 取得目前控制 token
CONTROL_TOKEN=$(curl -s http://127.0.0.1:8080/api/bootstrap | python -c "import sys,json; print(json.load(sys.stdin)['control_token'])")

# 結束目前巡查（之後合法觀測會回傳 200 {"accepted": false}）
curl -s -X POST http://127.0.0.1:8080/api/control \
  -H "Content-Type: application/json" \
  -H "X-Control-Token: ${CONTROL_TOKEN}" \
  -d '{"action":"stop"}'

# 開始新巡查（產生新 run_id，重設 sequence=-1，允許重新從 sequence=0 送出）
curl -s -X POST http://127.0.0.1:8080/api/control \
  -H "Content-Type: application/json" \
  -H "X-Control-Token: ${CONTROL_TOKEN}" \
  -d '{"action":"start"}'

# 檢視目前完整狀態、匯出回放 JSON 與 CSV
curl -s http://127.0.0.1:8080/api/state
curl -s http://127.0.0.1:8080/api/export -o artifacts/replay.json
curl -s "http://127.0.0.1:8080/api/export?format=csv" -o artifacts/replay.csv
```

每次巡查自動存檔位置（append-only）：
- 原始觀測：`data/raw/<run_id>/observations.jsonl`
- 任務清單：`data/raw/<run_id>/manifest.json`（含 `"truth_used_by_solver": false`）
- 狀態快照：`data/processed/<run_id>/states.jsonl`

---

## 5. 獨立真值檔與離線評估／實驗彙整

### 5.1 可直接貼用的 `truth.jsonl` 範例

每行對應一個與觀測輸入時鐘對齊的時間戳（單位：Local 公尺）：

```jsonl
{"timestamp": 1795651200.0, "scanner": [10.2, 4.5, 1.2], "targets": {"T01": [3.0, 3.15, 1.2], "T02": [9.0, 5.85, 1.2]}}
{"timestamp": 1795651201.0, "scanner": [10.132143509710112, 5.031717833074698, 1.2], "targets": {"T01": [3.0, 3.15, 1.2], "T02": [9.0, 5.85, 1.2]}}
```

### 5.2 執行離線定位誤差評估（`scripts/evaluate-run.py`）

```bash
python scripts/evaluate-run.py \
  "data/processed/<RUN_ID>/states.jsonl" \
  "runs/<EXP_ID>/truth.jsonl" \
  --max-time-delta-s 0.25 \
  --output artifacts/gazebo_eval.json
```

**評估規則與解讀重點**：
- 依 `(run_id, device_id, position_at)` 去重，避免每秒重複寫出的舊位置重複計分。
- 僅計算 `quality == "valid"` 且與 `truth.jsonl` 時間差 $\le 0.25\text{ s}$ 之非 Anchor 設備水平誤差 $e_k = \sqrt{(\widehat{x}_k - x_k^*)^2 + (\widehat{y}_k - y_k^*)^2}$。
- **區分真實誤差與殘差**：`evaluate-run.py` 產出的是對獨立真值的水平誤差（MAE／RMSE／P50／P95）；狀態檔中的 `residual_m` 僅為求解器內部測距殘差 $R_{\text{range}}$，小殘差不代表小真實誤差。

### 5.3 產出標準實驗彙整表（`scripts/summarize-experiments.py`）

```bash
python scripts/summarize-experiments.py \
  --experiment-id EXP-GAZ-001 \
  --source gazebo \
  --site gazebo-warehouse-v1 \
  --route "loop-turn-2targets" \
  --version "<GAZEBO_GIT_SHA>" \
  --run-id "<RUN_ID>" \
  --evaluation artifacts/gazebo_eval.json \
  --states "data/processed/<RUN_ID>/states.jsonl" \
  --scheduled-eval-points "RPi01=120;T01=120;T02=80" \
  --expected-targets "T01;T02" \
  --scanner-id RPi01 \
  --limitations "Gazebo 模擬結果（標明場景／噪聲參數），非實體 BLE 量測" \
  --csv-out artifacts/gazebo_summary.csv \
  --md-out artifacts/gazebo_summary.md \
  --json-out artifacts/gazebo_summary.json \
  --format markdown
```

- 多組實驗可改用 `--manifest <experiments.json 或 .csv>`（欄位範本見 `docs/report/experiments-template.csv`）。
- 若未實測端到端延遲，請**省略 `--latency-ms`**（輸出「未提供」），絕不填寫 `1000` ms 冒充實測。

---

## 6. 驗收測試清單（正常流程＋異常矩陣）

### 6.1 正常整合驗收預期

1. `GET /api/state` 顯示 `"input_mode": "external"`、`"source": "simulation"`、`"active": true`。
2. 完整巡查航線（含轉折、4 Anchor、2 靜止 Target）所有合法批次皆回傳 `HTTP 200` 且 `{"accepted": true}`。
3. 盤點計數 `counts.inventoried == 2`，`scanner.quality == "valid"`；Target 累積達 6 筆、基線 $\ge 1.5\text{ m}$、幾何非共線且殘差通過後轉為 `"valid"`。
4. 執行 `POST /api/control {"action":"stop"}` 後，`data/raw/<run_id>/observations.jsonl` 筆數與已接受批次數一致，`manifest.json` 含 `"truth_used_by_solver": false`。
5. `evaluate-run.py` 輸出有效誤差統計且 `skipped_unmatched` 符合預期（正常對齊下應接近 0）；`summarize-experiments.py` 標示 `source = gazebo` 且無來源衝突警語。

### 6.2 異常與故障測試矩陣

| 編號 | 測試情境 | 操作方式 | 預期 HTTP／系統結果 |
| --- | --- | --- | --- |
| F-01 | 夾帶真值或未知欄位 | 批次中加入 `"scanner_position": [1, 2]` 或 `"truth": {}` | `HTTP 400`，不寫入 `observations.jsonl` |
| F-02 | 時間戳超出 30 秒或倒退 | 送出距 UTC 超過 30 秒或小於前批之 `timestamp` | `HTTP 400`（`within 30s` 或 `out-of-order`） |
| F-03 | 序號重複或重啟未開新巡查 | 重送相同 `sequence`，或重開模擬直接送 `sequence: 0` | `HTTP 400`；先呼叫 `control start` 後 `sequence: 0` 恢復 `200 {"accepted": true}` |
| F-04 | 同批重複設備 ID | 同批 `observations` 含兩筆 `"device_id": "A01"` | `HTTP 400`（`Duplicate device in observation batch`） |
| F-05 | 權限錯誤／模式錯誤／停止後推送 | 錯或漏 Token ／ 以 `--mode demo` 啟動 ／ `stop` 後送合法批次 | 依序回傳 `HTTP 401` ／ `HTTP 409` ／ `HTTP 200 {"accepted": false}` |
| F-06 | Anchor 不足（`< 3`）或共線 | 遮蔽 2 個 Anchor，等舊觀測逾 3 s（僅剩 2 個）；另以共線擺放獨立測試 | `200 {"accepted": true}`；`scanner.quality == "insufficient"` 且不偽造座標；當批收到之 Target 仍計入 `counts.inventoried` |
| F-07 | Target 中途關閉（驗收 A02） | 停止 `T02` 廣播超過 10 秒 | `counts.inventoried` 維持 `2`、`counts.visible` 降至 `1`；`T02` 標 `stale` 且保留最後有效位置與 `position_at` |

---

## 7. 組員交付包規格與里程碑

### 7.1 交付包建議結構

```text
gazebo_delivery_<YYYYMMDD>/
├── README.md                      # 必填：版本、場景、航線、時鐘映射、噪聲/漏收、重現命令
├── world/                         # Gazebo 世界／模型檔與 Anchor／Target 擺放座標表
├── config/
│   └── site.gazebo.json           # 對應該場景之場地設定（anchor XYZ、bounds_m、scanner_id）
└── runs/
    └── <EXP_ID>/
        ├── observations.jsonl     # 嚴格 v1.0 合法觀測（不含任何真值）
        ├── truth.jsonl            # 對齊輸入時鐘之獨立真值
        ├── clock_mapping.json     # (sequence, sim_time_s, utc_timestamp) 映射紀錄
        ├── states.jsonl           # (選附) 對應 run_id 的狀態快照
        └── evaluation.json        # (選附) evaluate-run.py 輸出結果
```

### 7.2 `README.md` 必填檢查項（尚未定案者寫「待提供」）

1. **程式與模擬器版本**：Gazebo 版本、ROS／SITL 版本、組員程式 Git commit SHA 與主要相依。
2. **場景與座標定義**：場地尺寸、Local 原點與旋轉角（零旋轉為 X 東 Y 北）、高度基準 `z=0`、各 Anchor 與 Target 的座標及高度。
3. **航線設計**：起飛、巡查轉折軌跡、返航點、巡航高度與飛行速度；是否包含 Target 中途關閉或 Anchor 遮蔽情境。
4. **RSSI 與頻道模型參數**：$P_{1\text{m}}$、路徑損耗指數 $n$、噪聲分佈與標準差 $\sigma_\varepsilon$、漏收率模型、廣播週期、是否含 3D 衰減或牆面遮蔽。
5. **時鐘映射與暫停處理**：$t_{\text{sim}} \leftrightarrow t_{\text{utc}}$ 映射公式、RTF 設定、模擬暫停與重啟行為。
6. **實驗設計 metadata**：`scheduled_eval_points`（可按設備列出）、應盤點集合 $G_R$（如 `T01;T02`）、已知限制與正常／異常測試結果摘要。

### 7.3 整合里程碑

| 目標日期 | 里程碑 | 整合交付物 |
| --- | --- | --- |
| **2026-12-10** | 主要功能完成 | 交付首版場景、轉折航線、合法 `observations.jsonl` 與對齊 `truth.jsonl`，完成首輪 `external` 模式串接與 `evaluate-run.py` 評估 |
| **2026-12-17** | 全系統整合完成 | 補齊正常與異常測試矩陣紀錄、多組航線／噪聲實驗與完整 README；以 `summarize-experiments.py` 產出分來源實驗比較表 |
| **2026-12-24** | 最終展示與繳交 | 凍結模擬版本 SHA 與回放檔，核對專題報告模擬章節與最終簡報 |

## Codex 驗收補充

- 建立 config/site.gazebo.json 後再啟動；請由範例複製並改成實際場景。
- Bash：`cp config/site.example.json config/site.gazebo.json`；PowerShell：`Copy-Item config/site.example.json config/site.gazebo.json`。
- 範例中的 `<RUN_ID>`、`<EXP_ID>` 與 token 必須替換，不是已完成 Gazebo 實驗。預定評估數為示意，須按實驗設計填寫。
- 正式驗收必要欄位缺少時仍列待補，不因標「待提供」就算通過。
