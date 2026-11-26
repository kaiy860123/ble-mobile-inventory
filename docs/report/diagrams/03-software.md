# 第三層：軟體技術棧與模組分工

```mermaid
flowchart LR
  subgraph ExternalInputs["觀測輸入來源"]
    BLE["inputs.py：BleSource\n（已實作；待 XIAO 刷機封包）"]
    Synthetic["inputs.py：SyntheticSource\n（明確標示之合成測試來源）"]
    Gazebo["組員 Gazebo／SITL\n（外部；send-observations.py 可送樣本）"]
  end

  subgraph RPiProc["RPi 單一 Python 服務程序（src/ble_inventory/）"]
    Server["server.py\naiohttp HTTP／WS 與 1 s ticker 協調"]
    Contract["contracts.py\n觀測 schema v1.0 驗證（拒收真值）"]
    Engine["engine.py\nInventoryEngine：任務、去重、窗口"]
    Solver["positioning.py\n濾波、測距、兩階段穩健求解"]
    Coord["coordinates.py\nGeoReference：Local／ENU／ECEF／WGS84"]
    Config["config.py\n設定正規化、驗證與公開過濾"]
    SiteCfg["site_settings.py\n白名單編輯、revision 鎖與原子寫入\n（本機已驗；RPi 待部署）"]
    Store["storage.py\nRunStore：JSONL、manifest、CSV 匯出"]
    Cloud["cloud.py\nCloudPublisher：非阻塞 MQTT 最新狀態"]
  end

  subgraph Frontend["瀏覽器前端（web/，esbuild 打包）"]
    MainJS["main.js＋state.js\nSVG 網格、Leaflet 底圖、表格、回放"]
    SettingsJS["site-settings.js\n本地座標編輯對話框\n（公開端停用）"]
    CloudJS["cloud.js\nCognito 登入＋SigV4／MQTT WSS 唯讀"]
  end

  subgraph AWSCloud["AWS 雲端（待部署）"]
    IoT["AWS IoT Core／Cognito"]
  end

  subgraph OfflineEval["離線校正與事後評估（scripts/；不進入求解器）"]
    CalibCSV["已知距離 RSSI 校正 CSV\n（待實測）"]
    Calib["calibrate-rssi.py\n線性最小平方法擬合 P_1m 與 n"]
    Truth["獨立真值檔 truth.jsonl\n（僅供評估）"]
    Evaluate["evaluate-run.py\n依 position_at 對齊計算水平誤差"]
  end

  BLE -.->|"實體 BLE 觀測批次（待 XIAO 封包）"| Server
  Synthetic -->|"合成觀測批次（demo 模式）"| Server
  Gazebo -.->|"待整合：POST /api/observations（Bearer Token）"| Server

  Server -->|"驗證批次欄位與時間"| Contract
  Server -->|"ingest 合法觀測與 1 s snapshot"| Engine
  Engine -->|"驗證批次"| Contract
  Engine -->|"濾波、斜距轉水平、兩階段求解"| Solver
  Engine -->|"Local 轉 WGS84 座標"| Coord
  Engine -->|"過濾 cloud 私密欄位"| Config

  Server -->|"接受後寫入 raw JSONL 與 1 s 狀態快照"| Store
  Server -->|"預覽／原子保存並切新任務"| SiteCfg
  SiteCfg -->|"正規化與 WGS84 轉 Local"| Config
  Config -->|"座標轉換驗證"| Coord

  Server <-->|"GET／POST /api/settings（X-Control-Token）"| SettingsJS
  SettingsJS -->|"套用成功後更新畫面狀態"| MainJS
  Server -->|"WS /api/ws 狀態推播與 /api/control、/api/export"| MainJS

  Server -.->|"待雲端驗證：精簡最新狀態（QoS 0）"| Cloud
  Cloud -.->|"待部署：MQTT TLS 8883"| IoT
  IoT -.->|"待部署：MQTT WSS 443 唯讀"| CloudJS
  CloudJS -.->|"唯讀狀態快照回呼"| MainJS

  CalibCSV -.->|"多距離樣本（待實測）"| Calib
  Calib -.->|"人工審視後寫入 site config"| Config
  Store -->|"states.jsonl 或回放 JSON"| Evaluate
  Truth -->|"獨立水平真值（不進入定位核心）"| Evaluate
```

圖說與邊界說明：

- **單一程序結構**：`RPi 單一 Python 服務程序` 內的所有模組由 `cli.py` 啟動並在同一個 `aiohttp` 程序內執行，`server.py` 負責協調輸入、`engine.py`、`storage.py`、`site_settings.py` 與 `cloud.py`；`engine.py` 本身不直接相依於檔案寫入、HTTP 或 MQTT，亦不把各檔案拆分為獨立微服務。
- **儲存與雲端範圍**：持久化全部以本地檔案系統（`observations.jsonl`、`states.jsonl`、`manifest.json`、設定檔與私密備份）完成；第一版未部署 EC2、DynamoDB 或雲端歷史資料庫。
- **真值隔離**：`contracts.py`（搭配 `src/contracts/observation.schema.json`）以白名單欄位拒收任何真值座標；`truth.jsonl` 僅進入事後評估腳本 `scripts/evaluate-run.py`。
- **狀態說明**：`site_settings.py` 與 `web/site-settings.js` 已通過本機自動化與瀏覽器驗證（`TEST-011`、`TEST-012`），公開頁確認停用編輯（`TEST-013`），RPi 新版尚待部署；Gazebo、實體 XIAO 校正與 AWS 仍待外部交付或實測部署。
