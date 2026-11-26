# BLE 移動盤點與定位專題

以 XIAO ESP32C3 廣播設備與 Raspberry Pi 4B，實作移動盤點、兩階段 RSSI 定位及網頁呈現；Gazebo 模擬由另一位組員負責。

**目前階段：核心與網頁已實作、Pages 已發布，RPi 已部署並啟動實體 BLE 掃描與開機服務；XIAO 刷機、場地定位實測與 AWS 雲端部署尚待完成。**

## 快速開始

Windows 需 Python 3.11+ 與 Node.js 20+：

```powershell
./scripts/setup.ps1
./scripts/run-local.ps1
```

開啟 `http://127.0.0.1:8080`。預設合成示範不代表 Gazebo 或實體設備驗證；公開頁預設為明確標示的回放。RPi、刷機、校正、AWS 登入及部署詳見 [操作說明](docs/runbook.md)。

## 先讀這些文件

| 文件 | 用途 |
| --- | --- |
| [需求與驗收](docs/requirements.md) | 已確認需求、待確認事項與範圍 |
| [檔案存放規劃](docs/project-layout.md) | 程式、設定、資料、證據的存放方式 |
| [訪談紀錄](docs/interview-log.md) | 使用者回答及需求變更脈絡 |
| [架構候選方案](docs/design/architecture.md) | RPi、GitHub Pages、AWS 的角色與資料流 |
| [座標規劃](docs/design/coordinates.md) | Local／WGS84 轉換與底圖條件 |
| [開發紀錄](docs/development-log.md) | 每次變更、原因、關聯問題與驗證 |
| [問題與修正](docs/issues.md) | 重現、原因、處置、驗證與狀態 |
| [測試紀錄](docs/test-log.md) | 測試環境、步驟、預期、實際與證據 |
| [專題用語](GLOSSARY.md) | Anchor、Target、座標及定位用語 |
| [操作說明](docs/runbook.md) | 本地執行、RPi、刷機、校正與故障處理 |
| [共用介面](docs/contracts.md) | Gazebo／實體觀測、BLE 封包與輸出格式 |
| [AWS 部署](docs/aws-deployment.md) | Free Plan 查核、權限、裝置與觀看者配置 |

## 已知時程

- 展示／繳交日：2026-12-24（依本次對話年份解讀 12/24）。
- 主要功能完成目標：2026-12-10。
- 雙方整合完成目標：2026-12-17；可提前。
- 2026-12-18 至 2026-12-23：演練、修正與交付準備。

## 紀錄規則

1. 需求決定後即更新 `docs/requirements.md`；訪談脈絡記入 `docs/interview-log.md`。
2. 每次開發變更記入 `docs/development-log.md`。
3. 遇到問題即建立 `ISSUE-NNN`，記下症狀、重現方式、嘗試與修正，尚未驗證不能標為已解決。
4. 每次有意義的測試建立 `TEST-NNN`，連結資料及證據；明確區分實體、模擬與回放結果。
5. 原始觀測保留不覆寫，衍生結果另存；AWS／RPi 私密設定與憑證不發布。

原始簡報與構想檔維持在根目錄，不搬動或修改。課堂 PDF 維持使用者提供的 Downloads 路徑；其索引見 `docs/references/README.md`。
