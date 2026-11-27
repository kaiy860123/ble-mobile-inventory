# 問題與修正紀錄

狀態：待查／處理中／待驗證／已解決／暫緩。失敗嘗試也保留，避免重複走相同路徑。

## ISSUE-001 — 找不到指定需求訪談技能

- 發現日期：2026-11-26
- 類別：開發環境
- 狀態：已解決
- 症狀：使用者要求 grill-me-with-doc，但現有技能清單及本機搜尋未找到。
- 重現／證據：原技能目錄搜尋無對應項目；使用者後續提供 mattpocock/skills 儲存庫。
- 原因：所需外掛尚未安裝，且目前儲存庫技能名稱為 grill-with-docs。
- 修正：依儲存庫的 Codex 指引註冊 marketplace 並安裝 mattpocock-skills 1.3.2。
- 驗證：安裝回傳 pluginId、version、installedPath；其後成功讀取安裝的 SKILL.md 並開始訪談。
- 關聯：DEV-001。

## ISSUE-002 — 部分本機 PowerShell 查閱長時間未輸出

- 發現日期：2026-11-26
- 類別：開發工具執行環境
- 狀態：待查
- 症狀：部分唯讀命令回傳 session ID，數次等待仍無輸出；部分命令亦出現 InitializeDefaultDrives 訊息。
- 重現條件：本次工具執行環境中的部分 PowerShell 讀取／查閱命令；尚未建立穩定最小重現。
- 已知事實：相同類型讀取在其他呼叫或受允許的提升執行模式下可完成。
- 原因：未確認；不能將權限、Shell 啟動或 provider 訊息直接認定為根因。
- 已嘗試：停用 login profile、有限等待、必要時以已授權的唯讀方式查閱。
- 暫時處置：文件修改使用 apply_patch，僅在需要時執行範圍明確的查閱命令。
- 結果：可持續整理文件；尚未證實根本問題已修復。

## ISSUE-003 — Windows 中文紀錄讀取編碼不一致

- 日期：2026-11-26；狀態：已解決。
- 症狀：紀錄檔以 UTF-8 寫入，但測試使用 Windows 預設 cp950 讀取，出現 UnicodeDecodeError。
- 原因：測試漏寫 encoding；紀錄內容本身有效。
- 修正：所有文字紀錄讀取明確使用 UTF-8。
- 驗證：原失敗測試及完整 Python 測試通過，見 TEST-002。

## ISSUE-004 — WGS84 底圖被 SVG 網格擋住

- 日期：2026-11-26；狀態：已解決。
- 症狀：點擊 WGS84 底圖後按鈕已選取，視覺仍顯示 Local 網格。
- 原因：SVG 的 hidden 屬性未像 HTML 元素一樣反映至顯示狀態；網格仍占據容器。
- 修正：以 SVG style.display 明確切換。
- 驗證：瀏覽器複驗，實際出現 OSM 底圖及設備標記，無前端錯誤，見 TEST-004。

## ISSUE-005 — 合成移動資料的濾波延遲

- 日期：2026-11-26；狀態：已改善，待實體資料再調整。
- 發現：在相同 90 影格、相同雜訊種子與圓弧路徑下，median=5／alpha=0.4 的掃描器合成 RMSE 約 2.146 m，反映時間平滑造成的移動落後。
- 處置：範例設定改 median=3／alpha=0.65，保留可配置性。
- 驗證：掃描器合成 RMSE 約 1.106 m；T01／T02 約 0.802／0.349 m，見 TEST-005。
- 限制：這是數學觀測來源的比較，不是 Gazebo 或 BLE 實機精度保證。

## ISSUE-006 — ESP32 套件鏡像 DNS 失敗

- 日期：2026-11-26；狀態：已解決。
- 症狀：PlatformIO 的第一個下載鏡像解析失敗。
- 已知：官方套件管理器切換鏡像後完成下載，固定工具鏈不變。
- 處置：保留固定工具鏈，讓官方套件管理器嘗試其他鏡像，同時建立 Linux CI 編譯流程。
- 驗證：本機 Windows A01 編譯成功；Linux CI 的 A01–A04／T01–T02 六種韌體也編譯成功，見 TEST-006。仍未刷機。

## ISSUE-007 — AWS 部署環境尚未登入

- 日期：2026-11-26；狀態：阻塞雲端實際部署。
- 證據：本機沒有 AWS profile／credentials，preflight 明確停止；尚未建立雲端資源。
- 已完成：基礎建設模板、Free Plan 查核、裝置憑證與觀看者唯讀權限配置腳本。
- 後續：在使用者已登入的 CloudShell 或設定好的本機 AWS profile 執行；不要求把金鑰貼到聊天。

## ISSUE-008 — RPi SSH 部署前置條件

- 日期：2026-11-26；狀態：已解決。
- 起初使用者尚未設定，後續已提供位址與登入方式；成功確認主機、aarch64、Python 3.13 與藍牙服務。
- 改正：部署器加入隱藏密碼提示、既有主機金鑰驗證與傳輸 SHA-256 檢查；不保存登入密碼。
- 另修正：以 sudo 執行服務安裝器時，以 SUDO_USER 決定服務使用者，避免誤用 root 執行程式。
- 驗證：systemd 已啟用且 active/running，服務使用者正確；HTTP 200、BLE discovery active、畫面為 physical/ble，巡查操作可用。XIAO 刷機仍需實際連接與明確序列埠。

## ISSUE-009 — RPi 直接下載 ARM64 套件逾時

- 日期：2026-11-26；狀態：已解決。
- 症狀：在 RPi 下載 NumPy wheel 接近完成時發生 incomplete-download／timeout，安裝中斷。
- 原因：已確認為套件下載未完成；不能視為 ARM64 或程式不相容。
- 修正：在本機下載對應 aarch64／CPython 3.13 的 wheelhouse，SFTP 傳送並以 --no-index 離線安裝；保留獨立 venv。
- 工程改進：下載腳本列出 Linux 依賴，避免跨平台 pip 使用 Windows host marker 而誤選 WinRT；一般線上安裝增加 timeout／retries。
- 驗證：ARM64 wheelhouse 傳輸 checksum 相符、離線安裝完成、pip check 無相依性問題、服務與 HTTP API 啟動成功。

## ISSUE-010 — 沙箱 socket 與本次 RPi 更新

- 日期：2026-11-26；狀態：本機測試已解決，RPi 部署待網路恢復。
- 本機：一般沙箱 socket 連線回 10013，asyncio socketpair 初始化無法完成。以 faulthandler 確認卡在 socket.accept，停止等待，在授權的本機 socket 環境重跑，27 測試通過。
- Shell：本次 `cmd.exe` 搭配明確 UTF-8 可正常讀寫與建置，無須等待未輸出的 PowerShell 啟動。
- RPi：部署器在 SSH connect 逾時，未進入 SFTP；與先前已成功部署的版本區分。尚未確認是 RPi 關機、IP 更換或網路隔離，不將推測當根因。
- 後續：RPi 重新可達後部署已打包新版並驗證實際網頁，見 TEST-012。

## ISSUE-011 — 審查只監看主區，漏掉 Antigravity 真實 checkout

- 日期：2026-11-26；狀態：已修正來源與派工流程。
- 原因：Antigravity 依舊啟動文件另 clone，在本機分支提交 AG-002；主區指紋 unchanged 無法推論另一 checkout 沒有成果。
- 修正：註冊實際外部來源、直接讀本機分支／ready handoff、官方 CLI 任務佇列、heartbeat 同時檢查外部交付及主區差異。使用者不再代貼或手動推送。
- 證據：TEST-015，官方登入 probe 成功，AG-002 直接匯入，AG-001 真實派工已啟動。
- 限制：仍以實際 job／diff／測試確認成功，CLI 被 soft-deny 或工作中不當作已驗收。

## ISSUE-012 — 合法可選 null 觀測造成 TypeError

- 日期：2026-11-26；狀態：已修正並回歸。
- 來源：Antigravity F-06，Codex 獨立重現；schema 允許 rssi_at_1m_dbm=null，但 engine 將 None 傳入數學函式。
- 另查：scanner_height_m=null 也會在高度相減出錯。
- 修正：跳過 None 的參考 RSSI，沿用設備／封包／全域優先序；缺少或 null 掃描器高度採場地設定。保留正常數值的行為。
- 驗證：regression 原先 TypeError，修正後 engine 7 測試及當次完整回歸 40 測試通過，合成評估不變。

## ISSUE-013 — AG-001 發現之座標設定邊界與語意

- 狀態：四項均已修正；Codex 瀏覽器複驗與現場驗證仍依 TEST-017 限制追蹤。
- F1：舊預覽在編輯／預覽失敗後殘留，改為立即清空。
- F2：新 WGS84 原點曾自動寫 measured、既有 example 無法選擇變更；增加獨立來源欄位，新原點預設 example，保留自訂來源，避免混淆場地與原點量測狀態。
- F3：API 純空白轉換 ID／來源曾通過；後端拒絕 strip 後空值，兩個新增測試通過。
- F4：真正磁碟滿時錯誤清理可能蓋掉 507；close／aborted marker 改為最佳努力，新增雙重寫入失敗測試，原任務與設定保留。
- 證據：126 個非 browser 測試通過、build 成功，原交付與 Codex 審查紀錄完整保存。

## ISSUE-014 — Antigravity Windows headless 命令與 sandbox

- 症狀：CLI 曾回 SUCCESS 卻沒有檔案；後續只讀探測顯示命令被拒、相對 sandbox 路徑不被接受，修正路徑後 native 終端仍卡住並 timeout。
- 已完成：保留診斷，沒有全面跳過權限，沒有將無產出標為交付；已派工作狀態保持 blocked 可查。
- 採用修正：session 使用任務範圍的絕對 write_file 路徑並 deny command(*)；Antigravity 以內建檔案工具開發，Codex 使用既有可用的 cmd.exe／Python 工具執行測試與整合。
- 驗證：真實 CLI 檔案寫入探測成功；橋接器 12 案例通過。AG-003 已在保留成果與原分支的前提下接續，完整任務結果待交付。

## 新問題格式（範本）

```text
ISSUE-NNN — 標題
發現日期／修正日期：
類別／影響程度／狀態：
環境、硬體、程式與設定版本：
症狀與影響：
最小重現步驟／輸入 run_id：
預期與實際：
錯誤訊息與證據路徑：
原因（區分推測與已確認）：
嘗試一／結果：
嘗試二／結果：
採用修正與修改檔案：
驗證 TEST-NNN／證據：
剩餘限制／後續行動：
```

## ISSUE-015：實驗彙整證據狀態與任務混用

AG-003 審查發現頂層真值分離寫死 false、多 run_id 仍合併、CSV 忽略未實測延遲旗標。新增四個回歸先失敗，再修正為保留未知、拒絕混用任務、保留 latency_measured。21 個彙整測試通過，完整非 browser 149 通過；詳見同日 AG-003 審查。

## ISSUE-016：主機更新後虛擬環境失效與首次 XIAO 連線

- 原 .venv 指向已不存在的 Codex 舊版 Python runtime。以既有 Python 3.12.10 執行 `-m venv --upgrade --without-pip .venv` 修復，保留已安裝套件；PlatformIO 6.2.0 可執行。
- 首次 esptool stub 在 chip 辨識後回報無法驗證 Flash 連線；以 115200 baud、--no-stub flash_id 成功讀出 4 MB，再正常刷入 A01，所有段雜湊通過；尚不能斷言首次失敗根因。
- 同日 RPi SSH／HTTP 仍未連通，列為整合待恢復，不影響已完成的 A01 刷機與 Windows BLE 廣播接收。

## ISSUE-017：AWS 部署登入、區域及 WSS 簽章

- CloudShell 實際回報帳戶驗證進行中；官方 CLI 2.42.4 瀏覽器暫時登入可用，無須建立長期 access key。原 MSI 管理解壓等待未完成已停止，改從官方 MSI 內嵌 CAB 本地解出 CLI，沒有進行系統全域安裝。
- 新式 AWS 專案僅支援 ap-southeast-2；Tokyo 登入顯示 region_not_supported，改 Sydney 成功。SDK 登入需要 CRT，補安裝並在 dev 依賴加入 boto3[crt]。
- 初次真實 WSS 測試反覆斷線。依 AWS IoT 官方規則，將 STS session token 從 canonical query 移除，在簽章後加入；產品 CloudSession／CloudPublisher 實際端到端通過，觀看者發布後斷線符合唯讀限制。新增可重現簽章 regression，npm test 3 passed。
- 六塊同時通電實驗依最新指示保留待辦，未測不代填。

## ISSUE-018：AG-004 交接操作條件與簡報版面

- 發現送出器接 curl 序號重置衝突、Anchor TTL 等待條件缺漏、Gazebo 設定啟動路徑與前端建置缺漏，以及 export/ws 權限說明過度概括。
- Codex 依現有實作修訂手冊／簡報並以本地 HTTP、合成評估與彙整命令驗證；TEST-028 通過。未修改定位核心。
- 初次流程圖 Pages 標籤溢出，已精簡方塊文字、重排連線並重新渲染確認；22 頁逐頁看過，完整來源與限制見 docs/reviews/2026-11-27-AG-004.md。
