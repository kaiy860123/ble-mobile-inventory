# 報告四層架構圖與公式一致性審查報告（AG-002）

- 審查任務：AG-002
- 審查者：Antigravity（交付 Codex 審查）
- 審查日期：2026-11-26
- 基準 Commit：`51648b7bb00ed5841931c4bebc805aa36c6e2520`（程式交付基準 `9225d6be262071ab8ad31d6fb1f8b76526a5b04e`）
- 工作分支：`antigravity/AG-002-diagram-formula-review`
- 核對範圍（唯讀）：`docs/report/methods.md`、`docs/report/report-draft.md`、`docs/requirements.md`、`docs/contracts.md`、`docs/design/site-settings.md`、`docs/design/coordinates.md`、`docs/design/architecture.md`、`docs/test-log.md`、`docs/issues.md`、`src/ble_inventory/*.py`、`scripts/calibrate-rssi.py`、`scripts/evaluate-run.py`、`web/*.js`、`config/site.example.json`、`firmware/`、`infra/aws/template.json`
- 修改範圍：`docs/report/diagrams/01-context.md`、`02-deployment.md`、`03-software.md`、`04-sequence.md`

---

## 一、審查總結

1. **公式核心數學正確性**：`docs/report/methods.md` 第 2–10 節的主要數學式（因果中位數＋EMA、對數距離測距與最小平方校正、已知高度差水平投影、第 0 點差分線性初值、Huber 加權 Gauss-Newton IRLS、SVD 條件數、包圍盒基線 $B$、Local 旋轉至 ENU、WGS84↔ECEF↔ENU 轉換、去重／可見數、水平誤差與 MAE/RMSE/P50/P95）與目前程式碼（`positioning.py`、`coordinates.py`、`engine.py`、`calibrate-rssi.py`、`evaluate-run.py`）之**核心推導與旋轉方向均一致**，未發現會導致錯誤定位或錯誤座標轉換的公式符號反號錯誤。
2. **公式文件與程式對照之勘誤與待補強項**：共整理 **14 項（F-01～F-14）**，涵蓋符號重載（`e` 同時指涉有號測距殘差與非負真實位置誤差、`X` 同時指涉 ECEF 標量與三維向量）、程式預設值與範例設定差異（`RssiFilter` 預設 `(0.4, 5)` vs `site.example.json` `(0.65, 3)`）、文件漏列實作條件（`anchor_ttl_s=3 s`、`maxlen=240` 與 `0.15 m` 硬編碼、第二階段同樣套用 `max_residual_m=2.5 m`、未加權殘差與 Huber 加權目標的交互作用、名單過濾）、第 11 節合成表遺漏 `P50` 欄位，以及 2 項程式防禦邊界提醒。依任務邊界，**未直接修改 `methods.md` 或定位核心**，交由 Codex 統整修正。
3. **四層架構圖修正**：原版四圖存在多處狀態標示不一致（例如第一層實體 BLE 用實線而第二層用虛線、第二層未反映 RPi 仍為舊版 `0bdeea4`、第一層 AWS 節點為斷頭未連向觀看者）、連線缺少協定／資料語意（第三層 16 條連線有 15 條無標籤、第二層內部 3 條無標籤）、模組相依方向失真（第三層將 `storage.py`/`server.py`/`cloud.py` 畫成由 `engine.py` 呼叫，實際由 `server.py` 協調），以及第四層遺漏初始 `GET /api/settings` 與非法批次拒絕／`507` 磁碟失敗回復分支。四份圖檔皆已依程式碼與測試紀錄修正完成。
4. **無實測資料表位查核**：確認 `docs/report/report-draft.md` 與 `docs/report/methods.md` 並未將合成測試數據冒充為實體 BLE、Gazebo 或 AWS 實測結果；下文第四節補充報告結果章應保留之待補實測空位對照，避免後續撰寫誤填。

---

## 二、四層架構圖審查與修正清單

### 2.1 第一層：`docs/report/diagrams/01-context.md`（系統全景）

| 編號 | 發現問題 | 依據（程式／紀錄） | 修正內容 |
| --- | --- | --- | --- |
| D1-1 | `場域 BLE Anchor／Target --> 系統` 使用實線且無狀態標註，與 `report-draft.md`「虛線標示待部署／外部整合」及 `02-deployment.md` 虛線矛盾 | `TEST-006` 僅完成編譯；`HW-001` 尚未刷機與射頻實測 | 改為虛線 `-.->`，標註「待刷機／射頻驗證：BLE 廣播（ID、角色、1 m 參考值）與接收 RSSI」 |
| D1-2 | `AWS IoT Core／Cognito` 成為孤立終點，未連向 `組員／老師`；同時 `組員／老師 --> 系統` 模糊了公開唯讀與本地端界線 | `docs/aws-deployment.md`、`web/cloud.js`、`R14`/`R15` | 補上 `AWS -.-> 組員／老師`（待部署：Cognito 登入＋MQTT WSS 443 唯讀即時狀態），並釐清 `GitHub Pages --> 組員／老師` 為免登入回放與唯讀前端 |
| D1-3 | 「設定場地」未標示 RPi 新版尚未部署的差異 | `TEST-012`、`ISSUE-010` | 在現場操作者連線與圖說中明註新版座標設定（`9225d6b`）本機已驗、RPi 待部署 |
| D1-4 | 缺少圖例與選用 OSM 底圖說明 | `web/main.js:68`、`R09`/`R24` | 補齊實線／虛線圖例，於圖說說明 OpenStreetMap 底圖為選用且失敗時退回 Local 網格 |

### 2.2 第二層：`docs/report/diagrams/02-deployment.md`（軟硬體部署與通訊）

| 編號 | 發現問題 | 依據（程式／紀錄） | 修正內容 |
| --- | --- | --- | --- |
| D2-1 | 子圖標題僅寫「RPi 4B：服務已部署」，未區分已部署舊版 `0bdeea4` 與尚未部署的新版 `9225d6b` 座標設定 | `docs/collaboration/README.md` L23、`TEST-010`、`TEST-012` | 更新子圖標題與圖說，明確標示 `0bdeea4` 已部署、新版 `9225d6b` 座標設定待部署 |
| D2-2 | 內部三條連線（`BlueZ --> Core`、`Core --> Files`、`Core --> HTTP`）完全無資料／協定標籤；外部連線缺少驗證與傳輸語意 | AG-002 驗收條件；`inputs.py`、`storage.py`、`server.py`、`cloud.py`、`web/cloud.js`、`firmware/platformio.ini` | 逐條補齊標籤：BLE 非連線廣播（500 ms、+3 dBm）、`0xFFFF` 解碼、JSONL／manifest／原子設定與 CSV 按需匯出、`HTTP（X-Control-Token）／WS 8080`、`POST /api/observations（Bearer Token、JSON v1.0）`、`MQTT TLS 8883（X.509、QoS 0）`、`MQTT WSS 443（SigV4、QoS 0 唯讀）` |
| D2-3 | 未標示備品可刷韌體環境與選用 OSM 底圖連線 | `firmware/platformio.ini:27-30`、`web/main.js:68` | 標註備品支援 `A05`/`T03`，補入選用 `OpenStreetMap 公共圖磚`（HTTPS 443，失敗退回 Local） |

### 2.3 第三層：`docs/report/diagrams/03-software.md`（軟體技術棧與模組分工）

| 編號 | 發現問題 | 依據（程式／紀錄） | 修正內容 |
| --- | --- | --- | --- |
| D3-1 | 16 條連線中有 15 條缺少資料／協定語意標籤 | AG-002 驗收條件 | 為所有連線補上資料型別、呼叫或協定標籤 |
| D3-2 | 相依方向與實作不符：原圖畫成 `Engine --> Store`、`Engine --> API`、`Engine -.-> Cloud`、`Settings --> Engine` | `src/ble_inventory/engine.py`（只相依 `config`/`contracts`/`coordinates`/`positioning`）；`server.py` 協調 `inputs`、`engine`、`storage`、`site_settings`、`cloud` | 重繪為以 `server.py` 為單一程序協調中心，`engine.py` 維持純記憶體定位狀態機，明確列出 `config.py`、`site_settings.py`、`web/site-settings.js`、`web/main.js`、`web/state.js` |
| D3-3 | `BleSource` 與 `外部觀測 API` 均以無註記實線畫出，未反映待刷機與 Gazebo 待外部交付狀態；亦漏列離線校正腳本 `calibrate-rssi.py` | `HW-001`、`SIM-001`、`scripts/calibrate-rssi.py`、`methods.md` §3 | 以虛線標示待刷機 BLE 封包、待整合 Gazebo 與待實測校正 CSV；新增「離線校正與事後評估」區塊強調不進入求解器 |

### 2.4 第四層：`docs/report/diagrams/04-sequence.md`（關鍵流程序列）

| 編號 | 發現問題 | 依據（程式／紀錄） | 修正內容 |
| --- | --- | --- | --- |
| D4-1 | 巡查序列圖缺少非法／含真值／倒序批次拒收分支，未區分第一階段（Anchor）與第二階段（Target）兩層失敗條件，亦未寫明 `anchor_ttl_s`、移動門檻、WebSocket 與 `manifest.json` 時機 | `server.py:134-196`、`engine.py:37-116`、`storage.py:16-36` | 拆清 `Server` 與 `Core` 職責，補上拒收分支、兩階段條件（`anchor_ttl_s=3 s`、`≥3 Anchor`、`位移 ≥0.15 m`、`≥6 筆`、`B ≥1.5 m`、`殘差 ≤2.5 m`）、`observations.jsonl`/`states.jsonl`/`manifest.json` 寫入時機與協定語意 |
| D4-2 | 座標設定序列圖漏掉開啟表單時的 `GET /api/settings`（以致 `expected_revision` 來源不明），也未區分 `400`/`409`/`507` 錯誤碼與磁碟寫入失敗的 `aborted.txt` 回復機制 | `web/site-settings.js:53-67`、`server.py:50-105`、`site_settings.py:121-145` | 補上 `GET /api/settings`、HTTP 路徑與 `X-Control-Token`／同源檢查，明確呈現 `400`/`409` 與 `507`（標記 `aborted.txt` 並保留原設定與原任務）兩類失敗路徑 |

---

## 三、公式、符號、單位與實作逐項核對及勘誤清單

> 依 AG-002 規範，本節**僅記錄來源、推導、對照與影響**，未直接修改 `docs/report/methods.md` 或 `src/ble_inventory/` 程式碼，交由 Codex 審查後決定修訂。

### 3.1 逐節核對總表

| 章節 | 公式／定義 | 對應程式 | 核對結論 | 關聯勘誤 |
| --- | --- | --- | --- | --- |
| §1 符號與單位 | 符號、單位、旋轉角約定 | 全域 | 核心正確；有符號重載與缺漏符號 | F-01（於 §2）、F-02（於 §1）→ 見下方詳細編號 |
| §2 RSSI 濾波 | 因果中位數＋EMA | `positioning.py:19-29`、`engine.py:55-57`、`site.example.json` | 數學式一致；預設值與重置門檻需釐清 | F-03、F-04 |
| §3 測距與校正 | 對數距離反解與最小平方校正 | `positioning.py:7-10`、`scripts/calibrate-rssi.py:16-26`、`engine.py:59-60` | 數學式與範例數值（10 m）正確；有門檻精確值與 `None` 邊界 | F-05、F-06 |
| §4 高度差投影 | $\rho = \sqrt{\widehat d^2 - (\Delta h)^2}$ | `positioning.py:13-16`、`engine.py:64,71,87` | 數學式一致；需提醒 WGS84 橢球高與 Local 高度基準對齊 | F-07 |
| §5 第一階段初值 | $2(a_i-a_0)^T p = \rho_0^2 - \rho_i^2 + \|a_i\|^2 - \|a_0\|^2$ | `positioning.py:45-47`、`engine.py:66-75` | 代數推導與程式完全一致；漏列索引範圍與 `anchor_ttl_s` | F-08 |
| §6 非線性與穩健加權 | Huber 權重、Jacobian、IRLS、SVD、$R_{\text{range}}$ | `positioning.py:39-68` | 推導與程式完全一致；有符號重載與未加權殘差交互作用需說明 | F-01、F-09 |
| §7 第二階段 Target | 移動窗口、$0.15\text{ m}$ 門檻、基線 $B \ge 1.5\text{ m}$ | `engine.py:32,83-116`、`positioning.py:43-44` | 數學式與程式一致；漏寫硬編碼常數與第二階段殘差門檻 | F-10 |
| §8 Local／ENU／WGS84 | 旋轉矩陣、WGS84 橢球常數、$R$、ECEF 緯度迭代 | `coordinates.py:5-75` | 旋轉方向（+X 自東逆時針）、矩陣正交性（$\det R = +1$）與正逆轉換完全一致；有向量符號重載與高緯邊界註記 | F-02、F-11 |
| §9 盤點與暫未收到 | $S_R$、$C_R$、$C_{\text{visible}}(t)$（$\tau=10\text{ s}$） | `engine.py:51-63,129-145` | 數學式與程式一致；應補名單過濾與掃描器 `stale` 使用 `anchor_ttl_s` | F-12 |
| §10–§11 評估與合成結果 | $e_k$、MAE／RMSE／P50／P95、成功率、召回率、合成數值 | `scripts/evaluate-run.py`、`web/public/demo.json`、`tests/fixtures/truth.jsonl` | 重跑數值至小數第 3 位完全一致；§11 表格缺 P50 欄，另有一處腳本空值防禦 | F-01、F-13、F-14 |

### 3.2 詳細勘誤與建議清單（交付 Codex 審查）

- **F-01（中／符號重載，易混淆核心概念）**：`methods.md` §6（L102）使用 $e_i(p) = \|p - a_i\| - \rho_i$ 表示**有號測距殘差**（單位 m，可正可負），而 §10（L235）又使用 $e_k = \sqrt{(\widehat x_k - x_k^*)^2 + (\widehat y_k - y_k^*)^2}$ 表示**非負真實水平位置誤差**（單位 m）。報告刻意強調必須區分「模型測距殘差」與「對獨立真值的位置誤差」，建議將 §6 測距殘差改記為 $\varepsilon_i(p)$ 或 $\delta_i(p)$（並與 §3 雜訊符號區分，例如 §6 用 $v_i(p)$），避免讀者在報告正文中混用符號。
- **F-02（低／符號重載與 §1 漏列符號）**：`methods.md` §8.2（L178）以 $X, Y, Z$ 表示 ECEF 的三個純量分量，但 §8.3（L187、L198）隨即以同一個大寫 $X, X_0$ 表示三維 ECEF 位置向量（`R(X - X_0)`）；建議改為粗體 $\mathbf{X}, \mathbf{X}_0$。另 §1 符號表漏列高度 $z$、高度差 $\Delta h$、權重矩陣 $W = \operatorname{diag}(w_1,\ldots,w_m)$、觀測數 $m$ 與基線 $B$，建議補齊。
- **F-03（低／範例設定與程式預設值差異）**：`methods.md` §2（L33）記載 `目前範例 w=3、α=0.65`，與 `config/site.example.json`（L12–13）相符；但程式中 `positioning.py:20` 的 `RssiFilter.__init__(self, alpha=0.4, window=5)` 及 `engine.py:56`／`config.py:48` 的 `config.get("median_window", 5)` 仍保留 `ISSUE-005` 之前的舊預設值 `(0.4, 5)`。若外部或測試呼叫 `RssiFilter()` 或自訂設定省略 `median_window`，會靜默退回 `w=5`。建議於 `methods.md` 註明 `(3, 0.65)` 來自場地設定檔，並由 Codex 評估是否同步程式預設值。
- **F-04（低／濾波器重置條件未寫明門檻）**：`methods.md` §2（L33）僅敘述「設備長時間未收到後重新建立濾波器」，實作 `engine.py:55` 使用的是 `now - last_seen > stale_after_s`（範例 `10 s`，非 `anchor_ttl_s = 3 s`）。建議在公式旁補註重置條件 $t_k - t_{k-1} > \tau$。
- **F-05（低／校正距離倍數門檻之精確值）**：`methods.md` §3（L62）寫「距離範圍約至少二倍」，實作 `scripts/calibrate-rssi.py:22` 檢查 `np.ptp(log10(d)) >= 0.3`，對應最小距離比值 $d_{\max}/d_{\min} \ge 10^{0.3} \approx 1.9953$（略小於 $2.0$，因 $\log_{10} 2 \approx 0.30103$），且 $d_0 = 1\text{ m}$ 為固定寫死。文件「約至少二倍」無誤，建議附註 $\Delta\log_{10}(d) \ge 0.3$ 以利重現。
- **F-06（中／程式防禦邊界提醒，已重現）**：`engine.py:59` 使用 `device.get("rssi_at_1m_dbm", obs.get("rssi_at_1m_dbm", self.config["rssi_at_1m_dbm"]))`。因 `contracts.py:40` 允許 `obs` 含 `"rssi_at_1m_dbm": null`（`None`），若設定檔未指定該設備的 `rssi_at_1m_dbm` 而封包明確帶入 `null`，`obs.get(...)` 會回傳 `None` 進而於 `positioning.py:8` 觸發 `TypeError: must be real number, not NoneType`（已以最小輸入重現）。此問題不影響現行合成來源與 BLE 解碼器（均省略或給數值），建議 Codex 後續於 `engine.py:59` 過濾 `None` 加固。
- **F-07（中／WGS84 橢球高與 Local 高度基準對齊影響）**：`coordinates.py:68-75` 將 Anchor 的 WGS84 橢球高轉為相對原點橢球高 $h_0$ 的局部天頂分量 $U = z_m$，並寫入 `device["position"][2]`（`config.py:21`）；而 `engine.py:71` 直接計算 $\Delta h = z_{\text{scanner}} - z_{\text{anchor}}$。若使用者填入實際場地 WGS84 Anchor 橢球高（例如台北約 20–30 m），卻將地理原點 `georeference.height_m` 留為 `0`，同時把 `scanner_height_m` 填為離地高度 `1.2 m`，將產生近 20 m 的虛假高度差而導致 `horizontal_distance` 全面拒收。`methods.md` §4 與 §8.2 已有提醒，建議於報告實驗與操作說明明確寫出「`georeference.height_m` 須對應 Local $z=0$ 基準面之橢球高」。
- **F-08（低／§5 索引範圍與 `anchor_ttl_s` 非同步視窗）**：`methods.md` §5（L89–90）未標註差分索引為 $i = 1, \ldots, m-1$（矩陣 $A \in \mathbb{R}^{(m-1)\times 2}$）；且未提及 `engine.py:68` 會納入最近 `anchor_ttl_s`（範例 `3.0 s`）內收到之 Anchor 觀測。這意味移動掃描器在第一階段求解時，不同 Anchor 的測距可能存在最高 3 秒時間差，屬於報告討論誤差來源時值得註明之工程特性。
- **F-09（低／§6 演算法細節與未加權殘差門檻的交互影響）**：
  1. `positioning.py:39-44` 的 SVD 共線檢查在線性初值之前執行，對 $C_{i,\cdot} = a_i - \bar{a}$ 計算奇異值；另 L50 對預測距離施加 $\max(\|p-a_i\|, 10^{-6})$ 下限（與 $J_i$ 分母一致）。
  2. 求解器內部使用 Huber 權重（$c = 1.5\text{ m}$）降低離群值槓桿，但事後品質閘門 `R_range <= max_residual_m`（`2.5 m`）採用的是**未加權** RMS（`positioning.py:64`）：多點窗口下單一極端離群值可能讓未加權 $R_{\text{range}}$ 超過 2.5 m 而拒收準確估計；反之在 4 Anchor 情境下，獨立數值實驗（矩形場域 `12×9 m`、真值 `(4.2, 5.1)`、僅 `A01` 測距 `+6.0 m`）測得真實位置誤差達 `5.110 m`，未加權殘差卻僅 `1.796 m ≤ 2.5 m`，具體印證 §6「小殘差不代表小真實位置誤差」之警語。建議於 §6 明述此未加權門檻特性。
- **F-10（低／§7 第二階段硬編碼常數與殘差門檻）**：`methods.md` §7（L145）列出 `窗口 120 s、上限 240 筆、至少六筆、位移 0.15 m、基線 1.5 m`，其中 `120 s`、`6 筆`、`1.5 m` 為設定檔參數，但 `240 筆`（`engine.py:32`）與 `0.15 m`（`engine.py:92`）為程式硬編碼常數；另 `engine.py:111` 在第二階段同樣套用 `max_residual_m = 2.5 m` 閘門，建議於 §7 補註。
- **F-11（低／§8.3 極高緯度數值邊界與 `coordinates.md` 舊文措辭）**：
  1. `coordinates.py:33` 與 `methods.md` L207 的 $h = p/\cos\varphi - N_\varphi$ 在中低緯度（如台灣 $\varphi \approx 25^\circ$）完全精確（經獨立驗證往返誤差 $< 10^{-9}\text{ m}$）；僅在極點鄰近（$p \ge 10^{-9}\text{ m}$ 且 $|\varphi| \to 90^\circ$）因 $\cos\varphi \to 0$ 精度低於 $Z/\sin\varphi - N_\varphi(1-e^2)$，對本專題場域無實務影響。
  2. 跨文件核對發現 `docs/design/coordinates.md` L18 仍殘留舊候選措辭「相對正北旋轉角」，與同檔 L24、`methods.md` §1/§8.1 及 `coordinates.py` 實作（「Local +X 相對正東逆時針角」）不一致；另 `coordinates.md` L46 與 `architecture.md` L3 狀態仍寫「未實作／訪談中」，建議 Codex 統整文件時同步更新。
- **F-12（低／§9 名單過濾與掃描器逾時規則）**：`engine.py:51-52` 會略過不在場地名單 `config["devices"]` 內的 BLE ID，故 $S_R$ 僅統計已註冊的 Target；另 `engine.py:140` 判定掃描器 `stale` 使用 `anchor_ttl_s`（範例 `3 s`），與 Target 的 `stale_after_s`（`10 s`）不同，建議於 §9 補充說明。
- **F-13（低／§10–§11 表格缺 P50 與分位數插值方法）**：`methods.md` §10 定義了 $P50 = Q_{0.5}(\{e_k\})$，且 `scripts/evaluate-run.py` 實際有輸出 `p50_m`（使用 NumPy 預設線性插值 `np.percentile(..., method="linear")`），但 §11 合成結果表漏列 P50 欄（重跑結果：`RPi01 = 1.029 m`、`T01 = 0.305 m`、`T02 = 0.116 m`；`MAE`/`RMSE`/`P95`/樣本數與 §11 皆相符）。另 `report-draft.md` §5.1（L60）僅引述 `TEST-002–TEST-005`，建議後續一併納入 `TEST-011`。
- **F-14（低／評估腳本空值防禦）**：`scripts/evaluate-run.py:24-28` 未檢查 `position_at is None` 即傳入 `bisect_left`；正常 `engine.py` 有效解皆帶時間戳，不會觸發，但若評估外部工具產生的異常快照可能拋出 `TypeError`。建議在後續 AG-003／維護時留意。

---

## 四、報告無實測資料圖表之空白保留查核

核對 `docs/report/report-draft.md`（§5、§6、§8）與 `docs/report/methods.md`（§11），目前**沒有**任何虛構的實體 BLE、Gazebo 或 AWS 實測數據。為確保後續補齊實驗章節時不混用來源或誤填未量測數值，建議報告結果章維持下列獨立空白表位，待 `HW-001`、`SIM-001`、`CDX-CLOUD` 取得真實紀錄並以 `AG-003` 工具彙整後再填入：

| 實驗來源 | 對應任務 | 狀態 | 有效解數／定位成功率 | MAE / RMSE / P50 / P95（m） | 盤點召回率 | 端到端延遲 | run_id 與版本 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 合成固定種子（`seed=5047`） | `TEST-005` | 已有合成基準（**非實測／非 Gazebo**） | RPi01: 90、T01: 85、T02: 65（成功率待 AG-003 定義分母） | 見 `methods.md` §11（P50 另為 1.029 / 0.305 / 0.116） | 待 AG-003 以 $G_R$ 計算 | 未量測（不填 1 s） | `synthetic-example-5047` |
| 實體步行 BLE 實驗（≥3 獨立任務） | `HW-001` | 待刷機與場地量測 | 待測 | 待測 | 待測 | 待測 | 待取得 |
| Gazebo／SITL 整合實驗 | `SIM-001` | 待組員交付 | 待測 | 待測 | 待測 | 待測 | 待取得 |
| AWS／GitHub Pages 跨網路端到端 | `CDX-CLOUD` | 待登入與部署 | 不適用（或依實測） | 不適用（或依實測） | 待測 | 待新增時間戳實測 | 待取得 |
