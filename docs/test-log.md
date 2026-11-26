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
- 狀態：進行中，下載鏡像問題見 ISSUE-006；取得最終結果後更新。
- 未刷機，未測射頻廣播。

## TEST-007 — AWS 前置檢查

- 命令：`python scripts/aws-provision.py preflight`。
- 結果：按預期停止，原因為本機沒有 AWS 登入設定；未建立雲端資源。
- Free Plan 拒絕 Paid Plan 的邏輯另由 TEST-002 驗證。

## TEST-008 — RPi 部署套件

- 命令：`python scripts/package-project.py`。
- 結果：成功產生 `deliverables/ble-mobile-inventory.tar.gz`，包含建置網頁與 Python 程式，未包含裝置私鑰或實驗資料。
- 限制：RPi 尚未有 SSH，未將套件安裝到實機。

## 新測試格式

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
