# 共同開發任務

2026-11-28 最新協作：使用者要求六 Anchor 精度改善由 Codex 與 Antigravity 共同開發。AG-005 已透過官方 CLI 交付 6cbd3d4ccb3eb5f9919bed41a22e5cd3725c18c2，Codex 修正後比較測試11案、完整非browser167案通過；接受範圍為離線工具，新增兩塊尚待刷機。下列較早日期項目保留歷程，不作最新部署狀態。具體分工見 [six-anchor-plan.md](six-anchor-plan.md)。

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

- 負責：Antigravity；狀態：自動交付 291f0d1 已完成 Codex 審查／accept；80 個獨立 API 案例重跑通過，四項發現已修正，browser／現場限制見審查報告。
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

- 負責：Antigravity 開發，Codex 審查；狀態：AG-001／AG-002 均 accept，已自動交付 febfb3e；Codex 修正三項發現後 21 個彙整／149 個非 browser 測試通過，接受範圍為離線工具，無新實測。
- 可新增：`scripts/summarize-experiments.py`、`tests/test_experiment_summary.py`、`docs/report/experiments-template.csv`、`docs/handoffs/AG-003-result.md`。既有定位核心、評估腳本與原始資料維持只讀。
- 輸入：既有評估 JSON，加上明確填寫的實驗 metadata（來源、場地、版本、run_id、應評估時點／應盤點集合、缺測原因）。
- 輸出：可比較的實驗表，列有效樣本、MAE／RMSE／P50／P95、定位成功率、盤點召回率及限制；若沒有分母／應盤點集合，輸出未提供，不猜測。
- 驗收：合成 fixture 可獨立手算；分母為零、缺值、混合來源／不同版本標示正確；不將未量測延遲填成一秒，不重複計分舊位置；紀錄來源可追溯。
- 邊界：此任務補足目前實驗彙整缺口，不代表已新增任何實機結果；欄位與 `methods.md` 定義衝突時列勘誤交 Codex 協調。

## CDX-CLOUD — AWS 登入後部署與整合

- 負責：Codex；狀態：verified（限 AWS Sydney 部署與合成 TLS→WSS 通路；CI 45974522232 及 Pages 已成功，公開登入入口已查核；RPi／BLE 尚未接入）。
- 已排除：CloudShell 失敗改官方 CLI 暫時登入；本帳號僅支援 ap-southeast-2，詳見 TEST-027／ISSUE-017。RPi 裝置憑證已產生，尚未傳至 RPi。
- 驗收：Free Plan 狀態核對、IoT／Cognito 部署、登入唯讀、RPi 發布與斷線恢復實測、0 元現金支出限制。

## HW-001 — 六個 XIAO 刷機與場地量測

- 負責：使用者接線／標記，Codex 執行刷機與查核。
- 狀態：in_progress；2026-11-27 A01–A04、T01、T02 六塊皆已刷機、Windows BLE 各別收到並成功解碼；RPi SSH／HTTP 仍 timeout，收包及校正／定位尚未完成（TEST-021–026，交接 HW-001-flashing.md）。
- 最新排程：使用者指定同時通電實驗待處理，先完成 AWS；不自動要求接線或開始實體收包。
- 2026-11-28 更新：使用者要求準備實測。已建立 docs/testing/physical-checklist.md、座標量測空表與只讀收包檢查器；目前舊位址 SSH／HTTP 逾時，待確認目前 IP 與通電。尚未開始六塊同收或定位。
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

## AG-004 — Gazebo 組員整合交接簡報

- 使用者指定 Antigravity 製作、Codex 驗收後交付；已由官方 CLI 自動交付 f7430b2；Codex 修訂後 TEST-028 通過，22 頁逐頁 QA 與 PowerPoint 匯出完成。此為交接教材完成，SIM-001 尚待組員資料。
- 範圍：22 頁繁體中文工程交接，含資料契約、時鐘／座標、RSSI 公式、可執行接入命令、真值評估、正常／異常測試、分工與交付清單。
- Antigravity 交付 slides JSON、操作指南與 handoff；Codex 逐項核對實作、執行必要命令、建立可編輯簡報並逐頁渲染驗收。
- 允許檔案見 queue/AG-004.json；禁止編造 Gazebo／實體／RPi 已串接。六塊同時通電實驗依使用者指示待辦。
- 2026-11-28 使用者回饋難理解，由 Codex 直接重寫同一份簡報：前 12 頁白話分工與開工、後 8 頁技術附錄。入口為 docs/handoffs/AG-004-start-here.md；原 22 頁工程版資料保留，未覆寫 Antigravity 原交付。新內容與版型保存為 AG-004-readable-*。

## HW-002 — RPi 同收與新版部署（2026-11-28）

- TEST-030：復連、原主機金鑰相符，60 秒六 ID 全收、66 批真實觀測。
- TEST-031：保留設定後部署 8aab2aa；重啟後全收，RPi 座標欄位／預覽可用，未保存示例值。
- 交接 docs/handoffs/HW-002-reception.md；位置、校正、斷電與 AWS physical 待驗。

## HW-003 — 量測與多距離校正

- 使用者已在網頁保存四 Anchor 與設備高度；RPi 高度 0.90 m 已套用，XY 真值分離。
- TEST-032：單點靜態未校正基準完成；TEST-033：第二點 (1.5,0,0.9) 已收；TEST-034 第三點 (2.3,3.7,0.78) 已收。A01 不合理參數被拒，第四點待到位，尚未套用 RSSI 校正。
- 不以訓練點重算精度當獨立改善；正式成功率需事先定義評估格點；T02 斷電仍待執行。

- HW-003 最新：TEST-037 完整移動路徑 176 批觀測比較，候選 T01 有效位置 156→19，因此拒絕候選並只回退 RSSI 參數；保留實測座標、最新已知高度 0.60 m 與全部資料。TEST-038 同一巡查 T02 斷電／復電及盤點去重通過；TEST-039 Anchor 不足保護通過，復電結果見 HW-003／test-log 最新紀錄。整體定位精度仍待改善，RPi physical 上雲未完成。

## AG-005 — 四／六 Anchor 公平比較

- 負責：Antigravity，Codex 執行測試、審查與整合；交付6cbd3d4，審查見 reviews/2026-11-28-AG-005-codex.md（位於docs）。離線工具驗收完成，不代表六Anchor實機精度通過。
- 只可新增 scripts/compare-anchor-subsets.py、tests/test_anchor_comparison.py、docs/testing/six-anchor-experiment.md、docs/handoffs/AG-005-result.md；完整規格見 queue/AG-005.json。
- 相同原始資料、模型、濾波及冷啟動，只改 Anchor 子集；保留 Target 觀測。拒絕缺 A05／A06 的資料冒充六 Anchor，真值只供評估。
- 同時輸出各組有效數、MAE／RMSE／P50／P95，以及共同有效時間比較；正式成功率缺預定分母則未提供。合成測試不冒充實機改善。
- Codex 負責韌體 A06、刷機工具與 CI 擴充；兩塊硬體尚未刷入或量測，不修改目前 RPi 實測設定。演算法加權／重新校正另案，先取得四／六比較基準。
