<!--
  GuideView.vue — 使用說明 (/app/guide)
  靜態手風琴頁。無後端呼叫，無 Pinia store。
  12 個功能區塊，預設全展開，點標題可折疊。
-->
<template>
  <div class="guide">
    <div class="guide-header">
      <h1>📖 使用說明</h1>
      <p class="guide-sub">BamHI Quant 所有功能的操作與解讀指南。點擊標題可折疊各區塊。</p>
      <p class="guide-date mono">最後更新：2026-07-10</p>
    </div>

    <!-- 快速導覽 -->
    <nav class="toc">
      <span class="toc-label">快速跳轉：</span>
      <a v-for="s in SECTIONS" :key="s.id" :href="'#' + s.id" class="toc-link">{{ s.emoji }} {{ s.short }}</a>
    </nav>

    <!-- Accordion sections -->
    <section
      v-for="s in SECTIONS"
      :key="s.id"
      :id="s.id"
      class="accordion"
    >
      <button class="acc-head" @click="toggle(s.id)">
        <span class="acc-title">{{ s.emoji }} {{ s.title }}</span>
        <span class="acc-arrow" :class="{ open: opened[s.id] }">▼</span>
      </button>
      <div v-show="opened[s.id]" class="acc-body">
        <p class="acc-summary">{{ s.summary }}</p>

        <!-- 怎麼用 -->
        <div class="sub-block">
          <h3 class="sub-title">▶ 怎麼用</h3>
          <ul>
            <li v-for="(item, i) in s.howTo" :key="i" v-html="item" />
          </ul>
        </div>

        <!-- 怎麼看 -->
        <div class="sub-block" v-if="s.howRead && s.howRead.length">
          <h3 class="sub-title">▶ 怎麼看（指標解讀）</h3>
          <ul>
            <li v-for="(item, i) in s.howRead" :key="i" v-html="item" />
          </ul>
        </div>

        <!-- 注意事項 -->
        <div class="sub-block warn" v-if="s.warnings && s.warnings.length">
          <h3 class="sub-title">⚠️ 注意事項</h3>
          <ul>
            <li v-for="(item, i) in s.warnings" :key="i" v-html="item" />
          </ul>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { reactive } from 'vue'

const SECTIONS = [
  {
    id: 'search',
    emoji: '🔍',
    short: '個股搜尋',
    title: '個股搜尋',
    summary: '在頂部導覽列的搜尋框輸入任意美股代碼，即可進入個股深度分析頁，包含技術線圖、內部人交易與基本財務。',
    howTo: [
      '在頂部搜尋框輸入美股代碼（如 <code>AAPL</code>、<code>NVDA</code>），按 Enter 跳轉。',
      '選擇 <b>歷史區間</b>（6mo / 1y / 2y / 5y / max）調整 K 線長度。',
      '選擇 <b>K線級別</b>（1小時線 / 日線 / 週線）切換顆粒度。',
      '三個分頁：<b>技術線圖</b>（預設）/ <b>內部人交易</b> / <b>基本資料</b>。',
    ],
    howRead: [
      '<b>技術線圖</b>：K線 + MA10/20/60/120/200 均線，下方量化綜合分數（0–100）；分數 &gt;75 偏熱、&lt;25 偏冷。',
      '<b>趨勢狀態 / 量化訊號</b>：頁面頂部兩個標籤，快速確認個股當下狀態。',
      '<b>內部人交易</b>：Form 4 買賣標記疊在 K 線上，▲ 綠 = 公開買入（P），▼ 紅 = 公開賣出（S）；交易明細列出姓名、職位、股數、金額、申報日期。',
    ],
    warnings: [],
  },
  {
    id: 'home',
    emoji: '🏠',
    short: '首頁',
    title: '首頁 — 板塊即時訊號推播',
    summary: '登入後首頁展示全市場板塊的 RRG 象限 + MA 排列即時趨勢狀態，讓你一眼掌握哪些板塊正在領漲、哪些轉弱。',
    howTo: [
      '登入後自動載入板塊訊號，首次需約 5–15 秒（bulk 下載所有板塊資料）。',
      '直接瀏覽卡片顏色：<b>綠色</b> = 強勢領先，<b>藍色</b> = 改善中，<b>黃色</b> = 弱化，<b>橘/紅色</b> = 落後，<b>灰色</b> = 中性。',
      '點任一板塊卡片 → 自動跳轉「板塊輪動」頁並捲動到該板塊深度分析。',
      '三個快捷按鈕（🔄板塊輪動 / 🤖今日AI戰報 / 📊總經市場）可快速進入對應功能。',
    ],
    howRead: [
      '<b>狀態標籤</b>（如「動能領先」「逆勢上行」「籌碼轉弱」）= RRG 象限位置的口語化解讀。',
      '<b>detail 文字</b> = 當前動能差值（M10−M20）與 RS 相對強度的量化描述。',
      '<b>👑 龍頭：</b> = 該板塊 RS 排名最高的 1–3 檔個股，可拿去搜尋個股詳情。',
    ],
    warnings: [],
  },
  {
    id: 'macro',
    emoji: '📊',
    short: '總經市場',
    title: '總經市場 — 利率、市場寬度、情緒',
    summary: '監控影響整體市場走向的六大總經指標，包含殖利率曲線、核心經濟指標、市場寬度與情緒方向，含歷史衰退帶對照。',
    howTo: [
      '頂部 <b>指標切換按鈕</b> 選擇要看的指標：10年期美債 / 2年期美債 / 10-2 Spread / 核心經濟 / 市場寬度 / 情緒方向。',
      '<b>時間區間按鈕</b>（All / 6m / YTD / 1y / 3y / 5y / 10y）過濾圖表長度（客戶端切片，不重新下載）。',
      '若指標有子項目（如「情緒方向」有 NAAIM 與其他），會出現 <b>子 Tab</b> 可切換。',
    ],
    howRead: [
      '<b>最新值 + 漲跌</b>：右上角 MetricCard 顯示最新數值與期間變化。',
      '<b>灰色背景帶</b>：美國 NBER 定義的官方衰退期，觀察指標在衰退前後的走勢規律。',
      '<b>10-2 Spread</b>：10年期殖利率 − 2年期殖利率；倒掛（負值）歷史上是衰退前兆，恢復正數是景氣回升訊號。',
      '<b>市場寬度</b>：S&P 500 成分股中站上特定均線的比例；&lt;20% 為超賣警示，&gt;80% 偏熱。',
      '<b>情緒方向</b>：NAAIM（機構主動型基金曝險）或其他情緒指標；極高 = 過度樂觀，極低 = 恐慌底部。',
    ],
    warnings: [],
  },
  {
    id: 'screener',
    emoji: '🎯',
    short: '模型選股',
    title: 'BamHI 模型選股 — VCP / Alpha / Genesis',
    summary: '三套量化模型篩選出的每日候選清單：VCP 結構（跨板塊）、Alpha 趨勢戰報、Genesis 逆勢戰報。所有結果按市值分級，輸出優先排序清單。',
    howTo: [
      '切換頂部 Tab：<b>VCP</b>（Volatility Contraction Pattern）/ <b>Alpha 戰報</b> / <b>Genesis 戰報</b>。',
      'VCP Tab：直接看排序清單；🎯 強訊優先，其次看 VCP 分數 ≥70，等帶量突破進場。',
      'Alpha / Genesis Tab：選擇市值級別下拉（或看全部），每級最多 10 檔按 Resonance_Score 排序。',
      '展開頁面底部「📖 選股器使用方法 + 篩選邏輯」查閱完整 Playbook。',
    ],
    howRead: [
      '<b>VCP 分數</b>：越高代表收縮結構越完整（滿分 100）。<b>🎯 強訊</b> = 趨勢通過 + 連續收縮 + 吸籌訊號 + 跑贏大盤四條件全過。',
      '<b>Resonance_Score</b>（共振分）：Alpha/Genesis 模型的綜合打分，0–100。',
      '<b>Win_Prob</b>：AI 模型的預估勝率，僅作參考，<b>非真實歷史勝率</b>。',
      '<b>市值分級</b>：Mega（≥$100B）→ Large（$10–100B）→ Mid（$2–10B）→ Small（$300M–2B）→ Micro（&lt;$300M）；各級流動性門檻與停損規則不同。',
      '<b>ATR 停損</b>：進場價 − 1.5×ATR（平均真實波動幅度），勝過固定百分比停損。',
    ],
    warnings: [
      '<b>Genesis 歷史勝率約 22%</b>——會連敗。每筆 ≤2% 總資金嚴格執行，否則連敗期間帳戶會嚴重受損。',
      '這是篩選器，不是進場訊號。確認盤中量價配合後才執行。',
    ],
  },
  {
    id: 'dark-pool',
    emoji: '🕳️',
    short: '暗池監控',
    title: '暗池異常資金監控 — Surx 異常偵測',
    summary: '每日盤後全自動運算，捕捉暗池（場外 ATS）成交量異常放大事件（Surx），整合 VCP 趨勢結構與反彈技術濾網，過濾噪音。',
    howTo: [
      '頁面載入即顯示當日 Top 50 Surx 異常名單，按 Surx 由高到低排序。',
      '按 <b>↻ 重新整理</b> 手動刷新資料。',
      '按 <b>📥 下載 CSV</b> 匯出清單（Sparkline 走勢欄除外）。',
    ],
    howRead: [
      '<b>Surx（暗池成交量異常指數）</b>：當日暗池成交量 ÷ 歷史均值。<span style="color:#ff851b">橘色 ≥3.0x = 強烈異常</span>；<span style="color:#e5c07b">黃色 ≥1.5x = 值得注意</span>；無色 = 正常。',
      '<b>RSI 14</b>：<span style="color:#ef4444">紅色 &gt;70 = 超買</span>；<span style="color:#22c55e">綠色 &lt;30 = 超賣</span>。Surx 異常 + RSI 超賣 = 潛在反彈訊號。',
      '<b>60D 走勢 Sparkline</b>：快速確認近期趨勢方向，避免在下降趨勢中追暗池訊號。',
      '<b>MA200</b>：布林欄，確認是否站在長期均線之上（趨勢向好）。',
    ],
    warnings: [
      'Surx 是觀察名單，不是確認進場訊號。需配合 K 線型態、量能確認才有效。',
      '暗池訊號可能 T+1 才反映在日線，消息驅動的個股可能早已反應。',
    ],
  },
  {
    id: 'sector-rotation',
    emoji: '🔄',
    short: '板塊輪動',
    title: '板塊輪動 + VCP — 全覽與深度分析',
    summary: '最完整的板塊分析工具。上方全覽四個視圖掌握 41 個主題板塊相對位置，下方深度分析含 7 個動能指標、6 張圖表、VCP 選股清單。',
    howTo: [
      '左上下拉選擇 <b>深度掃描板塊</b>（或點熱力圖/RRG 上的板塊自動帶入）。',
      '右上下拉選擇 <b>歷史區間</b>（6mo / 1y / 2y / 5y）——軌跡圖建議選 2y 以上。',
      '<b>全覽 Tab 四選一</b>：熱力圖 / RRG 象限快照 / RRG 軌跡 / 相關係數熱力圖。',
      '點熱力圖方塊或 RRG 象限上的板塊點 → 自動跳轉並捲動到下方深度分析區。',
      '軌跡圖底部可切換天數（5 / 10 / 15 / 20 天）觀察路徑長短。',
    ],
    howRead: [
      '<b>熱力圖顏色（M10−M20）</b>：綠色 = 短線動能加速（短期強於中期）；紅色 = 動能轉弱。',
      '<b>RRG 四象限</b>：右上（領先）→ 右下（弱化）→ 左下（落後）→ 左上（改善）→ 循環；領先 + 持續向右上最強。兩軸都是「相對 SPY」，<b>不含絕對漲跌</b>。',
      '<b>實心 / 空心點</b>：實心 = 絕對趨勢多頭（指數 &gt; MA60 &gt; MA200）；空心 = 非多頭。<b>落在領先象限但空心 = 抗跌，不是強勢</b>（跌得比大盤少也會被畫在領先）。只看實心點。',
      '<b>相關係數熱力圖</b>：顏色越深 = 兩板塊同步性越高；行同向板塊不具分散效果。',
      '<b>7 個動能指標</b>：M5（5日極速）、M10（10日波段）、M20（中線）、動能差值（M10−M20 = 短線加速度）、RS斜率、資金佔大盤均量比。',
      '<b>板塊寬度</b>：成分股站上 MA20 的比例；≥80% = 過熱，≤20% = 超賣。',
      '<b>機構資金流</b>：上行成交量 ÷ 下行成交量；&gt;1.5x = 積極吸籌，&lt;0.7x = 分配。',
      '<b>VCP 清單</b>：板塊成分股中符合收縮結構的個股，🎯 強訊優先研究。',
    ],
    warnings: [
      '第一個 RRG 點需 63 個交易日、完整 20 點軌跡需 <b>82 個交易日</b>（約 4 個月）；區間選 6mo 以下軌跡會不完整。',
      '實心/空心需要 MA200 → 至少 <b>1y</b> 區間；選 6mo 時全部退回實心，該資訊失效。',
      '軌跡上限 20 個交易日（約 4 週），看不到標準 RRG 那種數月尺度的順時針旋轉，只能看短期方向。',
      '板塊指數為成分股<b>等權</b>合成，不是市值權重，也不是可交易的 ETF。',
    ],
  },
  {
    id: 'sector-strength',
    emoji: '🧭',
    short: '美股板塊強弱',
    title: '美股板塊強弱 — RS 線 + 動能熱力圖 + 策略掃描',
    summary: '專注美股 11 大板塊的相對強度，提供 RS 相對強度線、不同週期動能熱力圖、板塊總覽排名表，以及策略 A/B/C 三套量化掃描。',
    howTo: [
      '<b>RS 相對強度線</b>：點選上方 chip 按鈕選擇要比較的板塊（可多選），圖表即時更新疊加顯示。',
      '<b>動能熱力圖</b>：切換週期按鈕（1D / 3D / 1W / 1M / 3M）調整計算窗口。',
      '<b>板塊總覽表</b>：按列點擊 → 展開該板塊 ETF 的持股明細，並顯示「黃金伏擊條件」清單。',
      '<b>策略掃描</b>：滾動到頁面下方看策略 A（強勢持續）/ B（動能加速）/ C（轉強初期）各自的名單。',
    ],
    howRead: [
      '<b>RS 線（vs VTI）</b>：基準 = 1.0；持續高於 1.0 且向上 = 跑贏大盤。',
      '<b>20R / 60R / 120R</b>：全市場百分位排名（0–100），越高代表短/中/長期動能越強。',
      '<b>REL5 / REL20</b>：相對大盤 5 日 / 20 日的超額報酬。',
      '<b>🔥 黃金伏擊條件</b>：RSI &lt;60 + RS線 &gt;50MA + 50MA 斜率向上，是最佳的趨勢中回調進場窗口。',
    ],
    warnings: [],
  },
  {
    id: 'world-sectors',
    emoji: '🐫',
    short: '全球市場強弱',
    title: '全球市場強弱 — 龜族全景動能儀表板',
    summary: '覆蓋美股、各國 ETF、債券、商品、匯率等 30+ 全球資產類別，提供多週期動能排行與策略訊號掃描，幫助資產配置決策。',
    howTo: [
      '頂部 <b>週期按鈕</b>（1D / 1W / 1M / 3M / 6M / 1Y）切換計算窗口，圖表與排行即時更新。',
      '<b>熱力圖</b>：一眼看全球強弱格局，顏色越深綠 = 動能越強。',
      '<b>各區域排行</b>：US 股票 / 亞太 / 新興市場 / 債券 / 大宗商品分開呈現，方便跨類別比較。',
      '<b>策略掃描</b>：頁面下方三套策略掃出符合條件的全球資產。',
    ],
    howRead: [
      '<b>動能計分模式</b>：頁面頂部說明目前是「波動率調整計分（報酬÷標準差）」或「純漲跌幅」——前者更準確反映風險調整後表現。',
      '<b>趨勢線 Sparkline</b>：每個資產旁的 60 日走勢縮圖，快速確認趨勢方向不看文字。',
    ],
    warnings: [],
  },
  {
    id: 'insider',
    emoji: '🕵️',
    short: '內部人雷達',
    title: '內部人追蹤雷達 — SEC Form 4 交易代碼解讀',
    summary: '追蹤美股公司內部人（董事/高管/大股東）依 SEC 規定申報的買賣紀錄，快速辨識哪些公司有人「自掏腰包」或大量出貨。',
    howTo: [
      '選擇 <b>觀察區間</b>（7 / 30 / 60 / 90 天），再選 <b>排序方式</b>，頁面自動更新 Top 20 異動名單。',
      '先看「<b>公開買入最多 (P)</b>」——這是最有意義的看多訊號。',
      '搭配「<b>淨買入最多</b>」確認整體公司內部人的淨方向。',
    ],
    howRead: [
      '<span style="color:#22c55e"><b>🟢 P（Purchase）</b></span>：公開市場自掏腰包買入，是最強看多訊號。內部人願意用自己的錢在市場上買，代表對公司前景有信心。',
      '<span style="color:#ef4444"><b>🔴 S（Sale）</b></span>：公開市場賣出，看空訊號，但原因多樣（多角化、流動性需求等），需配合其他因素判斷。',
      '<span style="color:#e5c07b"><b>🟡 M+S（行權套現）</b></span>：行使選擇權後立即賣出，屬計畫性財務安排，<b>中性訊號，不是看空</b>。',
      '<span style="color:#6b7280"><b>⚫ F（稅務代售）</b></span>：強制賣股抵繳稅款（如限制性股票解鎖），<b>中性訊號，不是看空</b>。',
      '<b>淨買入 = P − S</b>：正值 = 整體看多，負值 = 整體看空；<b>不含 M+S 與 F</b>（不計算中性交易）。',
      '<b>人數</b>：有多少位內部人在此窗口內有交易；人數越多、方向越一致，訊號越強。',
    ],
    warnings: [
      '單筆內部人賣出不代表看空，但多人同步賣出（S 佔主導）值得警惕。',
      '資料每日從 SEC EDGAR 背景累積；首次啟動需幾分鐘暖機，「✓ 已累積 XX 筆」出現後才完整。',
    ],
  },
  {
    id: 'market-watch',
    emoji: '🔭',
    short: '市場觀察',
    title: '市場觀察 — The Kings / Rising Stars / Macro Compass',
    summary: '三大戰情儀表板：最強龍頭清單、動能加速新星、以及板塊龍頭間的 Granger 因果資金傳導網絡。',
    howTo: [
      '切換頂部三個 Tab：<b>The Kings</b> / <b>Rising Stars</b> / <b>Macro Compass</b>。',
      '<b>The Kings</b>：找到你關注板塊的 Sub-Industry，看 RS Rank 最高的 1–3 檔；Pullback_Buy ✅ = 此刻是進場窗口。',
      '<b>Rising Stars</b>：找「追動能」或「等回調」欄位都打 ✓ 的標的，入選條件已自動嚴格篩選。',
      '<b>Macro Compass</b>：從「最強資金傳導鏈」看哪個板塊龍頭領先跑，再找該板塊的成分股。',
    ],
    howRead: [
      '<b>RS Rank</b>：20日 / 60日 / 120日 報酬的全市場百分位加權排名；越接近 100 越強。',
      '<b>Pullback_Buy 條件</b>：RSI14 &lt;60（未超買）+ RS 相對強度線 &gt; 50 日均線 + 50 日均線斜率向上。三條件同時滿足 = 最佳的「趨勢中回調買入窗口」。',
      '<b>Rising Stars 入選門檻</b>：20R &gt; 60R &gt; 120R（短中長期動能多頭排列）+ 加速度 ≥30 + 20R ≥75。高標準篩選。',
      '<b>Granger 因果矩陣（Macro Compass）</b>：矩陣「行→列」= 資金傳導方向；顏色越深綠 = 統計因果越顯著（p值越小）；可識別「哪個板塊龍頭先動、其他板塊後跟進」的資金輪動規律。',
    ],
    warnings: [],
  },
  {
    id: 'models',
    emoji: '🤖',
    short: '交易模型',
    title: '交易模型 — Alpha 趨勢大腦 + Genesis 創世紀大腦',
    summary: '兩套 LightGBM 機器學習模型（Optuna 調優）每日輸出狙擊名單。Alpha 鎖定趨勢股，Genesis 鎖定底部爆發股。含「時光機」查歷史戰報。',
    howTo: [
      '<b>時光機下拉</b>：選「🔥 最新戰報」看今日輸出；或選歷史日期回溯任一天的模型輸出。',
      '切換 <b>Alpha</b> / <b>Genesis</b> Tab 在兩個引擎間切換。',
      '用 <b>市值級別</b> 下拉過濾（Mega / Large / Mid / Small / Micro / 全部），聚焦你習慣操作的市值帶。',
      '按 <b>📥 下載戰報 CSV</b> 匯出當前名單。',
    ],
    howRead: [
      '<b>Alpha 趨勢大腦</b>：目標 = 鎖定早期上升趨勢，捕捉 10% 以上的波段；偏向趨勢跟隨，需搭配帶量突破確認。',
      '<b>Genesis 創世紀大腦</b>：目標 = 極度收縮後的底部爆發；高風險高報酬，歷史勝率約 22%，但當勝時賠率高。',
      '<b>Resonance_Score（共振分）</b>：模型綜合打分 0–100；越高代表多個技術因子同步共振。',
      '<b>戰況速覽</b>：當日狙擊數 / 最高共振分 / 平均勝率——快速了解今日市場環境（狙擊數多 = 市場機會豐富；少 = 市場收縮）。',
    ],
    warnings: [
      'Win_Prob 是模型的相對信心，<b>非真實歷史勝率</b>，不可直接用來估算資金管理。',
      'Genesis 連敗期間每筆嚴格控制 ≤2% 總資金，避免連敗拖垮帳戶。',
    ],
  },
  {
    id: 'small-cap',
    emoji: '💰',
    short: '小市值策略',
    title: '小市值策略 — 雙池選股計分卡（L3）',
    summary: '針對 $150M–$20B 市值美股的事件驅動選股系統。每日夜間自動運算，左池捕捉底部拐頭，右池追蹤動能強勢股，並透過 L3 計分卡對各因子打分。',
    howTo: [
      '切換 <b>⬅ 左池（初期底部）</b> / <b>➡ 右池（右側動能）</b> Tab。',
      '先看 <b>✅ 候選清單</b>（Gate 通過 + 無否決旗標）= 可行動清單。',
      '再看 <b>👀 池內觀察</b>（等待催化劑落地或 Gate 尚未達標）= 持續追蹤清單。',
      '點任一 ticker 列 → 展開該標的近 90 天的 <b>事件流</b>（8-K 公告 + Form 4 申報），可看原始 SEC 申報連結。',
    ],
    howRead: [
      '<b>Total Score（總分 0–100）</b>：六因子加權總分，越高越強。',
      '<b>六因子說明</b>：',
      '&nbsp;&nbsp;• <b>catalyst（催化劑）</b>：近期重大公告的強度與確定性（8-K 事件品質）。',
      '&nbsp;&nbsp;• <b>institution（機構新進）</b>：本季 13F 申報中新進持有的機構數量（季度更新，有 45 天延遲）。',
      '&nbsp;&nbsp;• <b>op_leverage（營運槓桿）</b>：營收增速與毛利率擴張的組合訊號。',
      '&nbsp;&nbsp;• <b>partner（戰略夥伴）</b>：公告中涉及大廠合作、客戶贏單的加分。',
      '&nbsp;&nbsp;• <b>insider（內部人買入）</b>：Form 4 淨買入強度（90 日內，按市值歸一化）。',
      '&nbsp;&nbsp;• <b>narrative（主題敘事）</b>：LLM 分析公告主題與當前市場熱點的契合度。',
      '<b>Gate（資格閘門）</b>：左池需 catalyst specificity ≥4 + 事件 timeline ≤6 個月；右池需 specificity ≥3。Gate 嚴格，候選清單常空 = 設計行為，不是資料問題。',
      '<b>Veto（否決旗標，紅色）</b>：任何一個旗標亮紅即排除——常見 veto：稀釋性融資（Toxic Dilution）、現金不足（Cash Runway）、流動性差（Low Liquidity）、誠信問題（Integrity）。Veto 有時間窗（180天 / 365天），到期自動解除。',
      '<b>事件流中的 specificity</b>：1–5 分，代表 LLM 對此事件分析的確定性；5 = 非常具體可驗證的承諾，1 = 模糊公告。',
      '<b>事件流中的 direction</b>：🟢 看多 / 🔴 看空 / 🟡 中性。',
    ],
    warnings: [
      'institution 因子（機構持倉）季度更新，資料有 45 天申報延遲，反映約 1.5–4.5 個月前的持倉。',
      '左池候選清單嚴格（specificity ≥4 稀有），長期為空是正常現象，不代表系統有問題。',
      '系統每晚 UTC 22:00（台灣時間 06:00）自動更新，日間資料為前一日結果。',
    ],
  },
]

// 預設全部展開
const opened = reactive(Object.fromEntries(SECTIONS.map((s) => [s.id, true])))

function toggle(id) {
  opened[id] = !opened[id]
}
</script>

<style scoped>
.guide {
  max-width: 860px;
  margin: 0 auto;
  padding: 32px 24px 64px;
}

/* 頁首 */
.guide-header { margin-bottom: 24px; }
.guide-header h1 { font-size: 28px; margin: 0 0 8px; }
.guide-sub { color: var(--color-text-secondary); font-size: 14px; margin: 0 0 6px; }
.guide-date { color: var(--color-text-muted); font-size: 12px; }

/* 快速導覽 */
.toc {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 12px 16px;
  margin-bottom: 28px;
}
.toc-label { color: var(--color-text-muted); font-size: 12px; margin-right: 4px; flex-shrink: 0; }
.toc-link {
  color: var(--color-text-secondary);
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 20px;
  background: var(--color-bg-raised);
  border: 1px solid var(--color-border);
  white-space: nowrap;
  text-decoration: none;
  transition: color 0.1s, border-color 0.1s;
}
.toc-link:hover { color: var(--color-accent); border-color: var(--color-accent); }

/* Accordion */
.accordion {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  margin-bottom: 12px;
  overflow: hidden;
}

.acc-head {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: var(--color-bg-surface);
  border: none;
  cursor: pointer;
  text-align: left;
  transition: background 0.1s;
}
.acc-head:hover { background: var(--color-bg-raised); }

.acc-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.acc-arrow {
  color: var(--color-text-muted);
  font-size: 11px;
  transform: rotate(-90deg);
  transition: transform 0.2s;
  flex-shrink: 0;
}
.acc-arrow.open { transform: rotate(0deg); }

.acc-body {
  padding: 20px 24px 24px;
  background: var(--color-bg-base, #0a0e1a);
  border-top: 1px solid var(--color-border);
}

.acc-summary {
  color: var(--color-text-secondary);
  font-size: 14px;
  line-height: 1.7;
  margin: 0 0 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--color-border);
}

/* 子區塊 */
.sub-block { margin-bottom: 20px; }
.sub-block:last-child { margin-bottom: 0; }

.sub-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--color-accent);
  margin: 0 0 10px;
  letter-spacing: 0.03em;
}

.sub-block ul {
  margin: 0;
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.sub-block li {
  color: var(--color-text-secondary);
  font-size: 13.5px;
  line-height: 1.65;
}

/* warn sub-block */
.warn {
  background: rgba(245, 158, 11, 0.07);
  border: 1px solid rgba(245, 158, 11, 0.25);
  border-radius: var(--radius-md);
  padding: 14px 18px;
}
.warn .sub-title { color: #f59e0b; }
.warn li { color: #fbbf24; }

/* inline code */
:deep(code) {
  font-family: var(--font-mono, monospace);
  background: var(--color-bg-raised);
  color: var(--color-accent);
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 12px;
}

/* responsive */
@media (max-width: 640px) {
  .guide { padding: 20px 14px 48px; }
  .toc { display: none; }
  .acc-head { padding: 14px 16px; }
  .acc-body { padding: 16px 16px 20px; }
  .acc-title { font-size: 14px; }
}
</style>
