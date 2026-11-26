# 專題檔案存放規劃

已建立目錄與文件。可執行 Python 套件位於 `src/ble_inventory/`；原先 gateway／positioning／adapters 目錄提供對照說明，contracts 另保存公開 schema。

```text
專題/
├── README.md
├── GLOSSARY.md
├── 原始 PPTX、專題構想.txt      # 保留原位
├── docs/
│   ├── requirements.md         # 當前需求的主要紀錄
│   ├── interview-log.md        # 訪談歷史
│   ├── project-layout.md
│   ├── development-log.md
│   ├── issues.md
│   ├── test-log.md
│   ├── design/                 # 架構、座標等設計
│   └── references/             # 教材與來源索引
├── firmware/                   # XIAO 共用韌體、刷機說明
├── src/
│   ├── gateway/                # RPi BLE 收集與本地服務
│   ├── positioning/            # 濾波、兩階段定位、座標轉換
│   ├── contracts/              # 實體與模擬共用資料格式
│   └── adapters/               # Gazebo 輸入轉接、AWS 輸出轉接
├── web/                        # 共用網頁，部署至 RPi 或 Pages
├── config/                     # 可分享的設定範例
├── scripts/                    # 環境安裝、執行、部署、匯出腳本
├── tests/                      # 自動測試與可重現案例
├── data/
│   ├── raw/                    # 未修改的觀測與校正輸入
│   ├── processed/              # 定位結果及評估結果
│   └── replays/                # 可回放資料
├── artifacts/                  # 測試截圖、終端紀錄、影片證據
└── deliverables/               # 最終報告、展示影片、交付套件
```

## 存放與命名

- 每次實驗使用唯一 `run_id`，建議 `YYYYMMDDTHHMMSS+0800_<physical|simulation|replay>_<短名稱>`；檔名中的時間不要含冒號。
- 同一 `run_id` 對應 `data/raw/<run_id>/`、`data/processed/<run_id>/` 與 `artifacts/<run_id>/`。
- 每次實驗附 manifest，記錄來源、開始時間／時區、程式版本（未使用 Git 則記文件或套件版本）、設定版本、設備 ID、校正資料、座標框架、操作人及關聯 TEST／ISSUE。
- 原始資料只新增，重跑分析產生新結果或版本，不覆寫原始輸入。
- 公開回放只使用明確選定的實驗／示範資料，不直接發布全部本地資料。
- `config/` 放範例；真實憑證、私鑰、AWS 帳號私密設定與主機登入資料放在受忽略的本地位置。
- Gazebo 世界、飛控與航線由組員維護；此處保存共用介面、轉接器、已交付的樣本與整合說明，不接管其模擬實作。

## 開發、問題、測試如何串起來

`需求 → 開發紀錄 → ISSUE-NNN（若遇問題）→ TEST-NNN → run_id／證據 → 修正後驗證`

- 每次變更記錄「改了什麼、為什麼、影響哪些需求」。
- 每次失敗記錄實際錯誤與重現環境；推測原因和已證實原因分開。
- 修正需連結測試紀錄，測試結果必須註明通過／失敗／阻塞／未執行。
- 重要且難逆轉的取捨確認後，再依需要建立 ADR；不為每個小決定建立 ADR。
