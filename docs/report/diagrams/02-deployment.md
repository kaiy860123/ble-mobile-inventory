# 第二層：軟硬體部署與通訊

```mermaid
flowchart TB
  subgraph Field["實體場域（HW-001 待刷機／場地量測）"]
    Anchors["4 × XIAO ESP32C3 Anchor\nA01–A04；座標由 RPi 管理"]
    Targets["2 × XIAO ESP32C3 Target\nT01–T02；巡查期間靜止"]
    Spare["2 × XIAO ESP32C3 備品\n韌體支援 A05／T03"]
  end
  subgraph Pi["RPi 4B（已部署 0bdeea4：BLE／HTTP／巡查；新版 9225d6b 座標設定待部署）"]
    BlueZ["BlueZ／Bleak\nBLE 掃描器"] -->|"解碼原型封包（0xFFFF）＋接收 RSSI"| Core["Python 共用核心\n（單一 systemd 服務程序）"]
    Core -->|"附加寫入 JSONL／manifest；設定檔原子替換（CSV 按需匯出）"| Files["本地檔案系統\ndata/raw、data/processed、config/"]
    Core -->|"同程序狀態快照、巡查控制與設定處理"| HTTP["aiohttp HTTP／WebSocket\n本地 8080 埠"]
  end
  Anchors -.->|"待刷機／射頻驗證：BLE 非連線廣播（範例 500 ms、+3 dBm）"| BlueZ
  Targets -.->|"待刷機／射頻驗證：BLE 非連線廣播（範例 500 ms、+3 dBm）"| BlueZ
  Local["同區域網路電腦／手機"] <-->|"HTTP（X-Control-Token）／WS 8080：即時畫面、巡查與設定"| HTTP
  Sim["組員 Gazebo 主機"] -.->|"待整合：HTTP POST /api/observations（Bearer Token、JSON v1.0）"| HTTP
  Core -.->|"待部署：MQTT over TLS 8883（X.509 憑證、QoS 0、每秒最新狀態）"| IoT["AWS IoT Core\n（待部署）"]
  Pages["GitHub Pages\n（已發布）"] -->|"HTTPS 443：靜態前端與示範回放"| Public["遠端瀏覽器\n（公開唯讀）"]
  Auth["AWS Cognito\n（待部署）"] -.->|"HTTPS 443：受邀帳號登入與臨時憑證"| Public
  IoT -.->|"待部署：MQTT over WSS 443（SigV4、QoS 0 唯讀訂閱）"| Public
  OSM["OpenStreetMap 公共圖磚\n（選用）"] -->|"HTTPS 443：WGS84 底圖圖磚（失敗退回 Local）"| Public
```

圖說與部署狀態：

- **實線／虛線約定**：實線代表已實作並具本機／CI／既有機台驗證之路徑；虛線代表尚待刷機、雲端部署或外部整合之路徑。
- **網路邊界**：本地 HTTP／WebSocket（8080 埠）僅供同區域網路使用，不直接對網際網路開放；跨網路觀看改走 AWS 加密通道（TLS 8883 與 WSS 443），且公開瀏覽器僅能唯讀訂閱或檢視回放，無遠端巡查控制與座標修改權限（`TEST-013`）。
- **現況差異**：RPi 4B 已驗證 `0bdeea4` 之 `systemd` 服務、HTTP 200 與 BlueZ 掃描（`TEST-009`、`TEST-010`）；新版座標設定介面（`9225d6b`）已在本機驗證（`TEST-011`、`TEST-012`），因 RPi SSH 逾時尚未傳檔部署。XIAO 僅完成六種角色編譯（`TEST-006`），未刷機；AWS 僅完成模板與離線 preflight（`TEST-007`），未建立雲端資源。
