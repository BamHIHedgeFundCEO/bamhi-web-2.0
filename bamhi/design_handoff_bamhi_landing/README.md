# Handoff: BamHI Quant 行銷首頁（方向 C · 矽谷科技 SaaS / 玻璃擬態）

## Overview
BamHI Quant 是一個「板塊輪動量化研究平台」的行銷官網首頁。目標客群是散戶與專業交易者，主打把避險基金等級的板塊輪動、即時訊號與量化研究整合成一個現代、流暢、看得懂的儀表板。本交接包是已選定的視覺方向 **C（矽谷科技 SaaS，玻璃擬態 + 漸層光暈 + oklch 電光青／紫）** 的完整首頁。

## About the Design Files
此資料夾內的檔案是 **以 HTML/React(Babel) 製作的設計參考稿** — 用來呈現預期的視覺與互動，**不是要直接照搬到正式環境的生產程式碼**。任務是：在目標 codebase 既有環境（React / Vue / Next.js 等）中，依其既有的元件與樣式慣例，**像素級重建這份設計**。若專案尚無前端環境，建議採用 **React + Vite + Tailwind（或 CSS Modules）**，搭配一個輕量圖表方案（見下方說明）。

目前原型使用瀏覽器內的 Babel 轉譯（`<script type="text/babel">`），純為展示用，正式專案請改用標準建置工具。

## Fidelity
**High-fidelity (hifi)。** 顏色、字體、間距、圓角、陰影、動效皆為最終值，請依本文件像素級重建。圖表為「示意用的種子化 SVG」（非真實資料），正式環境請以同樣的視覺風格接上真實資料來源。

## Design Tokens

### Colors（核心使用 oklch，後備色為 hex）
| Token | 值 | 用途 |
|---|---|---|
| `--c-bg` | `#0a0c12` | 主背景（深藍黑） |
| `--c-bg2` | `#0c0f17` | 次背景 / 玻璃面板底 |
| `--c-glass` | `rgba(255,255,255,.04)` | 玻璃面板填色（淡） |
| `--c-glass2` | `rgba(255,255,255,.06)` | 玻璃面板填色（稍實） |
| `--c-line` | `rgba(255,255,255,.09)` | 主分隔線 / 邊框 |
| `--c-line2` | `rgba(255,255,255,.06)` | 次分隔線 |
| `--c-text` | `#eef1f7` | 主文字 |
| `--c-dim` | `#9aa3b4` | 次文字 |
| `--c-mute` | `#626b7c` | 弱化文字 / 註腳 |
| `--c-cy` | `oklch(.78 .13 214)` | 電光青（重點色） |
| `--c-vi` | `oklch(.68 .17 292)` | 電光紫 |
| `--c-mint` | `oklch(.78 .15 165)` | 薄荷綠（上漲 / LIVE） |
| `--c-gcy` | `linear-gradient(135deg, oklch(.82 .12 200), oklch(.66 .16 250))` | 青色漸層（主 CTA / logo） |
| `--c-gvi` | `linear-gradient(135deg, oklch(.74 .15 300), oklch(.6 .19 280))` | 紫色漸層 |
| `--c-gmint` | `linear-gradient(135deg, oklch(.84 .14 160), oklch(.7 .15 195))` | 薄荷漸層 |

漲跌語意色：上漲 `#5fe0ad`（文字）/ `rgba(52,211,153,.16)`（底）；下跌 `#fb8ca0`（文字）/ `rgba(251,113,133,.16)`（底）。圖表內漲綠 `#34d399`、跌紅 `#fb7185`、均線青 `#3fd0e6`、紫 `#a98bff`。

### Typography
- **顯示 / 標題字（拉丁）**：`Space Grotesk`（400/500/600/700）
- **中文 / 內文**：`Noto Sans TC`（300/400/500/600/700）
- **數字 / 等寬**：`JetBrains Mono`（`font-variant-numeric: tabular-nums`）
- 字級：H1 `56px`/line-height 1.08/weight 700/letter-spacing -.02em；區段 H2 `38px`/700/-.02em；CTA 大標 `40px`；卡片標題 `18px`/600；內文 `15px`base、`lead` `17px`/line-height 1.75；眉標 eyebrow `13px`/600/letter-spacing .04em/青色；價格數字 `42px`/700。
- 基礎 `line-height: 1.65`。

### Spacing / Radius / Shadow
- 內容容器 `.wrap`：`max-width: 1140px; margin: 0 auto; padding: 0 40px;`
- 區段 `.sec`：`padding: 64px 0;`
- 圓角：按鈕 `10px`、卡片 / 面板 `18px`、CTA 大區塊 `24px`、nav 膠囊 `16px`、icon 方塊 `11px`、pill `30px`。
- 陰影：玻璃面板 `0 30px 70px rgba(0,0,0,.5)`；產品框 `0 40px 90px rgba(0,0,0,.55)`；主 CTA `0 6px 20px rgba(80,180,230,.3)`（hover 升為 `0 10px 28px rgba(80,180,230,.42)`）。
- 玻璃效果：`backdrop-filter: blur(14px~16px)` + `border: 1px solid var(--c-line)` + `linear-gradient(160deg, var(--c-glass2), var(--c-glass))`。

### 背景氛圍（ambient mesh）
固定定位的 `.mesh` 容器內含 3 顆 `border-radius:50%; filter:blur(90px)` 的光暈 blob（青 `oklch(.6 .18 250)`、紫 `oklch(.62 .19 300)`、青綠 `oklch(.7 .15 180)`，opacity .16~.28），疊加一層 `54px` 網格 `.grid-ov`（用 `radial-gradient` mask 從頂端淡出）。

## Screens / Views

只有一個頁面：**行銷首頁（單頁、垂直捲動）**。由上而下的區塊：

1. **Sticky Nav（膠囊玻璃導覽列）** — `position: sticky; top:0`。膠囊內含 logo（漸層方塊 + 旋轉 45° 的小方塊缺口 + 「BamHI Quant」）、4 個文字連結（總經市場 / 交易工具 / 交易模型 / 會員方案）、右側「登入」文字鈕 + 「免費開始」漸層鈕。膠囊 `backdrop-filter: blur(16px)`、`border-radius:16px`、底 `rgba(12,15,23,.6)`。

2. **Hero** — 兩欄 `grid-template-columns: 1.05fr .95fr; gap:44px`。左：LIVE pill（薄荷漸層小標籤）→ H1「看懂市場輪動，從今天開始」（第二行套青色漸層文字 `grad-t`）→ lead 文案 → 雙 CTA（漸層「免費開始掃描 →」+ ghost「▶ 看今日 AI 戰報」）→ 信任列（3 個漸層頭像疊圈 + 「已有 12,000+ 投資人每天使用」）。右：`.hv` 高 440px，兩張浮動玻璃卡（`@keyframes c-float`，上下 ±12px，7s / 6s reverse）：主卡「即時訊號推播」含 4 列板塊訊號 + LIVE 點；浮卡「相對輪動 RRG」含小型 RRG 圖。

3. **Bento 功能格** — 區段標題（eyebrow「功能總覽」+ H2「一個平台，整套研究工作流」+ 副標）。`display:grid; grid-template-columns: repeat(4,1fr); gap:16px`。6 張卡，第一張 `grid-column: span 2`。每張：漸層 icon 方塊 → 標題 → 描述 → 底部嵌入對應小圖表（RRG / sparkline / bars / area / heatmap / gauge）。卡片 hover：`translateY(-3px)` + 邊框與背景加亮。功能：板塊輪動+VCP、即時訊號推播、暗池異常資金、總經市場、板塊強弱、AI 交易模型。

4. **產品預覽（瀏覽器框）** — eyebrow「產品預覽」+ H2「板塊輪動工作台」。`.frame` 模擬瀏覽器視窗：頂列 3 個圓點 + 假網址 `app.bamhi.quant / sector-rotation`。內容兩欄 `1.5fr 1fr`：左欄為 K 線圖（SOXX 半導體 ETF，含均線）+ 機構資金流 FlowBars；右欄為 RRG + 板塊動能 Heatmap。

5. **Pricing** — eyebrow「會員方案」+ H2。`grid-template-columns: repeat(3,1fr); gap:18px`。三方案：體驗（NT$0）/ 進階（NT$790，`.hot` 高亮：發光邊框 + 漸層底 + 「最受歡迎」標籤 + 漸層價格文字）/ 旗艦（NT$1,990）。每卡：方案名 → 價格 → 註記 → 功能清單（每項 `CCheck` 青色勾勾 SVG）→ 底部按鈕。

6. **CTA 大區塊** — `.ctab`，置中，漸層底 + 邊框，圓角 24px。H2「明天的盤，今晚就準備好」+ 副標 + 雙 CTA。

7. **Footer** — 上邊框分隔。左：logo + 免責聲明（投資風險警語 + © 2026）。右：三欄連結（產品 / 資源 / 公司）。連結 hover 變青色。

## Interactions & Behavior
- **按鈕 hover**：漸層鈕 `translateY(-1px)` + 加深陰影；ghost 鈕 邊框與文字提亮（transition .18s）。
- **nav 連結 hover**：文字轉白 + 淡玻璃底（.15s）。
- **Bento 卡 hover**：上移 3px + 邊框／背景加亮（.22s）。
- **Hero 浮動卡**：無限上下浮動 `c-float`（7s / 6s ease-in-out，reverse 錯開）。正式環境請用 `@media (prefers-reduced-motion: reduce)` 關閉。
- **LIVE 指示點**：薄荷色圓點 + `box-shadow` 發光。
- 目前 nav 連結與按鈕為純視覺，未接真實導覽；正式環境請接路由 / 註冊流程。
- **響應式**：原型針對 ~1140px 內容寬設計。重建時請補上中斷點：Bento 4→2→1 欄、Pricing 3→1 欄、Hero 兩欄→單欄堆疊、nav 在窄螢幕收為漢堡選單。

## State Management
首頁本身為靜態行銷頁，無複雜狀態。正式環境唯一的動態需求是把示意圖表換成真實資料：
- 即時訊號列表、RRG 座標軌跡、K 線、Heatmap、資金流、AI 分數 → 由後端 / 行情 API 提供。
- 建議以伺服器端取資料 + 客戶端輪詢（或 WebSocket 推送 LIVE 訊號）。

## Assets
- **無點陣圖 / 無 logo 檔**：logo 為純 CSS（漸層方塊 + 旋轉小方塊）。
- **字體**：Google Fonts（Space Grotesk、Noto Sans TC、JetBrains Mono）。
- **所有圖表為內嵌 SVG**，由 `charts.jsx` 以種子亂數（`mulberry32`）生成，方便重現「像真實行情」的外觀。正式環境請以真實資料驅動同樣的視覺；可沿用這些 SVG 元件，或換成 D3 / visx / lightweight-charts 等函式庫，但須保留配色與風格。
- 勾勾圖示 `CCheck` 為內嵌 SVG（青色圓底 + 勾）。

## Charts 元件對照（charts.jsx → window）
皆以「明確顏色 props」主題化，方便換膚：
- `Spark` — 折線 sparkline
- `AreaSpark` — 含漸層填色的面積 sparkline
- `Candles` — K 線（含均線 `ma`）
- `Heatmap` — 板塊 × 期間 熱力格
- `RRG` — 相對輪動圖（四象限 + 軌跡點 + 標籤）
- `Gauge` — 環形分數計
- `BarMini` — 迷你直條
- `FlowBars` — 正負（資金流入／流出）雙向條

## Files
- `BamHI Quant.html` — 正式首頁進入點（全寬，掛載 `LandingC`）。
- `landingC.jsx` — 首頁全部結構與樣式（scoped 於 `.lpc`），匯出 `window.LandingC`。**這是主要重建依據。**
- `charts.jsx` — 所有 SVG 圖表原始碼與配色 props。
- `index.html`（選附）— 原始三方向比較畫布（A 終端機 / B 編輯風 / C 本方向），僅供脈絡參考。

> 重建順序建議：先落地 Design Tokens（顏色 / 字體 / 間距）→ 玻璃面板與按鈕基礎元件 → 由上而下逐區塊搭出版面 → 最後把圖表接上真實資料。
