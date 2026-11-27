# HW-001：六塊 XIAO 刷機階段交接

2026-11-28後續：新增A05／A06已完成刷入及各別Windows BLE驗證，八塊均完成；使用者決定全部位置重排、下次測試。最新見[HW-004](HW-004-six-anchor-expansion.md)，以下保留原六塊階段歷程，不作目前待刷數量。

- 日期：2026-11-27；執行者：Codex；設備接線：使用者。
- 來源版本：`bf4c793c2f965d17707477257f18fcfde6e0d59c`；本階段未修改韌體程式或參數。
- 狀態：刷機與各別 Windows BLE 驗證完成；HW-001 整體尚未驗收，RPi／校正／精度待驗。

| ID | 角色 | 刷機及 Flash 雜湊 | 實際 BLE 接收與解碼 | 證據 |
| --- | --- | --- | --- | --- |
| A01 | Anchor | 通過 | 通過 | TEST-021 |
| A02 | Anchor | 通過 | 通過 | TEST-022 |
| A03 | Anchor | 通過 | 通過 | TEST-023 |
| A04 | Anchor | 通過 | 通過 | TEST-024 |
| T01 | Target | 通過 | 通過 | TEST-025 |
| T02 | Target | 通過 | 通過 | TEST-026 |

每次只接一塊，核對唯一 ESP USB 埠、不同晶片序號及 ESP32-C3／4 MB Flash，再執行 `scripts/flash-device.py <ID> --port <已辨識埠>`。PlatformIO 6.2.0、espressif32 6.10.0、NimBLE 2.3.6。各次完成後以 Windows Bleak 掃描 10 秒，使用產品 `decode_advertisement` 確認 ID。主機序號、BLE 位址與韌體 SHA256 留在忽略的 artifacts，各命令結果見 test-log。

## 限制與後續驗收

- 只證明六塊各別能廣播及產品解碼器能識別；尚未驗證六塊同時收包或 RPi 接收。
- RSSI=-59 為韌體預設的 1 m 參考值，尚未實測校正；接收事件數不作發送頻率或遺失率證據。
- RPi 既有位址重查 SSH／HTTP 仍逾時；沒有更新 RPi 或假稱部署成功。
- 使用者依序貼上 ID 標籤並提供穩定電源；Anchor 座標在 RPi 場地設定維護，不在 XIAO 韌體內。
- RPi 恢復連線後：核對六個 ID／角色、更新程式、確認 raw observation 為 physical；實測場地座標／天線高度，校正 RSSI，再進行有獨立真值的定位評估。
- 備品兩塊尚未刷機，維持既定備用規劃。

## 問題與還原

Python runtime 失效與首次 stub 連線問題及改正方式見 ISSUE-016。沒有新核心修改需要還原；設備若需更換角色，先核對標籤／晶片識別，使用對應 PlatformIO environment 重新刷機並重新驗證廣播。
