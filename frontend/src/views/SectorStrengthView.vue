<!--
  SectorStrengthView.vue — 美股板塊強弱 (/sector-strength)
  對應 Streamlit data_engine/market/strength.py · plot_chart() Tab1
  RS 相對強度線 + 動能熱力圖 + 板塊總覽表(含迷你線) + 策略 A/B/C 掃描
-->
<template>
  <div class="ss-view">
    <header class="ss-head">
      <h1>🧭 美股板塊強弱</h1>
      <span v-if="store.overview?.as_of" class="asof mono">資料日期 {{ store.overview.as_of }}</span>
    </header>

    <div v-if="store.loading" class="ph">初始化全市場動能數據…</div>
    <div v-else-if="store.error" class="alert">⚠️ {{ store.error }}</div>

    <template v-else-if="store.overview">
      <!-- ① 相對強度線圖 -->
      <section class="block">
        <h2>📈 板塊相對強度 (vs VTI)</h2>
        <div class="chips">
          <button
            v-for="t in tickerOptions"
            :key="t"
            class="chip"
            :class="{ on: selectedTickers.includes(t) }"
            @click="toggleTicker(t)"
          >
            {{ t }}
          </button>
        </div>
        <TimeSeriesChart v-if="rsOption" :option="rsOption" :height="420" />
        <p v-else class="hint">請至少選擇一個板塊。</p>
      </section>

      <!-- ② 動能熱力圖 -->
      <section class="block">
        <h2>🟩 板塊資金動能輪動 (Heatmap)</h2>
        <div class="range-bar">
          <button
            v-for="opt in PERIODS"
            :key="opt.value"
            class="range-btn"
            :class="{ active: opt.value === activePeriod }"
            @click="selectPeriod(opt.value)"
          >
            {{ opt.label }}
          </button>
        </div>
        <Treemap v-if="store.heatmap" :items="store.heatmap.items" :height="520" />
      </section>

      <!-- ③ 板塊總覽表 (點擊列 → 鑽取成分股) -->
      <section class="block">
        <h2>📋 全板塊總覽</h2>
        <p class="hint">含 20R/60R/120R 排名、相對大盤表現 (REL5/REL20) 與 60 日走勢。🔥 = 黃金伏擊條件。👉 點擊任一列可即時鑽取該 ETF 成分股。</p>
        <DataTable :columns="overviewCols" :rows="store.overview.items" row-key="ticker" clickable @row-click="drilldown">
          <template #cell-trend="{ value }">
            <Sparkline :data="value" :width="90" :height="24" />
          </template>
        </DataTable>
      </section>

      <!-- ③b 成分股鑽取 (yfinance on-demand) -->
      <section v-if="store.holdingsLoading || store.holdings || store.holdingsError" class="block drill">
        <h2>🧬 成分股即時掃描<span v-if="selectedEtf"> — {{ selectedEtf }}</span></h2>
        <div v-if="store.holdingsLoading" class="ph">正在即時計算 {{ selectedEtf }} 成分股動能指標（首次約需數秒）…</div>
        <div v-else-if="store.holdingsError" class="alert">⚠️ {{ store.holdingsError }}</div>
        <template v-else-if="store.holdings">
          <p v-if="!store.holdings.holdings_count" class="hint">{{ selectedEtf }} 無成分股資料 (etf_holdings.json 未收錄)。</p>
          <template v-else>
            <h3>🔥 黃金伏擊清單 (Golden Ambush)</h3>
            <p v-if="store.holdings.golden.length" class="warn-note">💡 紀律提醒：進場後絕對止損設於買入價下方 2.0×ATR，單筆持倉勿超過總資金 12.5%。</p>
            <DataTable v-if="store.holdings.golden.length" :columns="holdingsCols" :rows="store.holdings.golden" row-key="ticker">
              <template #cell-trend="{ value }"><Sparkline :data="value" :width="90" :height="24" /></template>
            </DataTable>
            <p v-else class="hint">目前 {{ selectedEtf }} 成分股內無標的符合完美進場條件。</p>

            <h3>🔍 {{ selectedEtf }} 全成分股總覽 ({{ store.holdings.holdings_count }} 檔)</h3>
            <DataTable :columns="holdingsCols" :rows="store.holdings.all" row-key="ticker">
              <template #cell-trend="{ value }"><Sparkline :data="value" :width="90" :height="24" /></template>
            </DataTable>
          </template>
        </template>
      </section>

      <!-- ④ 策略掃描 -->
      <section class="block">
        <h2>🎯 多週期量化信號掃描</h2>
        <div v-for="s in STRATEGIES" :key="s.key" class="strat">
          <h3>{{ s.label }}</h3>
          <DataTable
            v-if="store.overview.strategies[s.key].length"
            :columns="stratCols"
            :rows="store.overview.strategies[s.key]"
            row-key="ticker"
          >
            <template #cell-trend="{ value }"><Sparkline :data="value" :width="80" :height="22" /></template>
          </DataTable>
          <p v-else class="hint">目前無標的符合此條件。</p>
        </div>
      </section>

      <NotesPanel category="market" module="strength" />
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useSectorStrengthStore } from '@/stores/sectorStrength'
import DataTable from '@/components/ui/DataTable.vue'
import TimeSeriesChart from '@/components/charts/TimeSeriesChart.vue'
import Treemap from '@/components/charts/Treemap.vue'
import Sparkline from '@/components/charts/Sparkline.vue'
import NotesPanel from '@/components/ui/NotesPanel.vue'
import { recessionMarkArea } from '@/lib/recessions'

const store = useSectorStrengthStore()

const PERIODS = [
  { label: '1天', value: 1 },
  { label: '3天', value: 3 },
  { label: '1週', value: 5 },
  { label: '1個月', value: 20 },
  { label: '3個月', value: 60 },
]
const STRATEGIES = [
  { key: 'a', label: '🔥 策略 A：動態點火 (VCP 動態突破)' },
  { key: 'b', label: '💎 策略 B：動態錯殺 (乖離過大反彈)' },
  { key: 'c', label: '⚠️ 策略 C：波段破壞 (避險與資金撤出)' },
]
const PALETTE = ['#3b82f6', '#10b981', '#fbbf24', '#ef4444', '#22d3ee', '#a855f7', '#f97316', '#ec4899']

const activePeriod = ref(20)
const selectedTickers = ref([])
const selectedEtf = ref(null)

// ── 顏色輔助 ──
const signedColor = (v) => (v > 0 ? 'var(--color-bull)' : v < 0 ? 'var(--color-bear)' : '')
const rsiColor = (v) => (v > 70 ? 'var(--color-bear)' : v < 30 ? 'var(--color-bull)' : '')
const n = (v, d = 2) => (v === null || v === undefined ? '—' : Number(v).toFixed(d))
const signed = (v, d = 2) => (v === null || v === undefined ? '—' : `${v >= 0 ? '+' : ''}${Number(v).toFixed(d)}`)

const tickerOptions = computed(() => (store.overview?.items ?? []).map((i) => i.ticker).sort())

const overviewCols = [
  { key: 'signal', label: '訊號', align: 'center' },
  { key: 'group', label: '所屬板塊', align: 'left', mono: false },
  { key: 'ticker', label: 'Ticker', align: 'left' },
  { key: 'name', label: '標的名稱', align: 'left', mono: false },
  { key: 'price', label: 'Price', align: 'right', format: (v) => n(v) },
  { key: 'ret1', label: '1D%', align: 'right', format: (v) => signed(v), color: signedColor },
  { key: 'trend', label: '60D 走勢', align: 'center' },
  { key: 'r20', label: '20R', align: 'right', format: (v) => n(v, 0) },
  { key: 'r60', label: '60R', align: 'right', format: (v) => n(v, 0) },
  { key: 'r120', label: '120R', align: 'right', format: (v) => n(v, 0) },
  { key: 'total_rank', label: 'Rank', align: 'right', format: (v) => n(v, 1), color: () => 'var(--color-data-gold)' },
  { key: 'rel5', label: 'REL5', align: 'right', format: (v) => signed(v), color: signedColor },
  { key: 'rel20', label: 'REL20', align: 'right', format: (v) => signed(v), color: signedColor },
  { key: 'rsi', label: '14D RSI', align: 'right', format: (v) => n(v, 1), color: rsiColor },
]

const holdingsCols = [
  { key: 'signal', label: '訊號', align: 'center' },
  { key: 'ticker', label: 'Ticker', align: 'left' },
  { key: 'name', label: '名稱', align: 'left', mono: false },
  { key: 'price', label: 'Price', align: 'right', format: (v) => n(v) },
  { key: 'ret1', label: '1D%', align: 'right', format: (v) => signed(v), color: signedColor },
  { key: 'trend', label: '60D 走勢', align: 'center' },
  { key: 'total_rank', label: 'Rank', align: 'right', format: (v) => n(v, 1), color: () => 'var(--color-data-gold)' },
  { key: 'rel5', label: 'REL5', align: 'right', format: (v) => signed(v), color: signedColor },
  { key: 'rel20', label: 'REL20', align: 'right', format: (v) => signed(v), color: signedColor },
  { key: 'rsi', label: 'RSI', align: 'right', format: (v) => n(v, 1), color: rsiColor },
  { key: 'atr_pct', label: 'ATR%', align: 'right', format: (v) => n(v) },
]

const stratCols = [
  { key: 'ticker', label: '代號', align: 'left' },
  { key: 'name', label: '名稱', align: 'left', mono: false },
  { key: 'price', label: '最新價格', align: 'right', format: (v) => n(v) },
  { key: 'trend', label: '60D 走勢', align: 'center' },
  { key: 'atr_pct', label: 'ATR%', align: 'right', format: (v) => n(v) },
  { key: 'r20', label: '20D排名(PR)', align: 'right', format: (v) => n(v, 0) },
  { key: 'ret10', label: '10D漲跌%', align: 'right', format: (v) => signed(v), color: signedColor },
  { key: 'ret3', label: '3D點火%', align: 'right', format: (v) => signed(v), color: signedColor },
]

const rsOption = computed(() => {
  const series = store.rs?.series ?? []
  if (!series.length) return null
  return {
    yAxis: {
      type: 'value',
      name: 'Relative Strength',
      nameTextStyle: { color: '#94a3b8' },
      axisLabel: { color: '#94a3b8', formatter: '{value}' },
      splitLine: { lineStyle: { color: '#1f2d40', opacity: 0.4 } },
    },
    series: series.map((s, i) => ({
      name: `${s.ticker}/VTI`,
      type: 'line',
      showSymbol: false,
      data: s.data,
      lineStyle: { color: PALETTE[i % PALETTE.length], width: 1.8 },
      itemStyle: { color: PALETTE[i % PALETTE.length] },
      ...(i === 0 ? { markArea: recessionMarkArea([['2007-12-01', '2009-06-30'], ['2020-02-01', '2020-04-30']]) } : {}),
    })),
  }
})

function toggleTicker(t) {
  const idx = selectedTickers.value.indexOf(t)
  if (idx >= 0) selectedTickers.value.splice(idx, 1)
  else selectedTickers.value.push(t)
  store.fetchRelativeStrength(selectedTickers.value)
}

function selectPeriod(p) {
  activePeriod.value = p
  store.fetchHeatmap(p)
}

function drilldown(row) {
  selectedEtf.value = row.ticker
  store.fetchHoldings(row.ticker)
  // 捲動到鑽取區
  setTimeout(() => document.querySelector('.drill')?.scrollIntoView({ behavior: 'smooth' }), 100)
}

onMounted(async () => {
  await store.fetchOverview()
  // 預設選前 5 檔做 RS、載入熱力圖
  selectedTickers.value = tickerOptions.value.slice(0, 5)
  store.fetchRelativeStrength(selectedTickers.value)
  store.fetchHeatmap(activePeriod.value)
})
</script>

<style scoped>
.ss-view { padding: 28px; max-width: 1360px; margin: 0 auto; }
.ss-head { display: flex; align-items: baseline; gap: 14px; margin-bottom: 20px; }
.ss-head h1 { font-size: 22px; margin: 0; }
.asof { color: var(--color-text-muted); font-size: 12px; }
.block { margin-bottom: 36px; }
.block h2 { font-size: 16px; margin: 0 0 12px; }
.block h3 { font-size: 13px; margin: 18px 0 8px; color: var(--color-text-secondary); }
.hint { color: var(--color-text-muted); font-size: 12px; margin: 6px 0; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
.chip {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-family: var(--font-mono);
  cursor: pointer;
}
.chip.on { background: var(--color-accent); border-color: var(--color-accent); color: #fff; }
.range-bar { display: flex; gap: 6px; margin-bottom: 12px; flex-wrap: wrap; }
.range-btn {
  background: transparent;
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  padding: 5px 12px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  cursor: pointer;
}
.range-btn.active { background: var(--color-bg-raised); color: var(--color-text-primary); border-color: var(--color-accent); }
.ph { color: var(--color-text-muted); padding: 40px 0; }
.alert {
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid var(--color-warning);
  color: var(--color-warning);
  padding: 14px 18px;
  border-radius: var(--radius-md);
}
.strat { margin-bottom: 8px; }
.drill { border-top: 1px solid var(--color-border); padding-top: 20px; }
.warn-note {
  background: rgba(245, 158, 11, 0.08);
  border-left: 3px solid var(--color-warning);
  color: var(--color-warning);
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  margin: 6px 0 12px;
}
</style>
