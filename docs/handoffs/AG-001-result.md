# AG-001 任務交接結果

- 任務 ID／標題：AG-001 — 本地座標設定獨立驗收
- 交付者／審查者：Antigravity ／ Codex
- 狀態：ready_for_review
- 基準 commit：`28d61d6dd4e82002d53e17a4119c54aba061c679`（含先前 AG-002 交付，完整保留）
- 工作分支／交付 commit：`antigravity/AG-001-settings-review`（依派工要求僅於工作區新增允許檔案，未執行 `git add`/`commit`/`push`）

## 需求與驗收

- 對應需求：R25、R09、R15、`docs/design/site-settings.md`、`docs/collaboration/tasks.md`（AG-001）、`docs/collaboration/test-matrix.md`。
- 驗收要點：
  1. Local 座標與場地參數保存、重新載入及模擬重啟，保留 `cloud` 私密設定與 RF 模型參數，舊任務 `manifest.json`／觀測紀錄保留且切換新 `run_id`。
  2. WGS84 含旋轉角（多角度與 90° 方向約定、混合 Local／WGS84 Anchor、停用地理參考不捏造經緯度），以獨立於 `ble_inventory.coordinates` 之 WGS84 ECEF／ENU 公式核對。
  3. 欄位空白／型別錯誤／布林／`NaN`／`±Infinity`／格式錯誤 JSON／越界／未授權欄位／Target 平面位置注入全面拒絕且不改檔。
  4. Anchor 共線（水平、垂直、對角、重合、病態條件數 `> 100`、WGS84 共線）拒絕；合法細長矩形（條件數 `< 100`）放行。
  5. 過期 revision、雙頁面循序／並發（`asyncio.gather`）衝突、磁碟外部修改與外部設備名單變更均回 409 且不覆寫檔案或切換任務。
  6. 取消（按鈕與 `Escape` 鍵）與預覽均不寫入設定檔、不產生備份、不建立新任務目錄。
  7. 保存失敗（含原子替換 `os.replace` 中途 `OSError` 回 507 及驗證失敗回 400）維持原設定與原 `run_id`，清理暫存 `.site-*` 檔、標記 `aborted.txt`，原任務可繼續接收觀測。
  8. 公開端（回放／AWS 觀看模式）與無 `config_path` 服務唯讀，且所有設定端點皆強制 `X-Control-Token` 與同源 `Origin` 驗證。
  9. 區分 API 驗證與真實瀏覽器 UI 驗證，不以 API 結果推論 UI／手機通過；實機／未建置 bundle／實體手機未測項目明確列出原因。

## 允許修改範圍與實際修改檔案

- 允許修改範圍：
  - 允許檔案：`tests/test_settings_independent.py`、`docs/handoffs/AG-001-result.md`
  - 允許前綴：`tests/browser/`
- 實際新增／修改檔案（嚴格限於允許範圍；核心 `src/`、既有前端 `web/`、既有測試及 AG-002 交付均維持只讀未動）：
  - `tests/test_settings_independent.py`（新增 80 項獨立 Python／數值／API／交易／權限驗收測試）
  - `tests/browser/test_site_settings_browser.py`（新增真實無頭 Chromium CDP 瀏覽器端到端 UI 測試，覆蓋 B1–B8 共 8 個情境，直接載入未修改之 `web/site-settings.js`、`web/style.css`、`web/overrides.css` 對接真實 `create_app`）
  - `docs/handoffs/AG-001-result.md`（本交接報告）
- 介面或資料格式影響：無（僅新增獨立測試與交接文件；未修改任何應用程式碼、API、schema 或設定檔）。

## 測試環境／版本

- 作業系統：Windows（獨立 checkout 目錄 `C:\Users\user\.gemini\antigravity\scratch\ble-mobile-inventory`）
- Git 狀態：分支 `antigravity/AG-001-settings-review`，基準 SHA `28d61d6dd4e82002d53e17a4119c54aba061c679`
- Python：`3.12.14`（`D:\1_Kevin個人\115年台大在職專班\1_就學\115-1\物聯網導論 (COMME5047)\專題\.venv\Scripts\python.exe`），`pytest 9.2.0`
- 受測模組路徑確認：`ble_inventory.__file__` = `C:\Users\user\.gemini\antigravity\scratch\ble-mobile-inventory\src\ble_inventory\__init__.py`（確認指向目前 checkout/src，未誤測其他工作區）
- Node.js：`v22.23.2`（`tests/web.test.mjs` 執行用；本 checkout 無 `node_modules/` 與 `web/dist/`）
- 本機真實瀏覽器：Google Chrome `157.0.8103.80`（無頭模式 `--headless=new` + CDP）；另確認本機亦有 Edge `158.0.4370.33`
- 沙箱備註：一般 Windows 沙箱阻擋本機 loopback socketpair（`ISSUE-010` 同現象，致使 `asyncio`/`aiohttp.test_utils.TestServer` 測試卡住）；Node 單元測試與只讀檢查於標準沙箱完成，需本機 loopback socket 與無頭 Chrome CDP 的 `pytest` 於授權執行環境完成。

## 執行命令

```powershell
# 1. 基準版本與工作樹狀態確認（標準沙箱）
git status --short --branch
git rev-parse HEAD

# 2. 既有前端資料測試（標準沙箱）
node --test tests/web.test.mjs

# 3. 確認受測套件路徑並執行全部 108 項 Python（既有 27 + 獨立 80 + 真實瀏覽器 1 整合函式含 B1–B8）
$py = 'D:\1_Kevin個人\115年台大在職專班\1_就學\115-1\物聯網導論 (COMME5047)\專題\.venv\Scripts\python.exe'
$env:PYTHONPATH = (Resolve-Path 'src').Path
& $py -X utf8 -c "import ble_inventory; print('ble_inventory.__file__:', ble_inventory.__file__)"
& $py -X utf8 -m pytest -v

# 4. 邊界發現 F3 最小重現檢查
& $py -X utf8 -c "from ble_inventory.config import load_config; from ble_inventory.site_settings import editable_view, prepare_edit; cfg = load_config('config/site.example.json'); s = editable_view(cfg); [a.pop('computed_wgs84', None) for a in s['anchors']]; s['georeference'] = {'latitude_deg': 25.0, 'longitude_deg': 121.5, 'height_m': 0.0, 'rotation_deg': 0.0, 'transform_id': '   ', 'source': '   '}; c, _ = prepare_edit(cfg, s); print('F3_repro:', repr(c['georeference']['transform_id']), repr(c['georeference']['source']))"
```

## 逐項預期／實際結果

| 驗收項目 | 驗證層級 | 預期結果 | 實際結果 | 狀態 | 對應測試／證據 |
| --- | --- | --- | --- | --- | --- |
| 1. Local 保存與重載（含重啟、私密欄位、舊任務隔離） | API／檔案＋真實瀏覽器 UI | 保存後新 `run_id` 啟動、Target 計數重設、`GET /api/settings` 與重啟後皆載入新值；`cloud` 憑證路徑與 RF 參數保留；舊任務 `manifest.json`／觀測保留；備份位元組與原檔一致；停用地理參考不捏造經緯度；範圍外 Anchor 與示例狀態給警示不擋存 | 全部符合：`test_local_save_reload_restart_preserves_private_and_old_run`、`test_out_of_bounds_anchor_and_example_status_produce_warnings_without_rejecting`、`test_disable_georeference_and_switch_back_to_local_does_not_fabricate_wgs84` 與瀏覽器 B1（桌面編輯→預覽→改值重新鎖定保存→再預覽→保存→重開表單重載）全數通過 | 通過 | `tests/test_settings_independent.py`、`tests/browser/test_site_settings_browser.py`（B1） |
| 2. WGS84 含旋轉角 | 獨立數學＋API＋真實瀏覽器 UI | 以獨立 WGS84 ECEF／ENU 轉換驗算 `0°/25°/37°/90°/-90°/-135°/180°` 旋轉與高程，Local 誤差 `< 1e-5 m`、經緯度 `< 1e-9°`；`90°` 時正北→`+X`、正西→`+Y`；混合 Local／WGS84 Anchor 正常保存重載；無原點時拒收 WGS84 Anchor | 7 組旋轉角、90° 方向檢核、混合 Anchor 與瀏覽器 B2（UI 啟用 37° 旋轉原點、A01 切換 WGS84 輸入、預覽顯示正確 Local/WGS84、保存並重載）全數通過；另發現一項 `georeference.source` 與 `configuration_status` 聯動 UX 差異（見 F2） | 通過（附非阻塞 UX 觀察 F2） | `tests/test_settings_independent.py`（9 例）、`tests/browser/test_site_settings_browser.py`（B2） |
| 3. 空白／NaN／越界／非法欄位 | 單元＋HTTP 原始封包＋真實瀏覽器 UI | 空白、`None`、布林、`NaN`、`±Infinity`、原始 JSON 字面 `NaN`/`Infinity`、壞 JSON、倒置／超限 `bounds_m`、超限高度／經緯度／旋轉角、Target 注入平面座標、修改 ID、未授權欄位全數回 400 且不寫檔 | 53 組參數化非法輸入 + 原始 HTTP `NaN`/`Infinity`/壞 JSON + 瀏覽器 B3（空值、`NaN`、`1e309` 被表單阻擋，`2000000` 越界回報「允許範圍內」，保存鈕維持停用）全數通過；另確認直接 API 傳純空白 `transform_id`/`source` 未被拒（見 F3） | 通過（附邊界發現 F3） | `tests/test_settings_independent.py`（54 例）、`tests/browser/test_site_settings_browser.py`（B3） |
| 4. Anchor 共線與退化幾何 | 單元＋真實瀏覽器 UI | 水平／垂直／對角共線、四點重合、條件數 200（`> 100`）、WGS84 共線全數拒絕並回報「共線或幾何條件不良」；條件數 10 之有效細長矩形允許通過 | 全部符合：5 組 Local 退化案例、1 組 WGS84 共線＋有效矩形案例與瀏覽器 B3 共線預覽報錯全數通過；另記錄重預覽失敗時舊 `#site-preview` 文字未清除之 UX 觀察（見 F1） | 通過（附 UX 觀察 F1） | `tests/test_settings_independent.py`（6 例）、`tests/browser/test_site_settings_browser.py`（B3） |
| 5. 過期 revision | API 交易 | 錯誤／空字串／`None` 之 `expected_revision` 及外部修改設定檔或外部更改設備名單皆回 409，不改檔、不建備份、不切 `run_id` | 全部符合：`test_stale_revision_and_two_page_sequential_conflict` 與 `test_external_disk_edit_and_roster_change_return_409` 全數通過 | 通過 | `tests/test_settings_independent.py` |
| 6. 雙頁面衝突 | API（循序＋並發）＋真實雙分頁瀏覽器 UI | 兩頁載入同 revision，頁 A 保存成功後，頁 B 保存回 409 且不覆蓋頁 A；同時並發送出時僅一筆 200、另一筆 409；瀏覽器頁 B 保留開啟、顯示「設定版本已變更…」錯誤、停用保存鈕、不切狀態，按「重新載入」取回頁 A 修改後可合併保存 | 全部符合：API 循序與 `asyncio.gather` 並發測試及瀏覽器 B5（Chrome 實際開啟兩個分頁同步編輯衝突→409 UI→重新載入→合併保存）全數通過 | 通過 | `tests/test_settings_independent.py`、`tests/browser/test_site_settings_browser.py`（B5） |
| 7. 取消與預覽不寫檔 | API 檔案樹比對＋真實瀏覽器 UI | 開啟／取消按鈕／`Escape` 鍵與多次合法／非法預覽均不修改設定檔、不殘留 `.site-*` 暫存檔、不建立備份或新任務目錄、不切換 `run_id` | 全部符合：`test_preview_and_read_only_open_never_modify_filesystem_or_run` 與瀏覽器 B1/B4（預覽不寫檔、取消按鈕與 CDP 實體 `Escape` 鍵關閉不寫檔）全數通過 | 通過 | `tests/test_settings_independent.py`、`tests/browser/test_site_settings_browser.py`（B1、B4） |
| 8. 保存失敗不切換 | API（`os.replace` 失敗／驗證失敗）＋真實瀏覽器 UI | 寫檔／原子替換 `OSError` 回 507，原設定檔不變、清除 `.site-*` 暫存檔、標記 `aborted.txt`、維持原 `run_id` 且原任務可續收觀測；瀏覽器端對話框不關閉、顯示「原設定繼續使用」、停用保存鈕、不觸發 `onState` | 全部符合：`test_save_failure_mid_atomic_replace_preserves_old_run_and_cleans_tempfiles`、`test_save_validation_failure_does_not_switch_run_or_create_backup` 與瀏覽器 B6 全數通過；另記錄真實磁碟滿載時 `finally` 寫 `aborted.txt` 風險（見 F4） | 通過（附邊界觀察 F4） | `tests/test_settings_independent.py`、`tests/browser/test_site_settings_browser.py`（B6） |
| 9. 公開端唯讀與權限邊界 | API＋靜態模板＋真實瀏覽器 UI | 缺／錯 `X-Control-Token` 或跨源 `Origin`（含 `https://kaiy860123.github.io`）對三個設定端點皆回 403；無 `config_path` 啟動回 404 且 `settings_editable=false`；超出 `root/config` 路徑拒絕啟動；公開頁（`replay`／`cloud` 模式）停用按鈕與提示，即使手動移除 `disabled` 亦被前端阻擋；AWS 觀看策略無寫入／發布權限 | 全部符合：`test_settings_endpoints_enforce_token_origin_and_config_path_boundary`、`test_public_static_html_starts_settings_disabled_and_aws_template_has_no_write_policy` 與瀏覽器 B7 全數通過 | 通過 | `tests/test_settings_independent.py`、`tests/browser/test_site_settings_browser.py`（B7） |
| 10. 手機版面與鍵盤操作（模擬環境） | 真實無頭 Chrome（CDP 行動視埠 `390×844` + 鍵盤事件） | `390×844` 下對話框寬度不超視埠、無明顯水平溢出（`overflowX <= 2`）、動作按鈕高度 `>= 32px` 且不超右側；`Tab` 可移動焦點；未預覽按 `Enter` 不誤存；`Escape` 關閉對話框；全流程無未捕捉 JS 例外 | 全部符合：瀏覽器 B8 於 Chrome `157.0.8103.80` CDP `Emulation.setDeviceMetricsOverride(390, 844, 3, mobile=True)` 與 `Input.dispatchKeyEvent(Tab/Enter/Escape)` 通過，`exceptions == []` | 模擬視埠通過（實體手機列未測） | `tests/browser/test_site_settings_browser.py`（B8） |

## 證據摘要

- `pytest -v`（全部測試）：**`108 passed in 5.50s`**（既有 27 + `tests/test_settings_independent.py` 80 + `tests/browser/test_site_settings_browser.py` 1 支涵蓋 B1–B8 端到端流程；0 failed、0 skipped、0 warnings）。
- `node --test tests/web.test.mjs`：**`2 pass, 0 fail`**（90.3 ms）。
- 確認無越權修改：`git status --short --branch` 僅顯示 `tests/test_settings_independent.py`、`tests/browser/` 與 `docs/handoffs/AG-001-result.md`；`git diff --stat` 對既有檔案為空，AG-002 交付完整保留。

## 未執行項目及原因

以下項目無法於本任務環境執行或超出 AG-001 唯讀範圍，**不以 API 或無頭模擬測試推論其已通過**：

1. **完整建置後 `web/dist/assets/main.js`（含 Leaflet 地圖與 `web/main.js` 全頁掛接）之瀏覽器測試**：
   - 原因：目前 checkout 未包含 `node_modules/` 與 `web/dist/`，且 AG-001 限制不得修改既有前端或進行套件／部署變動。因此 `tests/browser/test_site_settings_browser.py` 係以輕量同源測試頁掛接未修改之 `web/site-settings.js`、`web/style.css`、`web/overrides.css` 對接真實 `create_app()`；未覆蓋 `web/main.js` 內 `setInterval(500)` 輪詢 `updateAvailability()` 與 Leaflet 底圖切換之整合路徑。
2. **實體手機觸控與行動瀏覽器實測（iOS Safari／Android Chrome）**：
   - 原因：本自動化執行環境無連接實體手機，僅以桌面 Chrome `157.0.8103.80` CDP `Emulation.setDeviceMetricsOverride(390×844, DPR=3, mobile=True)` 驗證 RWD 版面、按鈕尺寸與鍵盤事件；未實測實體手機虛擬鍵盤彈出、小數點／負號輸入法行為與觸控捲動。
3. **RPi 4B 新版實機服務與線上 GitHub Pages／AWS 登入後端點驗證**：
   - 原因：RPi 新版部署仍因 SSH 逾時待辦（`ISSUE-010`）、AWS 實際部署阻塞（`CDX-CLOUD`），且本次派工明令禁止變更 RPi／AWS／帳號設定。
4. **螢幕報讀器（NVDA／VoiceOver）完整無障礙實測**：
   - 原因：僅檢查對話框鍵盤 `Tab`/`Enter`/`Escape` 與既有 `role="alert"`／`aria-live="polite"` 行為，未執行輔助科技朗讀驗證。

## 問題重現與發現（依範圍未修改核心／既有前端，提交 Codex 評估）

本次未發現會導致資料損毀、越權寫入或任務誤切換的阻斷性缺陷；另發現 4 項低～中風險邊界與 UX 問題供 Codex 審查決定是否修補：

1. **AG001-F1（UX，低）— 預覽失敗後未清除舊預覽結果**：
   - 位置：`web/site-settings.js:58-66`。
   - 重現：先輸入合法座標並點擊「計算預覽」（`#site-preview` 顯示座標），再將 Anchor 改為共線後再按「計算預覽」；此時 `#site-error` 正確顯示錯誤且 `#site-save` 正確停用（不會誤存），但 `#site-preview` 仍保留上一次的舊預覽文字，易造成操作者混淆。
   - 建議：在 `input`/`change` 事件或 `run()` 進入預覽失敗的 `catch` 時清空 `#site-preview`。
2. **AG001-F2（產品語意／UX，中低）— `georeference.source` 與 `configuration_status` 無法由 UI 同步**：
   - 位置：`web/site-settings.js:49`（`source:original.georeference?.source??'measured'`）與 `web/main.js:29`。
   - 現象：
     - 當設定原本無 `georeference` 且 `configuration_status === "example"`，使用者於 UI 啟用地理對準後，前端會固定寫入 `georeference.source = "measured"`，導致主畫面顯示「已地理對準」而不顯示「範例原點」。
     - 反之若原設定檔 `georeference.source === "example"`，使用者完成場地量測並將 `configuration_status` 改為 `measured` 後，UI 並無欄位可將 `georeference.source` 改回 `"measured"`，主畫面將持續顯示「範例原點」。
   - 建議：評估將 `georeference.source` 改為與 `configuration_status` 連動，或在表單提供明確選擇。
3. **AG001-F3（輸入驗證邊界，低）— 後端 API 接受純空白之 `georeference.transform_id` 與 `source`**：
   - 位置：`src/ble_inventory/site_settings.py:68-70`（僅檢查 `1 <= len(geo[k]) <= 64`，未檢查 `.strip()`）。
   - 重現：已實測以直接呼叫 `prepare_edit` 傳入 `transform_id="   "`、`source="   "` 通過驗證（輸出 `F3_repro: '   ' '   '`）。UI 端因有 `.trim()` 會轉成空字串而被攔下，但直接 API 呼叫可寫入純空白字串。
   - 建議：檢查 `geo[k].strip()` 非空或套用與 `frame_id` 一致之字元白名單。
4. **AG001-F4（錯誤處理邊界，低）— 真實磁碟空間耗盡時 `aborted.txt` 寫入可能將 507 蓋成 500**：
   - 位置：`src/ble_inventory/server.py:102-105`（`finally:` 區塊中 `(prepared.raw / "aborted.txt").write_text(...)` 未包 `contextlib.suppress(OSError)`）。
   - 現象：模擬 `persist_edit` 拋出 `OSError` 時因磁碟仍有空間，可順利寫出 `aborted.txt` 並回傳 HTTP 507；但若實體 RPi SD 卡真實空間耗盡，該行 `write_text` 亦可能拋出 `OSError`，導致客戶端收到 500 而非預期之 507 訊息。
   - 建議：於 `server.py:104-105` 加上 `with contextlib.suppress(OSError):` 保護 `prepared.close()` 與 `aborted.txt` 寫入。

## 剩餘限制／阻塞

- 實體手機實測、完整 `web/dist` bundle 整合測試、RPi 4B 新版實機部署與公開 GitHub Pages／AWS 實測均待對應環境就緒後補測（詳見「未執行項目及原因」）。
- `tests/browser/test_site_settings_browser.py` 若於無安裝 Chrome／Edge／Chromium 的環境執行，會自動 `pytest.skip` 而不造成無瀏覽器 CI 失敗。

## 合併注意事項

- 本任務僅新增 `tests/test_settings_independent.py`、`tests/browser/test_site_settings_browser.py` 與 `docs/handoffs/AG-001-result.md`，與核心模組、既有前端及 AG-002 交付均無衝突。
- 若 Codex 於無頭 Linux CI 執行 `pytest`，請留意 `tests/browser/test_site_settings_browser.py` 在無瀏覽器環境會 skip；若 CI 已安裝 Chromium，該測試會自動執行並驗證 B1–B8。
- 若 Codex 採納 AG001-F1～F4 建議並修補核心／前端，可直接重跑本批 81 項新增測試（80 支 API／數值＋1 支瀏覽器端到端）作為回歸驗證。

## 部署與還原方式

- 不涉及 RPi、AWS 或 GitHub Pages 部署。
- 如需還原，僅需移除新增之 `tests/test_settings_independent.py`、`tests/browser/test_site_settings_browser.py` 與 `docs/handoffs/AG-001-result.md` 即可回到基準 `28d61d6dd4e82002d53e17a4119c54aba061c679`。

## 報告／進度需更新處

- 請 Codex 審查後依整合結果更新：
  - `docs/progress/state.json`（更新 `AG-001` 狀態與證據）並執行 `scripts/render-progress.py`。
  - `docs/test-log.md`（補記本次獨立驗證與瀏覽器驗證 TEST 條目）。
  - `docs/issues.md`（若採納 AG001-F1～F4 任一項目進行追蹤修補）。

## 下一個具體動作

1. Codex 審查 `tests/test_settings_independent.py`、`tests/browser/test_site_settings_browser.py` 與 `docs/handoffs/AG-001-result.md`，並在目標環境重跑確認。
2. Codex 決議是否修補 AG001-F1～F4，以及何時補跑完整 `web/dist` bundle、實體手機與 RPi 新版部署後驗收。

---

狀態標記：`ready_for_review`
