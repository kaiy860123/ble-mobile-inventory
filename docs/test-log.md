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
- 橋接器：最新 10 測試通過，涵蓋 ready 狀態、檔案白名單、指定儲存庫、重複派工、依賴／dirty workspace、session 權限範圍，以及驗收 receipt 不被舊 worker 狀態覆蓋。
- 限制：第一次真實工作仍需以其 handoff、diff 與獨立測試確認結果；CLI SUCCESS 不等於測試通過。帳號不支援 auto，首輪回落 default；後續採 session 範圍的測試命令與 accept-edits，保留原政策，不全面跳過權限。

## TEST-016 — AG-002 獨立審查與 null regression

- 完整交付 SHA：28d61d6dd4e82002d53e17a4119c54aba061c679；六份文件逐檔核對範圍、協定、流程與部署狀態，報告見 docs/reviews/2026-11-26-AG-002-codex.md。
- 先新增 regression 重現 null 參考 RSSI 造成的 TypeError；修正 RSSI／scanner_height_m 的可選 null fallback，engine 7 測試通過。
- 當次完整 Python 回歸 40 passed in 1.90s；後續增加 receipt 競爭案例，橋接器目標測試 10 passed。
- 重跑合成評估數值一致，Markdown 本地連結失效 0；未渲染 Mermaid，不宣稱版面驗收。

## TEST-017 — 首輪自動交付 AG-001 與 Codex 獨立驗收

- 官方 CLI 實際完成，returncode=0、provider_status=SUCCESS；橋接器驗證 HEAD／範圍與 ready handoff 後提交三檔，交付 SHA `291f0d13c43fd9d589e9925f447168f8cc5b00eb`。
- Codex 直接 import，不需人工推送；閱讀獨立 API／數值測試後，實際重跑 80 passed in 0.98s。
- 修正四項發現後，命令 `python -m pytest -q --ignore=tests/browser`：126 passed in 2.35s；npm run build 成功。
- 新 regression：純空白 transform_id／source 拒絕、aborted.txt 因磁碟滿也失敗時仍回 507；UI 編輯／錯誤清空舊預覽、原點來源改為獨立明示欄位且新值預設 example。
- Browser：交付者回報其基準版實際 108 passed（含 B1–B8）；Codex 本機未執行該 CDP 腳本，閱讀後納入 CI 並補修正後斷言，不將提供者數字列為 Codex 重跑。
- 審查與 accept：docs/reviews/2026-11-26-AG-001-codex.md；兩項 accept 後已自動派送 AG-003。
- 限制：正式 bundle、實體手機、RPi 新版與 AWS 未由此驗收；CI browser 結果另查核。

## TEST-018 — Windows headless 限制與編輯階段分工

- AG-003 前兩次受阻均被橋接器檔案／handoff 檢查擋下，未將 CLI returncode=0／SUCCESS 當成完成。
- 只讀 command 探測查明：Windows 權限匹配需要 regex；sandbox 相對 write_file 路徑報 non-absolute；修正絕對路徑後命令本身仍因終端未輸出逾時。失敗紀錄保留於私密 artifacts。
- 採更窄分工：Antigravity 編輯檔案，Codex 執行所有命令與測試；不放寬或關閉 sandbox。
- 實際檔案探測：CLI 明確 deny command(*)，只 allow 一個忽略檔的絕對路徑，回傳 0、file_verified=true、stderr 0 bytes。
- 最新橋接器目標測試：12 passed，包含絕對路徑／越界拒絕與編輯 worker 不取得命令權限。
- 已保留原分支／HEAD／成果，依 bounded resume 接續 AG-003 第三次；其結果以後續實際交付判斷，不在此先標完成。

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

## TEST-019：自動派工整合最終回歸（2026-11-26）

- 命令：`.venv/Scripts/python.exe -X utf8 -m pytest -q --ignore=tests/browser`。
- 實際結果：128 passed in 2.38s；包含 80 個 Antigravity 獨立 API 案例及 12 個 bridge 測試。
- browser 測試未在本機執行；CLI 任務 AG-003 第三次以僅檔案工具模式執行中，尚無交付，不能列為通過。

- GitHub Actions 45855333250：verify-build 與 publish 均 success；遠端 pytest、npm test、build、封裝及 Pages 部署步驟通過。此處未取得 pytest 細項輸出，不額外宣稱 browser 案例數。

## TEST-020：AG-003 Codex 獨立驗證（2026-11-26）

- 原始交付 17 passed in 0.28s；四個 Codex regression 先 4 failed／17 passed，修正後 21 passed in 0.20s。
- 完整命令：`.venv/Scripts/python.exe -X utf8 -m pytest -q --ignore=tests/browser`，149 passed in 2.31s。
- CLI 範本、合成狀態／獨立真值實跑成功；有效樣本 90/85/65，RMSE 重現 1.106/0.802/0.349 m。沒有新實機資料。
- 完整 SHA、修正與版本欄位限制見 docs/reviews/2026-11-26-AG-003-codex.md。

## TEST-021：第一塊 XIAO A01 實體刷機與 BLE 驗證（2026-11-27）

- 唯一 ESP USB 序列埠 COM147；esptool 確認 ESP32-C3 revision v0.4、4 MB Flash。主機識別及韌體 SHA256 留在本地忽略的 artifacts/first-xiao-probe.json。
- 命令：`.venv/Scripts/python.exe -X utf8 scripts/flash-device.py A01 --port COM147`。PlatformIO 6.2.0、espressif32 6.10.0、NimBLE 2.3.6；實際 SUCCESS 22.744 s，四個 Flash 段雜湊驗證通過。
- Windows Bleak 實掃 10 秒，收到六筆 A01 專題 manufacturer 廣播，payload 424901010100c50000，以產品 decode_advertisement 解出 A01、reference RSSI=-59；接收 RSSI -45 至 -43 dBm。事件數非封包遺失率／發送頻率證據；-59 為預設值，尚未校正。
- RPi 既有位址的 SSH 與 HTTP 仍未連通；未完成 RPi 收包或定位驗證。只有一個 Anchor，不能驗證完整定位精度；其餘設備待接線。

## TEST-022：第二塊 XIAO A02 刷機與 BLE 驗證（2026-11-27）

- 唯一 ESP USB 設備 COM148，序號不同於 A01；esptool ROM 模式確認 ESP32-C3 revision v0.4、4 MB Flash。硬體識別與韌體 SHA256 留於忽略檔 artifacts/a02-hardware-probe.json。
- 命令：`.venv/Scripts/python.exe -X utf8 scripts/flash-device.py A02 --port COM148`；PlatformIO 6.2.0、espressif32 6.10.0、NimBLE 2.3.6，SUCCESS 49.917 s，四個 Flash 段雜湊驗證通過。
- Windows Bleak 實掃 10 秒，收到兩筆 A02 廣播；payload 424901010200c50000，產品解碼器確認 device_id=A02、預設 reference RSSI=-59；實收 RSSI -48 至 -47 dBm。事件數不作發送頻率／遺失率證據。
- 此次未重測 RPi 連線，未完成 RPi 收包、校正或定位精度驗證；沒有修改韌體程式。

## TEST-023：第三塊 XIAO A03 刷機與 BLE 驗證（2026-11-27）

- COM149 的唯一 ESP USB 晶片與 A01／A02 序號不同，esptool 確認 ESP32-C3 revision v0.4、4 MB Flash。識別與韌體 SHA256 保存在忽略檔 artifacts/a03-hardware-probe.json。
- 命令：`.venv/Scripts/python.exe -X utf8 scripts/flash-device.py A03 --port COM149`；PlatformIO 6.2.0、espressif32 6.10.0、NimBLE 2.3.6；SUCCESS 43.914 s，四個 Flash 段雜湊通過。
- Windows BLE 實掃 10 秒收到六筆 A03 廣播，payload 424901010300c50000，產品解碼器解出 A03、預設 reference RSSI=-59；實收 RSSI -59 至 -56 dBm。事件數不作封包遺失率或頻率證據。
- 未修改韌體程式，未重測 RPi 連線；RPi 收包、現場校正與定位仍待驗證。

## TEST-024：第四塊 XIAO A04 刷機與 BLE 驗證（2026-11-27）

- COM150 為不同於 A01–A03 的新設備；ESP32-C3 revision v0.4、4 MB Flash。硬體識別與韌體 SHA256 留於忽略檔 artifacts/a04-hardware-probe.json。
- 命令：`.venv/Scripts/python.exe -X utf8 scripts/flash-device.py A04 --port COM150`；PlatformIO 6.2.0、espressif32 6.10.0、NimBLE 2.3.6；SUCCESS 42.125 s，四個 Flash 段雜湊通過。
- Windows BLE 實掃 10 秒收到八筆 A04 廣播；payload 424901010400c50000，解碼為 A04、預設 reference RSSI=-59，實收 RSSI -59 至 -52 dBm；事件數非頻率／遺失率證據。
- A01–A04 皆已各別刷機及 Windows BLE 驗證；未重測 RPi 連線，未完成四 Anchor 同時收包、場地校正或定位精度驗證。

## TEST-025：第五塊 XIAO Target T01 刷機與 BLE 驗證（2026-11-27）

- COM151 為新晶片，序號與 A01–A04 不同；ESP32-C3 revision v0.4、4 MB Flash。硬體識別及韌體 SHA256 留於忽略檔 artifacts/t01-hardware-probe.json。
- 命令：`.venv/Scripts/python.exe -X utf8 scripts/flash-device.py T01 --port COM151`；PlatformIO 6.2.0、espressif32 6.10.0、NimBLE 2.3.6；SUCCESS 52.213 s，四個 Flash 段雜湊通過。
- Windows BLE 實掃 10 秒收到四筆 T01 廣播；payload 424901020100c50000，role=2、ordinal=1，產品解碼為 T01、預設 reference RSSI=-59；實收 RSSI -64 至 -60 dBm。事件數非頻率／遺失率證據。
- 尚未校正 RSSI，未重測 RPi 連線或完成 RPi 同時收包／定位驗證。

## TEST-026：第六塊 XIAO Target T02 刷機與 BLE 驗證（2026-11-27）

- COM152 為不同於前五塊的新晶片；ESP32-C3 revision v0.4、4 MB Flash。硬體識別與韌體 SHA256 留於忽略檔 artifacts/t02-hardware-probe.json。
- 命令：`.venv/Scripts/python.exe -X utf8 scripts/flash-device.py T02 --port COM152`；PlatformIO 6.2.0、espressif32 6.10.0、NimBLE 2.3.6；SUCCESS 43.617 s，四個 Flash 段雜湊通過。
- Windows BLE 實掃 10 秒收到四筆 T02 廣播；payload 424901020200c50000，role=2、ordinal=2，產品解碼為 T02、預設 reference RSSI=-59；實收 RSSI -61 至 -58 dBm。事件數非頻率／遺失率證據。
- 六塊皆完成各別刷機與 Windows BLE 解碼；沒有修改韌體程式。RPi SSH 與 HTTP 重查皆 timeout（本地證據 artifacts/rpi-network-check.json），尚未完成 RPi 同時收包、RSSI 校正或定位精度驗證。交接見 docs/handoffs/HW-001-flashing.md。

## TEST-027：AWS Sydney 實際部署與合成通路驗證（2026-11-27）

- CLI 2.42.4 官方瀏覽器暫時登入，SDK preflight 確認 ACTIVE FREE、到期 2027-05-15、當次額度 US$119.998896；CloudShell 帳戶驗證失敗及 Tokyo 區域不支援另見 ISSUE-017。
- 執行 aws-provision.py 的 preflight／deploy／device／viewer，實際區域 ap-southeast-2；CloudFormation stack 成功，建立 IoT、Cognito 與本專題限定權限。裝置私鑰與觀看密碼僅留 config/private，未寄信。
- 真實網路測試使用產品前端 web/cloud.js CloudSession，Cognito 登入及身分憑證 → MQTT WSS 訂閱；產品 CloudPublisher 使用裝置 TLS 發出 simulation 合成快照，觀看端收到 schema 1.0、六設備、獨立 aws-synthetic-smoke run_id。觀看者再嘗試發布同一 topic 後被 broker 斷線，符合唯讀規則。原始證據 artifacts/aws-cloud-smoke.json 忽略不公開。
- npm test：3 passed；npm run build：成功；完整非 browser Python：149 passed in 3.83s。沒有新 BLE／RPi 資料，不當作精度或延遲量測。本地沒有執行自製 CDP browser 腳本。

- 發布版本 ca01517e50afcadc7d76803e88d3a246cc9bb7ec；GitHub Actions 45974522232 的 verify-build／publish 均 success。CUA 查核公開 Pages：登入即時資料可開啟帳密表單；AWS 即時選項也要求登入，取消回到明確標示的合成回放；巡查與座標控制 disabled。沒有透過 CUA 輸入觀看者密碼，實際 Cognito／WSS 驗證使用上述產品 CloudSession 網路測試。

## TEST-028：Gazebo 組員交接簡報與範例驗收（2026-11-27）

- Antigravity 官方 CLI 交付 f7430b2e4c2fcf6e6e0a0c0f15f633b0aa2d067d；Codex 修訂操作前提及版面。
- Python 3.12.10：`artifacts/verify-ag004.py` 通過 22 頁結構／來源／JSON 範例／數值例、本地 API accepted／拒絕／停止／新巡查／空批與既有合成 fixture 的 evaluate／summary CLI。初次沙箱 HTTP 未完成已停止，正常工具審核後相同命令 1.21s 通過。
- `python -m pytest -q tests/test_antigravity_bridge.py`：12 passed in 0.08s。
- 合成評估 skipped_unmatched=0；90／85／65 個有效位置，RMSE 1.106／0.802／0.349 m，與既有基準一致；非新增 Gazebo 或 BLE 性能證據。
- 可編輯雲端簡報 22 頁逐頁原尺寸渲染檢查，修訂 4／9／15 頁再次檢查；6 個原生表格與 2 頁原生流程圖。PowerPoint 匯出儲存成功；桌面 PowerPoint 相容性未測。
- 詳細範圍與發現：docs/reviews/2026-11-27-AG-004.md。未進行 RPi、實體通電或新 AWS 部署。

## TEST-029：白話交接與實機測試準備（2026-11-28）

- Codex 直接重寫同一雲端簡報為 20 頁：12 頁白話分工與實作，8 頁技術附錄；原工程稿與 Antigravity 交付 SHA 保留。20 頁逐頁原尺寸渲染，修訂第 7 頁後再看；加入 MAE／RMSE 手算例，屬數學示例。
- 舊 RPi 位址唯讀 TCP 檢查：22／8080 均 TimeoutError，耗時 8.04s；證據 artifacts/rpi-preflight-20261128.json。沒有 SSH 登入、部署或硬體測試通過的證據。
- 新增 scripts/check-physical-readiness.py，僅輪詢本地 API，要求 physical／ble、active 且無 input_error，同一次 run_id，僅接受檢查開始後的 last_seen；不控制巡查，不推估遺失率或精度。
- Python 3.12.10；新增 6 案例檢查新觀測、舊快照、合成來源、錯模式、停止與輸入錯誤。`python -m pytest -q tests/test_hardware_readiness.py`：6 passed；最終 `python -m pytest -q --ignore=tests/browser`：155 passed in 3.51s。--help 可正常執行。
- 現場測試單與空白量測表已備妥；座標、校正、六設備同收、定位及 AWS physical 通路均待實測。未用單元測試替代硬體證據。
- 進度產生器僅支援四種狀態，首次以 ready_for_review 填入時 assertion 阻止輸出；改以 in_progress 並在範圍明示待閱讀回饋後重新產生成功，未擴充看板狀態。

## TEST-030：RPi 六設備真實 BLE 收包（2026-11-28）

- 新位址 SSH／HTTP 可達，原 Ed25519 key 相符；aarch64、Python 3.13.5、service running、藍牙 powered/discovering。
- 新巡查 20261127T172127Z_physical_2dd5d3，舊歷史保留。readiness --duration 60：59 次取樣，A01–A04／T01／T02 均有本輪新觀測，passed=true、missing=[]。
- 結束保存 67 幀回放、66 批 raw、manifest、states；Target 已盤點／可見各 2。觀測數／RSSI 見 HW-002，聚合觀測數不作封包頻率或遺失率證據。
- 座標 example、尚無校正或獨立真值，未評精度；T02 斷電仍待使用者實體操作確認。

## TEST-031：RPi 新版與座標介面（2026-11-28）

- 先下載本輪 raw／manifest／states 及設定，RPi 另備份程式、config、service，再部署 8aab2aa 與新建置 web/dist。上傳 SHA256 相符、site.local.json 位元組不變、服務重啟 active。
- 使用現有 CPython 3.13 aarch64 離線套件；本輪無核心修改，沿用先前 155 非 browser／CI 通過版本。
- 新任務 20261127T172421Z_physical_b7bbeb，重啟後 15 秒、15 次取樣仍全六 ID；physical／ble 正確。
- 設定 GET／preview 200，revision 不變。CUA 真實開啟 RPi 網頁：六設備接收、Target 2、定位資料不足；座標欄位與預覽可用，示例警示正確，取消返回未保存。
- 不包含量測、實測座標保存、精度或 AWS physical；cloud.enabled=false，未傳裝置憑證。

## TEST-032：實測高度保存與未校正靜態基準（2026-11-28）

- 讀取使用者已保存的 measured Anchor／Target 高度，將 RPi 1.20 m 改為本輪回報的 0.90 m；preview／save 成功，除 scanner_height_m 外設定不變，新 run_id 20261127T174653Z_physical_bd3ffe。RPi／Target XY 僅另存評估參考。
- 使用者確認位置不變且全通電後，再採約 45 秒，44 快照。排除確認時間窗外舊位置，evaluate-run.py 對分離的固定真值、position_at 去重，三設備各 43 有效位置，skipped_unmatched=0。
- RPi／T01／T02 的 MAE=1.332／1.196／1.887 m、RMSE=1.522／1.196／1.890 m；完整 P50／P95、真值來源與單點限制見 HW-003。尚未校正，未代表移動巡查精度。
- 初始彙整錯用實際取得快照數為預定分母，已保留初稿並移除分母、重新產生正式 summary，成功率為未提供；來源與誤差結果不變。修正的是本地採樣 helper，未改共用彙整器。

## TEST-033：第二已知位置校正採樣（2026-11-28）

- 使用者指定第二點 (1.5,0)、高度 0.9 m，採獨立巡查 35 秒，六設備均收到，每 ID 30–32 筆去重 RSSI 觀測；保存 samples／CSV／replay／manifest，結束此校正巡查，舊資料保留。
- 合併第一與第二點，依實際已知三維距離檢查跨度，六 ID 皆未達 log10 距離跨度 0.3；不強行擬合或套用參數。第三點待使用者到位。

## TEST-034：第三點採樣與校正參數拒絕（2026-11-28）

- 使用者指定第三點 (2.3,3.7)、高度 0.78 m。以設定交易只將 RPi 高度 0.90 改 0.78，其他配置不變，再用獨立巡查採 35 秒，六 ID 各 31–33 個去重 RSSI 觀測；完整資料保存。
- 合併三點，四 Anchor 距離跨度通過，T01=1.680／T02=1.970 仍不足；A01 診斷擬合 n=−0.155，不在 0.5–6 合理範圍。
- 實際執行既有 calibrate-rssi.py，以 A01 fitted path-loss exponent implausible 退出，未產生 candidate-three-points.json，未套用任何校正參數。此為預期資料品質保護，非將失敗當通過。
- 依實測不一致新增靠近 A01 的第四點採樣計畫；待使用者到位。T02 斷電測試與校正後保留點／移動驗證尚未執行。

## TEST-035：第四點模型與保留點同原始資料比較（2026-11-28）

- 第四點 (0.5,0)、高度 0.80 m，35 秒採樣：六 ID 各 19–33 筆。四點合併後各設備 125–139 筆，距離跨度及 n 範圍皆通過，候選模型產生成功。
- 原子備份／保存只更新每設備 P1m／n，normalize_config 通過，座標與 cloud 不變，服務重啟 active。後續保留點僅將已知高度改 0.60 m；模型固定，訓練 SHA256 不變。
- 保留點 (1.7,1.3,0.6)，新巡查 20261127T180754Z_physical_a69c49，45 快照；下載原始 observations，使用相同 45 批資料冷啟動重播原模型／候選。共同有效 RPi／T01／T02 位置數 45／29／25，RMSE 原模型 2.467／4.646／3.174 m、候選 2.745／0.893／3.027 m。
- 各模型有效樣本不同，全表與限制見 HW-003；原始資料未刪選以改善數字，保留點未加入訓練。結果混合，不宣稱整體校正改善或真實移動巡查通過。

## TEST-036：移動巡查錄製中斷（2026-11-28，未通過／待重測）

- 新開移動巡查 20261127T181107Z_physical_4a1206 後，使用者要求稍等並重新上電。HTTP timeout，錄製程序已退出；部分逐筆快照已落盤，另寫 interruption／manifest 明示 route_completed=false。
- 未取得路徑完成確認，不產生正式移動精度、RPi 路徑真值、T02 斷電或網路復原通過結論。停止後未再發硬體請求，等待使用者已上電／新 IP。

## TEST-037：完整移動比較、候選拒絕與回退（2026-11-28）

- 使用者重新上電後六 ID／候選持久保存及時鐘已查核，再開新巡查；使用者明確確認路徑完成。取得 172 快照、176 原始觀測批，run_id=20261127T181538Z_physical_b3a149。
- 執行本地 capture-motion-resilient.py、retrieve-and-compare-motion-02.py，以同原始資料冷啟動比較原模型／候選，XY 只進評估。共同有效 T01 19 筆 RMSE 3.656→1.874 m、T02 129 筆 2.683→2.473 m；但各自有效 T01 156→19、T02 156→132，不能只報較低條件誤差。
- 結論：候選不接受。rollback-rssi-model.py 以設定雜湊檢查、normalize_config、備份及原子保存，只還原 RSSI 覆寫參數；保留實測座標、最新 0.60 m 高度、cloud=false 及歷史。服務 active，六設備 API distance_m 與原參數逐項吻合。
- Python 3.12.10／NumPy 2.5.5 離線，RPi Python 3.13.5／NumPy 2.5.5。證據 measurements-20261128/motion-02 的 manifest、paired-comparison、quality-reasons 與 rollback。沒有移動 RPi 軌跡真值，不報該誤差；正式成功率、延遲未量測。

## TEST-038：T02 斷電／復電去重（2026-11-28，功能通過）

- 使用者明確確認 T02 切電及接回。watch-t02-off.py／watch-t02-on.py 讀取同一 physical 巡查 20261127T182101Z_physical_a26b2b，分別保存 56／26 快照。
- 斷電：T02 stale、不可見，其他五設備可見；可見 Target 2→1、已盤點保持 2，最後模型有效位置與時間保留。復電：收到更新 last_seen，六設備可見，Target 可見回 2、已盤點仍 2，連續三次檢查通過。
- artifacts/hardware/t02-off-01 與 t02-on-01 保存狀態與明確操作者事件。不是位置準確性、精確切電延遲或額外獨立路徑的證據。

## TEST-039：Anchor 不足與恢復（2026-11-28，功能通過）

- 使用者只斷開 A03、A04，watch-anchor-insufficient.py 在同一巡查保存 12 快照；只剩 A01／A02 新鮮，掃描器與兩 Target 均不足，position_at 連續不再更新。
- 兩 Target 持續可見，已盤點與可見數均為 2。沒有將舊位置當新有效位置；未放寬門檻。證據 artifacts/hardware/anchor-insufficient-01/result.json。
- 使用者確認 A03、A04 已上電，watch-anchor-recovery.py 保存 89 快照，末三次六 ID 新鮮、可見，盤點與可見 Target 仍 2。掃描器恢復 valid、新 position_at；末快照 T01 valid、T02 因 RSSI 殘差過大仍 insufficient，不宣稱全部 Target 有效定位恢復。證據 anchor-recovery-01/result.json；全程同一 run_id，服務保持 active。

## TEST-040：六 Anchor 協作派工與韌體準備（2026-11-28）

- 擴充 bridge 的 dispatch／delivery／import／accept 支援 AG-005；加入新任務交付偵測與依賴保護測試。`.venv/Scripts/python.exe -X utf8 -m pytest -q tests/test_antigravity_bridge.py`：13 passed；完整 `-m pytest -q --ignore=tests/browser`：156 passed，2.48 s。
- worker 原 AG-004 分支已 accepted 且 clean，保留舊分支後接到已審 e353b35，再 `scripts/antigravity-bridge.py run AG-005`。status 確認 branch=antigravity/AG-005-anchor-comparison、job=running；限制為指定四檔編輯，命令 deny 不變，這只證明已派工，不代表交付驗收。
- `.venv/Scripts/python.exe -X utf8 -m platformio run --project-dir firmware -e A05 -e A06`：兩環境成功，A05 50.881 s、A06 42.289 s；PlatformIO 6.2.0、espressif32 6.10.0、NimBLE 2.3.6。A06 RAM 23,636 bytes、Flash 470,770 bytes。
- `scripts/flash-device.py --help` 正確列出 A06；CI 編譯名單加入 A05／A06。尚未新增實體刷機、八設備接收或六 Anchor 精度證據；目前 RPi 設定及服務未改。

## TEST-041：AG-005 比較工具交付與整合驗收（2026-11-28）

- Antigravity官方CLI交付6cbd3d4ccb3eb5f9919bed41a22e5cd3725c18c2，四檔範圍及ready handoff吻合，原提交已匯入專用ref保留。先讀全部程式、測試與說明後執行：原交付比較測試10 passed。
- Codex新增硬連結輸出別名回歸：初次一般沙箱在建立link時WinError5，未重現產品問題；在本地允許硬連結的測試環境再次執行，確實因DID NOT RAISE ValueError失敗。加入samefile保護後比較測試11 passed（0.38 s），完整非browser167 passed（2.44 s）。原始資料未用來做覆寫測試，僅pytest臨時資料。
- 修正文件的A05／A06候選ID對應與無地理參考的方向用語，以及「共同有效樣本消除選擇偏差」過度宣稱；補廣播競爭效應及逐批新鮮度限制。參數、定位核心與實測設定未變更。
- 使用既有motion-02的176批physical四Anchor原始資料與獨立六Anchor測試設定，工具明確以缺A05/A06拒絕，沒有產生六Anchor實機結果。另產生12批獨立合成比較，標simulation、formal_success_rate=null，原始輸入雜湊與真值隔離可查；本地證據artifacts/ag005-validation/。
- CLI --help、git diff --check通過。另以25批無噪聲合成smoke驗證八設備與A05/A06封包解碼，本地證據artifacts/six-anchor-smoke.json；非physical或Gazebo結果。
- 準備提交fcd2d62的GitHub CI 46053421624（測試／網頁發布）與46053421571（八種XIAO韌體）均success。AG-005整合後發布結果另以最終提交CI查核，不將前一提交CI冒充新提交。
