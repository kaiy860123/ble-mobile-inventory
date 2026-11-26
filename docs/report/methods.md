# 計算方法、公式與實作對照

版本：報告方法草稿，2026-11-26。公式描述目前程式；工程參數是範例設定，不是實機精度保證。報告結果須標示使用的 commit、設定、資料來源與 run_id。

## 1. 符號與單位

| 符號 | 定義 | 單位 |
| --- | --- | --- |
| \(a_i=(x_i,y_i)\) | 第 i 個已知 Anchor 的 Local 平面位置 | m |
| \(p_k=(x_k,y_k)\) | 第 k 時點的掃描器估計位置 | m |
| \(q_j=(u_j,v_j)\) | 第 j 個靜止 Target 的未知位置 | m |
| \(r_k\)、\(s_k\) | 原始、濾波後 RSSI | dBm |
| \(P_{d_0}\) | 參考距離 \(d_0=1\) m 的實測接收 RSSI | dBm |
| \(n\) | 路徑損耗指數 | 無單位 |
| \(d\)、\(\rho\) | 估計三維斜距、扣除高度差後的水平距離 | m |
| \(\theta\) | Local +X 相對正東的逆時針旋轉角 | 設定用度，計算用弧度 |
| \(\varphi,\lambda,h\) | WGS84 緯度、經度、橢球高 | 設定為度／m |
| \(z,\Delta h\) | Local 相對高度、天線高度差 | m |
| \(m,W,B\) | 參考觀測數、\(W=\operatorname{diag}(w_i)\)、包圍盒基線 | 筆、無單位、m |

重要區別：\(P_{d_0}\) 是接收訊號的校正值，不是晶片射頻發射功率；RSSI 濾波與測距也不提供方向資訊。

## 2. RSSI 濾波

先使用因果滑動中位數，再用指數移動平均：

\[
\widetilde r_k=\operatorname{median}(r_{\max(0,k-w+1)},\ldots,r_k)
\]

\[
s_k=\alpha\widetilde r_k+(1-\alpha)s_{k-1},\qquad s_0=\widetilde r_0
\]

目前範例 \(w=3\)、\(\alpha=0.65\)。中位數抑制短時離群，EMA 平滑抖動；移動掃描器會受到時間延遲，不能只以畫面平滑判斷定位較準。設備長時間未收到後重新建立濾波器，避免混入過舊觀測。

實作：`src/ble_inventory/positioning.py:RssiFilter`、`engine.py:ingest`。

上述參數來自場地設定；直接呼叫 `RssiFilter()` 的函式預設仍是 alpha=0.4、window=5。重置條件為相鄰接收間隔大於 stale_after_s（範例 10 s），不是 Anchor 解算視窗的 3 s。

## 3. RSSI 測距與校正

採對數距離模型：

\[
r(d)=P_{d_0}-10n\log_{10}(d/d_0)+\varepsilon
\]

由濾波後 RSSI 反解：

\[
\widehat d=d_0\,10^{(P_{d_0}-s_k)/(10n)}
\]

範例：\(P_{1m}=-59\) dBm、\(s_k=-79\) dBm、\(n=2\)，得到 \(\widehat d=10\) m。這只是模型計算，不表示實際測距誤差為零。

校正資料使用多個已知距離：令 \(z_l=\log_{10}(d_l/d_0)\)，

\[
\begin{bmatrix}\widehat\beta_0\\\widehat\beta_1\end{bmatrix}
=\arg\min_{\beta_0,\beta_1}\sum_l(r_l-\beta_0-\beta_1z_l)^2,
\quad \widehat P_{d_0}=\widehat\beta_0,
\quad \widehat n=-\widehat\beta_1/10
\]

程式以最小平方法求解，不直接計算矩陣逆。校正腳本要求每設備至少六筆、距離範圍約至少二倍，並檢查 \(0.5\le n\le6\)。這些是資料檢查門檻；實驗仍應採多距離、多次量測，並保留天線方向與高度。

實作：`positioning.py:rssi_to_distance`、`scripts/calibrate-rssi.py`。每設備設定優先於封包參考值，最後才使用全域範例值。

## 4. 高度差與水平距離

在已知天線高度差 \(\Delta h\) 下：

\[
\rho=\sqrt{\widehat d^2-(\Delta h)^2}
\]

目前實作只接受 \(\widehat d>|\Delta h|\)，不符者視為不一致或退化觀測。所有高度須用同一 Local 基準；模擬飛行高度可作已知輸入，但掃描器真值 XY 不得提供給定位器。

實作：`positioning.py:horizontal_distance`。

WGS84 輸入時，georeference.height_m 必須對應 Local z=0 基準面的橢球高；scanner_height_m 與 Target 高度則是相對此面的高度。不能同時將原點橢球高留 0、Anchor 填實際橢球高、RPi 填離地高度，而期待高度差正確。

## 5. 第一階段：Anchor 求掃描器位置

每個 Anchor 形成距離限制：

\[
\|p-a_i\|\simeq\rho_i
\]

以第 0 個參考點相減，建立線性初值：

\[
2(a_i-a_0)^T p
=\rho_0^2-\rho_i^2+\|a_i\|^2-\|a_0\|^2
\]

寫為 \(Ap\simeq b\)，求 \(p^{(0)}=A^+b\)。實作使用 `numpy.linalg.lstsq`，避免把 \((A^TA)^{-1}\) 當作必要且總能存在的計算方式。

至少需要三個具良好二維幾何的參考點；「有三個點」不保證可定位，若近乎共線仍須拒絕或提示品質不足。

差分索引為 i=1,…,m−1，A 有 m−1 列、2 欄。使用最近 anchor_ttl_s（範例 3 s）內的 Anchor 觀測，移動中不同 Anchor 的測距可能非同一時間，應列為誤差來源。

## 6. 非線性改良與穩健加權

目前求解器採非線性距離殘差：

\[
v_i(p)=\|p-a_i\|-\rho_i
\]

使用 Huber 型加權的迭代最小平方法：

\[
L_H(e)=\begin{cases}\tfrac12 e^2,&|e|\le c\\c(|e|-\tfrac12c),&|e|>c\end{cases}
\]

\[
w_i=\min\left(1,\frac{c}{\max(|v_i|,10^{-6})}\right),\qquad c=1.5\text{ m}
\]

\[
J_i=\frac{(p-a_i)^T}{\max(\|p-a_i\|,10^{-6})}
\]

\[
\Delta=\arg\min_\delta\|W^{1/2}(J\delta-v)\|_2^2,
\qquad p\leftarrow p-\Delta
\]

每次步長上限 5 m，最多 30 次；步長小於 \(10^{-6}\) m 結束。這是防止數值不穩定的工程設定，不是統計信賴區間。

對中心化參考點矩陣 \(C\) 做 SVD。若最小奇異值小於 \(10^{-5}\) 或 \(\sigma_{max}/\sigma_{min}>100\)，視為退化／條件差。距離殘差為：

\[
R_{range}=\sqrt{\frac1m\sum_i(\|\widehat p-a_i\|-\rho_i)^2}
\]

範例最大可接受殘差為 2.5 m，超過則不更新有效位置。**小殘差不代表小真實位置誤差**；受共同偏差影響時，模型可自洽但仍偏離真值。

實作：`positioning.py:multilaterate`、`engine.py`。

此處 v 為有號測距殘差，與 §10 的非負真實位置誤差 e 分開。求解內採 Huber 權重，但品質閘門使用未加權 RMS；因此離群值仍可能使有效解被拒絕，或使有偏解在殘差門檻內通過。

## 7. 第二階段：移動觀測求靜止 Target

在掃描器估計位置 \(\widehat p_k\) 有效時累積 Target 測距：

\[
\widehat q_j=\arg\min_q\sum_{k\in\mathcal W_j}
L_H\left(\|q-\widehat p_k\|-\rho_{j,k}\right)
\]

使用同一最小平方法初值與穩健迭代。\(\mathcal W_j\) 為最近觀測窗口；目前範例窗口 120 s、上限 240 筆、至少六筆。相鄰採樣掃描器位置至少移動 0.15 m 才加入，並要求：

\[
B=\sqrt{(\max x_k-\min x_k)^2+(\max y_k-\min y_k)^2}\ge1.5\text{ m}
\]

此外仍檢查共線／條件數。此基線是觀測位置包圍盒對角長，不是每兩個採樣點都須相距 1.5 m。

第一階段的位置誤差會傳遞到第二階段；Target 巡查期間靜止是本方法的基本假設。實際飛行控制使用的導航位置與本專題 BLE 掃描器估計位置應分開。

240 筆上限與 0.15 m 位移門檻目前是程式常數；窗口時間、最低樣本及基線來自設定。Target 解與掃描器解同樣套用 max_residual_m（範例 2.5 m）品質閘門。

## 8. Local、ENU 與 WGS84

### 8.1 Local 旋轉至 ENU

\[
\begin{bmatrix}E\\N\end{bmatrix}
=\begin{bmatrix}\cos\theta&-\sin\theta\\\sin\theta&\cos\theta\end{bmatrix}
\begin{bmatrix}x\\y\end{bmatrix},\qquad U=z
\]

\(\theta=0\) 時 X 向東、Y 向北；\(90^\circ\) 時 X 向北、Y 向西。逆轉換使用 \(-\theta\)。自動轉換需要明確原點與方向，不能僅由任意 Local 數值推得唯一經緯度。

### 8.2 WGS84 至 ECEF

\[
a=6378137\text{ m},\quad f=1/298.257223563,\quad e^2=f(2-f)
\]

\[
N_\varphi=\frac{a}{\sqrt{1-e^2\sin^2\varphi}}
\]

\[
X=(N_\varphi+h)\cos\varphi\cos\lambda,\quad
Y=(N_\varphi+h)\cos\varphi\sin\lambda,\quad
Z=(N_\varphi(1-e^2)+h)\sin\varphi
\]

設定中的角度先轉弧度。\(h\) 是橢球高，不能直接當作海拔或任意樓層高度。

### 8.3 ECEF 與場地 ENU

以原點 \((\varphi_0,\lambda_0,h_0)\) 得 \(X_0\)，定義：

\[
R=\begin{bmatrix}
-\sin\lambda_0&\cos\lambda_0&0\\
-\sin\varphi_0\cos\lambda_0&-\sin\varphi_0\sin\lambda_0&\cos\varphi_0\\
\cos\varphi_0\cos\lambda_0&\cos\varphi_0\sin\lambda_0&\sin\varphi_0
\end{bmatrix}
\]

\[
[E,N,U]^T=R(X-X_0),\qquad X=X_0+R^T[E,N,U]^T
\]

ECEF 反解地理座標時，\(\lambda=\operatorname{atan2}(Y,X)\)，緯度採迭代，極點另外處理。地圖元件的顯示投影與此 Local 公尺框架分開。

具體迭代式（非極點）：令 \(p=\sqrt{X^2+Y^2}\)，\(\varphi^{(0)}=\operatorname{atan2}(Z,p(1-e^2))\)，

\[
\varphi^{(k+1)}=\operatorname{atan2}\!\left(Z+e^2N_{\varphi^{(k)}}\sin\varphi^{(k)},p\right),\qquad
h=\frac{p}{\cos\varphi}-N_\varphi.
\]

目前最多 12 次，緯度變化小於 \(10^{-14}\) rad 停止；極點改用半短軸計算高度。

實作：`coordinates.py`；測試：`tests/test_coordinates.py`、`tests/test_config.py`。

## 9. 盤點與暫未收到

對本次任務 \(R\)，去重集合與計數：

\[
S_R=\{ID_i:\text{任務內曾收到該 Target 的合法觀測}\},\quad C_R=|S_R|
\]

目前可見數：

\[
C_{visible}(t)=\sum_{i\in Targets}\mathbb 1[0\le t-t_i^{last}\le\tau],\qquad\tau=10\text{ s}
\]

中途關掉 Target，\(C_R\) 保留，\(C_{visible}\) 超時後下降。開始新任務才清空本次集合；Anchor 不列入 Target 計數。

僅場地名單中的 Target 計入 S_R，未登錄 ID 略過。掃描器若超過 anchor_ttl_s 未有新觀測批次，另標近期無有效觀測；這與 Target 的 10 s 可見期限不同。

## 10. 評估指標

在獨立真值 \(p_k^*\) 下定義水平位置誤差：

\[
e_k=\sqrt{(\widehat x_k-x_k^*)^2+(\widehat y_k-y_k^*)^2}
\]

\[
MAE=\frac1N\sum_ke_k,\quad
RMSE=\sqrt{\frac1N\sum_ke_k^2},\quad
P50=Q_{0.5}(\{e_k\}),\quad P95=Q_{0.95}(\{e_k\})
\]

定位成功率及盤點召回率另計：

\[
\text{定位成功率}=\frac{\text{有效定位時點數}}{\text{預定評估時點數}},\qquad
\text{盤點召回率}=\frac{|S_R\cap G_R|}{|G_R|}
\]

\(G_R\) 需事先定義為任務期間實際應被盤點的 Target 集合，與「目前正在廣播」的時間集合分開。無樣本或分母為零時標不適用，不能填 0 冒充量測。

目前評估腳本依 `position_at` 與獨立真值時間對齊，預設最大差 0.25 s；同一位置時間不重複計分，只評估有效位置。因此現有 MAE／RMSE 是**條件於有效解**的結果，應另外報告有效解數與成功率。若未有效解只報精度，容易形成選樣偏差。

實作：`scripts/evaluate-run.py`。新增成功率、端到端延遲、盤點召回率的正式實驗彙整仍需測試與資料，不宣稱目前腳本已全部實作。

## 11. 目前可引用的合成結果

| 設備 | 有效位置樣本 | MAE（m） | RMSE（m） | P50（m） | P95（m） |
| --- | ---: | ---: | ---: | ---: | ---: |
| RPi01 | 90 | 1.043 | 1.106 | 1.029 | 1.734 |
| T01 | 85 | 0.464 | 0.802 | 0.305 | 1.809 |
| T02 | 65 | 0.220 | 0.349 | 0.116 | 1.029 |

來源：TEST-005、固定種子合成觀測及獨立 `tests/fixtures/truth.jsonl`。不是 Gazebo，也不是 BLE 實測。T02 的廣播有中斷情境，不能把 65/90 直接當成與實驗設計無關的定位失敗率。

## 12. 第一手參考

- [NumPy least squares](https://numpy.org/doc/stable/reference/generated/numpy.linalg.lstsq.html)
- [PROJ topocentric conversion](https://proj.org/en/stable/operations/conversions/topocentric.html)
- [AWS IoT 協定與驗證](https://docs.aws.amazon.com/iot/latest/developerguide/protocols.html)

公式與具體參數以本專題程式／設定對照為準；外部文件支持工具與座標定義，不替代本專題實測。
