# 共用介面 v1.0

此文件交給 Gazebo 組員；模擬場景、飛控與 RSSI 觀測模型由組員實作。專題內的 `SyntheticSource` 僅是數學測試來源，不能當成 Gazebo 已驗證。

## 觀測輸入

JSON Schema：`src/contracts/observation.schema.json`。每批只含 RSSI、ID、時間及可選的掃描器已知高度，不接受掃描器 XY 位置、Target 座標或真值。

```json
{
  "schema_version":"1.0",
  "timestamp":1795651200.0,
  "source":"simulation",
  "scanner_id":"RPi01",
  "sequence":0,
  "scanner_height_m":1.2,
  "observations":[
    {"device_id":"A01","rssi_dbm":-70.5,"rssi_at_1m_dbm":-59},
    {"device_id":"T01","rssi_dbm":-65.2,"rssi_at_1m_dbm":-59}
  ]
}
```

- `timestamp`：Unix UTC 秒，可含小數；即時 API 要求距伺服器 UTC 30 秒內。模擬時間需映射至牆鐘時間，保留原始模擬時間於評估檔。
- `sequence`：同任務內遞增，不得重複或倒序；重開模擬且序號歸零時，先開始新巡查。
- 同一批每個設備只一筆，沒有收到的設備省略；空批次合法。
- RSSI 單位 dBm。`rssi_at_1m_dbm` 是一公尺接收訊號校正值，不是射頻發射功率。
- 設備的場地設定若有專屬校正值，優先使用該值，其次封包參考值，最後使用全域參考值。
- Anchor／Target 角色由場地名單決定；初始 A01–A04／T01–T02。新增設備需同步韌體 ID 與名單。
- `scanner_height_m` 是同 Local 框架的已知天線高度，可由固定配置或獨立高度來源提供，不得夾帶真值 XY。

## 即時接入

1. 設定環境變數 `BLE_INGEST_TOKEN`（自選長隨機值，勿放網址、公開檔案或聊天）。
2. 啟動 `ble-inventory serve --mode external --host 0.0.0.0 --config config/site.local.json`。
3. 向 `/api/observations` POST JSON，Header 為 `Authorization: Bearer <token>`。
4. 每批回應 `{"accepted":true}`。停止任務時為 false；無效、重複、倒序或過時資料回傳 400。

`scripts/send-observations.py tests/fixtures/observations.jsonl` 可驗證連線；它是檔案送出器，不是 Gazebo 模型。跨主機需先完成 RPi 網路及防火牆設定；本地 HTTP 介面只供可信任實驗區域網路，公共網路觀看使用 AWS 的加密通道。

## 真值與評估

真值另存檔，例如 `tests/fixtures/truth.jsonl`，由時間對齊後計算估計誤差。真值不能送進上述 API；`additionalProperties:false` 與程式驗證會拒絕未知欄位。

## BLE 廣播封包

原型 Manufacturer ID `0xFFFF`（實驗用途，非已分配廠商 ID）。其後 9 bytes，little-endian：

| 欄位 | 大小 | 值 |
| --- | --- | --- |
| magic | 2 | ASCII BI |
| version | 1 | 1 |
| role | 1 | 1=Anchor，2=Target |
| ordinal | 2 | 1–999，產生 A01／T01 等 ID |
| rssi_at_1m | 1 signed | 初值 -59，需實測校正 |
| sequence | 2 | 首版 0，接收器不以此去重 |

韌體共用程式，PlatformIO environment 決定角色和 ordinal。預設 500 ms 廣播、+3 dBm 發射功率，無連線、無 Scan Response；發射功率與校正 RSSI 各自管理。

## 狀態輸出與回放

- `/api/state`／`/api/ws`：完整目前狀態，含來源、任務、計數、設備、品質、最後有效位置與場地框架。
- AWS：每秒最新狀態，省略重複的完整航跡；瀏覽器累積目前連線期間的航跡，不提供登入前的雲端歷史。
- `/api/export`：`kind=ble-inventory-replay` 的 JSON；`?format=csv` 為結果表。
- 完整原始觀測另存在 `data/raw/<run_id>/observations.jsonl`，不是從估計結果逆推。
- 新開公開頁面在下一筆每秒狀態取得當前畫面；尚無資料或逾 10 秒未收時明確提示。
