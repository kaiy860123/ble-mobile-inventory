# 本地座標設定介面與交易契約

狀態：本次新增需求，實作與部署狀態以測試紀錄及進度資料為準。

## 使用者操作

- RPi 本地頁提供「座標設定」。Anchor 可用 Local X/Y/Z 公尺，或已有地理參考時輸入 WGS84。
- 可編輯場地範圍、掃描器／Target 固定高度、Local 框架名稱、WGS84 原點與旋轉角、設定是否已實測。
- Target 水平位置由定位器估計，此介面不提供其真值輸入。
- 先預覽轉換結果與配置，再「儲存並開始新巡查」。取消與預覽均不改檔。
- 新任務使用新設定；舊任務的 manifest、原始資料及位置結果保留，避免混合不同 Anchor 配置。
- 公開 GitHub Pages／AWS 觀看端維持唯讀。

## API

所有設定 API 沿用本地 `X-Control-Token` 與 Origin 驗證；不接受檔案路徑、雲端憑證或變更設備角色／ID。

- `GET /api/settings`：可編輯欄位及不透明 revision，不包含 cloud 或私密路徑。
- `POST /api/settings/preview`：`settings` 候選，回傳正規化座標與警示，不保存。
- `POST /api/settings`：`expected_revision`＋`settings`；版本衝突回 409，驗證錯誤 400，寫入失敗明確報錯。

可編輯欄位：`bounds_m`、`frame_id`、`scanner_height_m`、`georeference`、`configuration_status`、`anchors`、`targets`（僅固定高度）。

## 保存規則

1. 在記憶體合併白名單欄位，保留原設定的模型參數及 cloud 區塊。
2. 檢查有限數值、座標／範圍、原點及旋轉、完整 Anchor 名單與二維幾何；缺少地理參考不自動捏造經緯度。
3. 比對 revision，避免兩個瀏覽器頁面互相覆寫。
4. 同目錄暫存檔後原子替換，保留本地私密備份。路徑固定為啟動時指定的場地設定。
5. 成功後切換新任務；預覽、驗證失敗、衝突及保存失敗均維持原任務與生效設定。

實作必須有對應測試；未通過或未部署不得在報告宣稱已可用。
