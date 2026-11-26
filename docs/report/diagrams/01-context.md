# 第一層：系統全景

```mermaid
flowchart LR
  Field["現場操作者"] -->|"本地 HTTP／WS：開始或結束巡查、檢查品質、設定場地（新版座標設定 RPi 待部署）"| System["BLE 移動盤點與定位系統\n（RPi 4B 共用核心與本地紀錄）"]
  System -->|"本地即時畫面、目標 ID／數量／估計位置、CSV／回放匯出"| Field
  Tags["場域 BLE Anchor／Target\n（4 Anchor＋2 Target＋2 備品）"] -.->|"待刷機／射頻驗證：BLE 廣播（ID、角色、1 m 參考值）與接收 RSSI"| System
  Gazebo["組員 Gazebo／SITL\n（外部負責）"] -.->|"待整合：HTTP 觀測 JSON v1.0（僅 RSSI／高度）；真值另存評估"| System
  System -.->|"待部署：MQTT TLS 8883 發布每秒最新狀態（無雲端歷史）"| AWS["AWS IoT Core／Cognito\n（待部署；0 元 Free Plan 限制）"]
  AWS -.->|"待部署：Cognito 登入＋MQTT WSS 443 唯讀即時狀態"| Viewer["組員／老師\n（公開唯讀觀看者）"]
  GitHub["GitHub Pages\n（已發布）"] -->|"HTTPS 443：唯讀前端與合成／匯入紀錄回放（免登入）"| Viewer
```

圖例與狀態說明：

- **實線箭頭（`-->`）**：已實作且具軟體／本機或公開頁驗證證據之路徑（見 `TEST-004`、`TEST-010`、`TEST-011`、`TEST-012`、`TEST-013`）。
- **虛線箭頭（`-.->`）**：尚待硬體刷機、雲端部署或外部組員整合之路徑（見 `HW-001`、`SIM-001`、`CDX-CLOUD`）。
- **系統邊界**：系統方塊刻意不展開內部模組，呈現使用者、感測／模擬輸入與外部服務。具 WGS84 地理參考時，前端另可向 OpenStreetMap 取得公開底圖圖磚（選用；失敗或無地理參考時退回 Local 網格）。
- **部署差異**：RPi 目前運行 `0bdeea4` 服務（`TEST-010`）；新版座標設定（`9225d6b`）已通過本機與桌面驗證（`TEST-011`、`TEST-012`），因 SSH 逾時尚待部署至 RPi。XIAO 韌體已完成六種角色 CI 編譯（`TEST-006`），尚未刷機與實測射頻。
