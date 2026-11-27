# HW-004：A05／A06 刷機與下次重排場地

日期：2026-11-28，基準0f5b8be76e9aa2bccf144ace7d7612ba89e9010e。使用者逐塊接線，Codex辨識、刷入及驗證；沒有改正式韌體程式或RSSI參數。

| ID | 晶片與Flash辨識 | 刷機 | Windows BLE掃描10秒 |
| --- | --- | --- | --- |
| A05 | 新晶片，與前六塊不同，ESP32-C3 v0.4／4MB | SUCCESS 6.512 s，四段雜湊均通過 | 4筆匹配觀測，RSSI −50至−46 dBm，payload 424901010500c50000 |
| A06 | 與前七塊不同，ESP32-C3 v0.4／4MB | SUCCESS 6.819 s，四段雜湊均通過 | 6筆匹配觀測，RSSI −49至−45 dBm，payload 424901010600c50000 |

PlatformIO6.2.0／espressif32 6.10.0／NimBLE2.3.6／esptool4.5.1，使用`scripts/flash-device.py <ID> --port <已核對埠>`。產品decode_advertisement確認Anchor角色及ordinal5／6，參考RSSI=−59。韌體SHA256、USB／BLE識別、chip probe、完整flash log及逐筆掃描保存在忽略的artifacts/a05-*與a06-*；原始硬體識別不公開。

初次探測嘗試`python -m esptool`因該venv未獨立安裝模組而停止，沒有刷入；改用既有PlatformIO固定工具包的esptool.py後成功（ISSUE-028）。BLE觀測事件數不是空中封包數、頻率或遺失率。

## 使用者最新安排

使用者表示「我要全部重新設定位置，下次進行測試」。因此本輪結束實體測試；不保存建議座標、不擴充目前RPi名單、不再要求接線／量測。先前A05約(0,3.8)、A06約(0,1.9)建議不作新配置，全部位置待使用者下次實測。舊場地與真值只供舊run重現，不套用到重排後資料。

本輪曾唯讀查核先前RPi位址，SSH／HTTP逾時；沒有登入或修改，不推斷其根因。下次再確認連線資訊即可，不為本輪重排安排重試。

八塊XIAO均完成各別刷機與Windows解碼，不等於八塊由RPi同時收到、六Anchor配置保存或精度通過。Target真值仍另存。下次提供新場地尺寸／障礙物、全部Anchor XYZ、Target高度與分離XY真值、RPi高度及驗證位置，依新配置開新run，保留舊資料。

設定介面只編輯既有設備的座標與高度，不允許新增／變更ID或角色。新增A05／A06名單需先由Codex核對設定、備份及原子更新後重啟；之後座標調整可用原設定交易。不得直接把新增ID送到現有API並假定會成功。

定位品質改善提案見[roadmap](../design/localization-quality-roadmap.md)，提案未部署，不把新公式當作已實作方法。
