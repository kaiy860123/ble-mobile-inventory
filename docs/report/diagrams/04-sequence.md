# 第四層：關鍵流程序列

## 巡查觀測與定位

```mermaid
sequenceDiagram
  participant Tag as Anchor／Target（待刷機）
  participant Input as BLE／外部觀測來源
  participant Server as server.py（協調與 API）
  participant Core as contracts.py＋engine.py＋positioning.py
  participant Store as storage.py（本地檔案）
  participant Web as 本地網頁（main.js）
  participant Cloud as AWS IoT（Sydney 已部署）

  Tag-->>Input: 待射頻驗證：BLE 廣播（ID、角色、1 m 參考值）＋接收 RSSI
  Input->>Server: 觀測批次（時間、ID、RSSI、可選高度；外部 API 另驗 Bearer Token 與 UTC ±30 s）
  Server->>Core: validate_batch 與 engine.ingest(batch)
  alt 觀測非法／含真值欄位／序號重複或倒序
    Core-->>Server: 拋出 ValueError（拒絕批次）
    Server-->>Input: 外部模式回傳 400（不寫入原始觀測）
  else 任務進行中且批次合法
    Core->>Core: 依名單去重計數（Target 加入 S_R）、逾時重置濾波、中位數＋EMA、測距
    Core->>Core: 第一階段：取 anchor_ttl_s（範例 3 s）內 Anchor 扣除高度差並求掃描器位置
    alt 掃描器解有效（≥3 Anchor、SVD 條件合格、殘差 ≤ 2.5 m）
      Core->>Core: 更新掃描器位置與航跡；位移 ≥ 0.15 m 時加入 Target 移動窗口（120 s、上限 240 筆）
      alt Target 窗口達標（≥6 筆、基線 B ≥ 1.5 m、SVD 合格、殘差 ≤ 2.5 m）
        Core->>Core: 第二階段求解並更新 Target 位置與 position_at
      else Target 觀測不足、幾何退化或殘差過大
        Core->>Core: 標示 insufficient 與原因，保留最後有效位置
      end
    else 掃描器定位失敗
      Core->>Core: 掃描器與當批 Target 標示 insufficient，保留最後有效位置
    end
    Server->>Store: 追加已接受原始觀測（data/raw/<run_id>/observations.jsonl）
  end
  Note over Server,Store: 每 publish_interval_s（範例 1 s）執行狀態發布；manifest.json 於任務啟動時建立
  opt 任務進行中
    Server->>Store: 追加精簡狀態快照（data/processed/<run_id>/states.jsonl）
  end
  Server-->>Web: WebSocket /api/ws 推送目前狀態（逾 10 s 未收標為 stale）
  opt 雲端已啟用且連線（PC 合成已驗，RPi 待串接）
    Server-->>Cloud: MQTT TLS 8883 發布精簡最新狀態（QoS 0、不保留；斷線不影響本地）
  end
```

## 座標設定切換（本地已驗證，RPi 新版待部署）

```mermaid
sequenceDiagram
  participant User as 本地操作者
  participant UI as 座標設定對話框（site-settings.js）
  participant API as 設定 API（server.py＋site_settings.py）
  participant File as 場地設定檔與私密備份
  participant Run as 巡查引擎與 RunStore

  User->>UI: 開啟「場地／Anchor 座標設定」
  UI->>API: GET /api/settings（X-Control-Token＋同源檢查）
  API-->>UI: 可編輯欄位與目前 revision（SHA-256；不含 cloud 私密欄位）
  User->>UI: 編輯 Anchor（Local／WGS84）、範圍、高度或地理原點
  UI->>API: POST /api/settings/preview（X-Control-Token＋候選設定）
  API-->>UI: 轉換預覽與幾何／範圍警示（不寫檔、不改任務）
  User->>UI: 點擊「保存並開始新巡查」
  UI->>API: POST /api/settings（X-Control-Token＋候選設定＋expected_revision）
  API->>API: 取得鎖，驗證權限、revision、設備名單不變、數值、WGS84 與 SVD 幾何
  alt 驗證失敗（400）或版本／名單衝突（409）
    API-->>UI: 回傳明確錯誤，維持原生效設定與原任務
  else 驗證通過
    API->>Run: 建立新引擎與新 RunStore，並寫入舊任務最後狀態快照
    API->>File: 備份原設定並 fsync＋os.replace 原子替換
    alt 磁碟或寫入失敗（507）
      API->>Run: 標記未提交新任務為 aborted.txt，維持原設定與原任務
      API-->>UI: 回傳 507 錯誤提示
    else 保存成功（200）
      API->>Run: 切換至新設定與新 run_id，關閉舊 RunStore（舊紀錄完整保留）
      API-->>UI: 回傳新 revision、警示與新任務狀態
    end
  end
```

圖說與驗證狀態：

- **定位與真值邊界**：Target 去重計數（$S_R$）發生在合法觀測進入名單核對之後，即使當下 Anchor 不足而無法定位掃描器，已收到的 Target 仍計入本次已盤點（見 `tests/test_engine.py:test_missing_anchors_no_fabricated_solution`）；真值資料絕不進入本序列之定位核心。
- **設定交易狀態**：本地數值、交易失敗回復（`400`/`409`/`507`）、API 與桌面瀏覽器操作已通過 `TEST-011`、`TEST-012`，公開頁已確認停用設定編輯（`TEST-013`）；RPi 新版更新因 SSH 逾時尚待部署（`ISSUE-010`），最終報告須保留此部署差異，待現場複驗後再更新。
