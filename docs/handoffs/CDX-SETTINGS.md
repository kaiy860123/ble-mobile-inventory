# CDX-SETTINGS 交付摘要

- 日期：2026-11-26；負責：Codex。
- 版本：包含本交付文件與 `web/site-settings.js` 的 commit；接手者先執行 `git rev-parse HEAD` 回報完整 SHA，避免只用會移動的 main 名稱。
- 需求與契約：R25、`docs/design/site-settings.md`。
- 修改：Python 設定正規化、白名單設定 API／版本／備份／原子保存、本地座標編輯表單與主頁掛接；CLI 將啟動設定路徑傳入服務。
- 證據：TEST-011／TEST-012；27 Python、2 前端資料測試通過，build 成功；桌面預覽與保存後新巡查通過，console error／warn 空。
- 可重現：建立獨立 venv，安裝 `pip install -e .[dev]`，`npm ci`、`npm run build`、`python -m pytest -q`、`npm test`；`python -m ble_inventory.cli serve --mode demo` 開啟本機頁。
- 實驗隔離：請複製 example 為 `config/site.local.json`，啟動時指定 `--config config/site.local.json`，避免改動版本管理的範例。demo 是合成來源，非實機精度測試。
- 未驗證：手機、鍵盤完整操作、跨頁衝突的 UI、RPi 新版；API 的衝突／失敗已有測試。RPi 更新在 SSH connect 逾時，未傳檔，不影響舊版。
- AG-001：僅新增任務允許的獨立測試與交接結果；發現問題附最小重現，不直接修改核心／舊前端或部署。
- AG-002：可先獨立核對報告四圖及公式；公式勘誤附符號／單位／程式位置。

接收交付後，Codex 審查差異、重跑受影響案例，再更新進度／問題與報告。實機、Gazebo 與 AWS 未完成項目仍保留待驗證。
