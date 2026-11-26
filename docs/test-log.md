# 測試紀錄

所有結果以實際執行為準。已進行本地合成定位、座標數值、API、網頁與回放測試；尚未完成 BLE 實機精度、Gazebo 或 AWS 真實連線測試。

## TEST-001 — 專題文件與目錄檢查

- 日期：2026-11-26
- 類別：文件與檔案結構檢查
- 狀態：通過
- 範圍：確認規劃目錄與說明文件存在；Markdown 本地連結可解析；需求未把待答覆方案寫成已確認；原始檔維持原位。
- 預期：上述檢查均符合。
- 實際：以 Python 標準函式庫唯讀檢查 25 份 Markdown 文件及 16 個預期目錄；缺少目錄 0、失效本地 Markdown 連結 0。確認原始 PPTX 與構想文字檔仍存在；日期計算為 12/10、12/17、12/24。
- 語意核對：需求文件將完整網頁清單、公開即時架構與地理參考方式保留為待確認，未記為已完成。
- 執行環境：Codex 本機 bundled Python；一般沙箱呼叫等待未取得輸出後，以已授權的唯讀提升模式完成，退出碼 0。關聯 ISSUE-002。
- 證據：本次工具輸出為 `Markdown files: 25`、`Missing directories: []`、`Broken local Markdown links: []`、`Schedule: 2026-12-10 2026-12-17 2026-12-24`。
- 限制：不驗證任何應用程式功能。

## TEST-002 — Python 核心與 API

- 日期：2026-11-26；環境：Windows／Python 3.12。
- 命令：`.venv/Scripts/python.exe -m pytest -q`。
- 結果：18 passed。
- 範圍：獨立座標控制點、不同旋轉角往返、WGS84 輸入與衝突、精確兩階段合成定位、共線／Anchor 不足、真值拒收、重複／倒序拒收、去重計數與失聯、紀錄／CSV、API 權限與停止／新任務、拒絕付費方案及觀看者權限檢查。
- 初次結果：14 passed／1 failed；失敗為 cp950 測試讀取，已修正 ISSUE-003。後續因新增案例總數增加。
- 限制：外部 API 用本機測試伺服器；AWS 權限模板及 preflight 使用離線檢查，不代表已部署。

## TEST-003 — 前端資料與建置

- 命令：`npm test`、`npm run build`。
- 結果：2 個前端資料測試通過，正式靜態建置成功；套件安裝時 npm audit 顯示 0 vulnerabilities。
- 範圍：回放時序／混合任務拒收、CSV 公式防護、時間格式與 bundle 建置。
- 限制：npm audit 是安裝當下的套件資料庫結果。

## TEST-004 — 瀏覽器操作

- 本地：即時畫面、新任務、停止任務、切換回放、Local／WGS84 底圖。
- 回放第 70 秒：已盤點 2、目前可見 1，T02 保留最後有效位置與時間。
- 發現並修正 ISSUE-004；複驗底圖實際出現，瀏覽器 error／warn 紀錄為空。
- 證據：`artifacts/ui/`；桌面截圖已保存，手機版及公開部署檢查另補。
- 資料為合成示範，已在畫面標示。

## TEST-005 — 獨立真值評估（合成）

- 命令：`python scripts/evaluate-run.py web/public/demo.json tests/fixtures/truth.jsonl`。
- 真值與定位輸入分離；依 position_at 對齊，重複位置不重複計分。
- 90 影格固定種子；掃描器 RMSE 1.106 m，T01 0.802 m，T02 0.349 m；無時間無法對齊樣本。
- 證據：`artifacts/evaluation.json`，原濾波比較在 `artifacts/evaluation-baseline.json`。
- 限制：不得當成真實 BLE／Gazebo 的精度結果。

## TEST-006 — XIAO 編譯

- 命令：`python -m platformio run --project-dir firmware -e A01`。
- 狀態：GitHub Linux CI 已成功編譯 A01、A02、A03、A04、T01、T02。
- 證據：GitHub Actions workflow run `45777923193` conclusion=success。
- 本機 Windows A01 亦已編譯成功：RAM 23,636 bytes、應用程式 Flash 470,768 bytes。先前下載鏡像問題見 ISSUE-006。
- 未刷機，未測射頻廣播。

## TEST-007 — AWS 前置檢查

- 命令：`python scripts/aws-provision.py preflight`。
- 結果：按預期停止，原因為本機沒有 AWS 登入設定；未建立雲端資源。
- Free Plan 拒絕 Paid Plan 的邏輯另由 TEST-002 驗證。

## TEST-008 — RPi 部署套件

- 命令：`python scripts/package-project.py`。
- 結果：成功產生 `deliverables/ble-mobile-inventory.tar.gz`，包含建置網頁與 Python 程式，未包含裝置私鑰或實驗資料。
- 後續：已以另含 ARM64 wheelhouse 的套件成功安裝到 RPi，見 TEST-009／TEST-010。

## TEST-009 — RPi SSH 與套件傳輸

- 日期：2026-11-26；狀態：通過。
- SSH 主機金鑰驗證通過，確認 aarch64、Python 3.13.5、Debian 13，藍牙服務 active。
- SFTP 傳送套件後，遠端檔案 SHA-256 與本地相符。
- 密碼僅以隱藏輸入提示使用，未保存。

## TEST-010 — RPi 服務、數值與實體 BLE 啟動

- 日期：2026-11-26；環境：RPi 4B／aarch64／Python 3.13.5。
- 安裝：使用 ARM64 離線 wheelhouse，獨立 venv；`pip check` 回報 No broken requirements found。
- 服務：ble-inventory.service 為 enabled、active/running，以部署使用者執行。
- 藍牙：Powered=yes、Discovering=yes；API input_error 為空，source=physical、input_mode=ble。
- 網頁與 API：HTTP 200；瀏覽器驗證開始新巡查／結束巡查，任務 ID 正確更新。
- 原始資料：已產生並持續追加 observations.jsonl；每任務分開保存。
- ARM64 數值檢查：以獨立四點／已知距離求解，結果 (3.0000000000000004, 4.0)，符合預期 (3,4)。
- 證據：本地 `artifacts/deployment/rpi-verification.json`、`artifacts/ui/rpi-physical-dashboard.jpg`，不提交主機資訊或截圖到公開庫。
- 限制：尚無專題 Tag 廣播，目前 Target 數 0；場地座標與校正仍為範例。這不是兩階段 BLE 實機精度驗收，也尚未串接 AWS。

## TEST-011 — 座標設定交易與回歸

- 日期：2026-11-26；Windows／Python 3.12.14。
- 命令：`.venv/Scripts/python.exe -X utf8 -m pytest -q`、`npm test`、`npm run build`。
- 結果：27 Python 測試、2 前端資料測試通過，正式網頁建置成功。
- 新增覆蓋：WGS84 37° 旋轉往返、私密 cloud 欄位保留、NaN／範圍／共線／ID／Target 真值欄位拒絕、設定 API token／Origin、預覽不改檔／任務、磁碟失敗 507 保留原設定、正常保存／備份／新任務／舊 manifest、revision 衝突 409。
- 初次失敗：新增模組括號不配對，已修正後重跑完整測試。
- 環境限制：一般沙箱 Windows socket 回傳 10013，asyncio 建立 socketpair 時等待；停止該次測試，在允許本機 socket 的執行環境重跑，27 passed in 1.83s。此為執行環境限制，非 API 程式死鎖。
- 限制：未由此推論 BLE／Gazebo／AWS 實機整合通過。

## TEST-012 — 新版座標表單與部署嘗試

- 本機瀏覽器：127.0.0.1:8091，合成 demo；開啟座標表單、確認 Local／高度／地理參考欄位、計算預覽，再以原有示例值保存。
- 結果：預覽顯示四 Anchor 的 Local 座標與尚未實測警示；保存後顯示成功，run_id 改變、Target 計數重設；console error／warn 為空。
- 測試未將示例標成已量測；範例設定內容未變，僅保存格式變化已恢復原格式。
- 打包成功：80 檔案，未包含裝置私鑰或實驗資料。
- RPi 部署：SSH 連接逾時，尚未傳檔、未重啟，故 RPi 新版尚未部署；不能當作 RPi 新功能驗收。
- 限制：手機、跨頁衝突 UI、鍵盤完整走訪待 AG-001 獨立檢查；API 衝突／失敗已有 TEST-011。

## TEST-013 — 交付版本 CI、公開頁與進度互動

- 程式 SHA：`9225d6be262071ab8ad31d6fb1f8b76526a5b04e`。
- CI：GitHub Actions [45841081307](https://github.com/kaiy860123/ble-mobile-inventory/actions/runs/45841081307) completed／success；Linux 完成 Python／前端測試、建置與 Pages 發布。
- 公開網頁：實際載入新版合成回放，顯示「非 Gazebo／實機」，座標設定停用並提示需 RPi 本地模式。
- 文件：本地 Markdown 連結失效數 0。
- 進度：產生約 7 KB fragment，JavaScript 語法檢查通過；使用 UTF-8 的本機預覽選取 AG-002，細節正確切換至任務證據與下一步。
- 預覽環境修正：直接以無 charset 的一般 HTTP 預覽會誤判中文字元；改用 UTF-8 預覽包裝後互動正常。Codex fragment 本身維持原始 UTF-8，不加入完整網頁外殼。
- 限制：預覽驗證不等同已取得 Antigravity 的測試結果；RPi 新版／AWS／實機定位仍未完成。

## TEST-014 — 自動審查變更偵測

- 日期：2026-11-26；命令：`.venv/Scripts/python.exe -X utf8 -m pytest tests/test_collaboration_monitor.py -q`。
- 結果：5 passed in 0.06s；涵蓋新增／修改／刪除、至少 60 秒穩定、再次編輯重算、還原變更、重複去重、審查中變更不能 ack、忽略輸出與越界路徑拒絕。
- 排程：Codex heartbeat `ble-antigravity` 建立成功，status=ACTIVE、每 5 分鐘；view 回傳可檢視。
- 限制：5 個測試驗證偵測規則，不代表已完成另一工具交付審查；實際背景觸發以後續執行紀錄為準。

## TEST-015 — 官方 Antigravity CLI 與本機交接

- 官方安裝：查閱安裝腳本，使用其 SHA-512 驗證，安裝 agy 1.5.18；實際 --help 支援 print、JSON、timeout、sandbox 與 session settings。
- 最小無讀寫 probe：既有登入回傳 returncode=0、status=SUCCESS、response=BLE_BRIDGE_READY。
- 已實際辨識外部 checkout 的乾淨 AG-002 分支，fetch 至專用 ref；AG-001 已由腳本建立分支並啟動官方 CLI，未要求人工貼 prompt 或推送。
- 橋接器：最新 9 測試通過，涵蓋 ready 狀態、檔案白名單、指定儲存庫、重複派工、依賴／dirty workspace、session 權限範圍，以及驗收 receipt 不被舊 worker 狀態覆蓋。
- 限制：第一次真實工作仍需以其 handoff、diff 與獨立測試確認結果；CLI SUCCESS 不等於測試通過。帳號不支援 auto，首輪回落 default；後續採 session 範圍的測試命令與 accept-edits，保留原政策，不全面跳過權限。

## TEST-016 — AG-002 獨立審查與 null regression

- 完整交付 SHA：28d61d6dd4e82002d53e17a4119c54aba061c679；六份文件逐檔核對範圍、協定、流程與部署狀態，報告見 docs/reviews/2026-11-26-AG-002-codex.md。
- 先新增 regression 重現 null 參考 RSSI 造成的 TypeError；修正 RSSI／scanner_height_m 的可選 null fallback，engine 7 測試通過。
- 當次完整 Python 回歸 40 passed in 1.90s；後續增加 receipt 競爭案例，橋接器目標測試 9 passed。
- 重跑合成評估數值一致，Markdown 本地連結失效 0；未渲染 Mermaid，不宣稱版面驗收。

## 新測試格式（範本）

```text
TEST-NNN — 測試名稱
日期、操作者、環境／版本：
類型：文件／單元／整合／實體／模擬／回放／展示
對應需求／ISSUE：
前置條件與設定：
步驟／命令：
輸入資料 run_id：
預期結果：
實際結果與量測單位：
狀態：通過／失敗／阻塞／未執行
證據與輸出路徑：
修正與重測 TEST：
```
