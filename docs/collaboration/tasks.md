# 共同開發任務

以下是可交接的任務規劃，不代表另一工具已開始執行。

最新：AG-002 的本機交付 `28d61d6dd4e82002d53e17a4119c54aba061c679` 已找到並匯入專用 ref 待審；AG-001 已由官方 CLI 自動派工。實際執行狀態以 bridge status 與交接為準，不再要求使用者代貼。

## CDX-AUTO-REVIEW — Antigravity 變更後自動審查

- 使用者指定：兩工具使用同一專題資料夾。
- 狀態：已建立本聊天 ACTIVE heartbeat（`ble-antigravity`），每 5 分鐘檢查；指紋穩定後自動審查與測試，規則見 `auto-review.md`。
- 偵測：已追蹤檔案與未忽略新檔；新增／修改／刪除、未提交變更皆涵蓋。共用 checkout 依內容而非作者推測判斷。
- 寫檔：開發中唯讀審查，交接最後標記 ready_for_review 後再修正與整合。審查途中變更保留新版待審。
- 證據：TEST-014；排程工具回傳建立 ACTIVE、view 可檢視；實際後續排程觸發仍須依第一筆執行紀錄確認。

## CDX-SETTINGS — 本地座標設定介面

- 負責：Codex。
- 狀態：本地實作／API／桌面操作已驗證；RPi 新版部署 blocked（SSH connect 逾時，尚未傳檔）。
- 範圍：Anchor Local／WGS84、場地範圍、天線高度、WGS84 原點／旋轉角、預覽與持久保存。
- 契約：`docs/design/site-settings.md`。
- 驗收：非法值與過期版本不改檔；雲端設定不被覆寫；成功保存後開始新巡查，舊紀錄可追溯；公開頁不提供遠端修改。
- 程式交接基準：`9225d6be262071ab8ad31d6fb1f8b76526a5b04e`（啟動前回報 checkout 完整 SHA）；驗證見 TEST-011／TEST-012／TEST-013。Antigravity 只在指定新增測試檔驗證，不改相同核心檔案。

## AG-001 — 座標設定獨立驗證

- 負責：Antigravity；狀態：已由 Codex 透過官方 CLI 自動啟動，結果待交付／驗收；以 bridge status 為準。
- 前置：CDX-SETTINGS 交付可驗證版本（本次已完成本地驗證，見 `docs/handoffs/CDX-SETTINGS.md`；接手時回報完整 SHA）。
- 可新增：`tests/test_settings_independent.py`、`docs/handoffs/AG-001-result.md`，必要時新增 `tests/browser/` 的可重現案例。
- 只讀：核心、設定 API、既有前端程式。
- 逐項驗證：Local 儲存與重新載入、WGS84 含旋轉角、欄位空白／NaN／越界、Anchor 共線、過期 revision、雙頁面衝突、取消不改檔、預覽不改檔、保存失敗仍維持舊狀態、公開端不可修改、手機／鍵盤操作。
- 完成：提供預期／實際、執行命令與結果、失敗重現及證據；若全通過也寫清楚未測環境。
- 合併：Codex 審查、重跑後決定，不直接推 main 或部署 RPi。

## AG-002 — 報告四層圖與公式對照

- 負責：Antigravity；狀態：交付 28d61d6 已完成 Codex 文件整合審查與 accept，見 docs/reviews/2026-11-26-AG-002-codex.md。
- 可修改：`docs/report/diagrams/`、新增 `docs/report/diagram-review.md` 與 `docs/handoffs/AG-002-result.md`。
- 只讀核對：`docs/report/methods.md`、定位／座標程式、需求與測試紀錄。
- 驗收：四層圖一致、每條連線有資料／協定語意、現有與待部署標示一致；逐式檢查符號、單位、旋轉方向、殘差與真實誤差的區別。
- 完成：圖檔、圖說、修正清單；沒有實測資料的圖表保留空位，不代填數字。

## AG-003 — 實驗彙整工具開發（AG-001／AG-002 後）

- 負責：Antigravity 開發，Codex 審查；狀態：todo。
- 可新增：`scripts/summarize-experiments.py`、`tests/test_experiment_summary.py`、`docs/report/experiments-template.csv`、`docs/handoffs/AG-003-result.md`。既有定位核心、評估腳本與原始資料維持只讀。
- 輸入：既有評估 JSON，加上明確填寫的實驗 metadata（來源、場地、版本、run_id、應評估時點／應盤點集合、缺測原因）。
- 輸出：可比較的實驗表，列有效樣本、MAE／RMSE／P50／P95、定位成功率、盤點召回率及限制；若沒有分母／應盤點集合，輸出未提供，不猜測。
- 驗收：合成 fixture 可獨立手算；分母為零、缺值、混合來源／不同版本標示正確；不將未量測延遲填成一秒，不重複計分舊位置；紀錄來源可追溯。
- 邊界：此任務補足目前實驗彙整缺口，不代表已新增任何實機結果；欄位與 `methods.md` 定義衝突時列勘誤交 Codex 協調。

## CDX-CLOUD — AWS 登入後部署與整合

- 負責：Codex；狀態：blocked。
- 阻塞：尚無可用的 AWS 執行登入環境；既有瀏覽器操作曾因無法確認網址而中斷。
- 驗收：Free Plan 狀態核對、IoT／Cognito 部署、登入唯讀、RPi 發布與斷線恢復實測、0 元現金支出限制。

## HW-001 — 六個 XIAO 刷機與場地量測

- 負責：使用者接線／標記，Codex 執行刷機與查核。
- 狀態：blocked；使用者已指定稍後接線。
- 驗收：每個 ID 對應實體標籤、RPi 實際收到封包、Anchor 座標與天線高度實測、校正樣本完整。

## SIM-001 — Gazebo 觀測串接

- 負責：Gazebo 組員；Codex 整合。
- 狀態：等待外部交付，未掌握組員內部進度。
- 交付：程式版本、schema v1.0 觀測 JSONL、獨立真值、模擬時間對牆鐘方法、操作說明。
- 驗收：同一核心完成兩階段定位；真值未進入求解器；保留模擬場景、噪聲／漏收設定與誤差報告。

## CDX-REPORT — 實驗、報告與展示整合

- 負責：Codex 統整，Antigravity 圖表與勘誤，使用者／組員提供實測。
- 狀態：方法與架構草稿製作中；最終結果待 HW-001、SIM-001、CDX-CLOUD。
- 時程：12/10 主要功能、12/17 整合、12/24 展示／繳交。
