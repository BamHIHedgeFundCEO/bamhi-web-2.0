<!--
  SearchView.vue — 個股深度搜尋 (/search?q=TICKER)
  對應 Streamlit views/search_view.py
  價格/估值 + 參數(區間/K線級別) + Tabs(技術線圖 / 基本資料 / 財務報表)
-->
<template>
  <div class="sv">
    <RouterLink :to="{ name: 'home' }" class="back">← 返回首頁</RouterLink>

    <!-- 參數 -->
    <div class="params">
      <label>📅 歷史區間
        <select v-model="period" @change="reload"><option v-for="p in PERIODS" :key="p" :value="p">{{ p }}</option></select>
      </label>
      <label>⏱️ K線級別
        <select v-model="interval" @change="reload">
          <option value="1h">1小時線</option><option value="1d">日線</option><option value="1wk">週線</option>
        </select>
      </label>
    </div>

    <div v-if="store.loading" class="ph">正在全網掃描 {{ ticker }} 的深度數據…</div>
    <div v-else-if="store.error" class="alert">⚠️ {{ store.error }}</div>

    <template v-else-if="p">
      <!-- 標題 + 價格 -->
      <h1 class="title">{{ p.company_name }} <span class="tkr">({{ p.ticker }})</span></h1>
      <div class="price-row" :class="up ? 'up' : 'down'">
        <span class="price">${{ p.price.current.toFixed(2) }}</span>
        <span class="chg">{{ p.price.change >= 0 ? '+' : '' }}{{ p.price.change.toFixed(2) }} ({{ p.price.change_pct >= 0 ? '+' : '' }}{{ p.price.change_pct.toFixed(2) }}%)</span>
      </div>

      <!-- 估值四宮格 -->
      <div class="metrics">
        <MetricCard label="總市值" :value="p.valuation.market_cap_b !== null ? p.valuation.market_cap_b + ' B' : 'N/A'" delta-suffix="" />
        <MetricCard label="本益比 (P/E)" :value="p.valuation.pe ?? 'N/A'" delta-suffix="" />
        <MetricCard label="股價淨值比 (P/B)" :value="p.valuation.pb ?? 'N/A'" delta-suffix="" />
        <MetricCard label="股東權益報酬率 (ROE)" :value="p.valuation.roe_pct !== null ? p.valuation.roe_pct + '%' : 'N/A'" delta-suffix="" />
      </div>

      <!-- 趨勢/訊號 -->
      <div class="info-row">
        <div class="info-chip">趨勢狀態：<b>{{ p.trend_status }}</b></div>
        <div class="info-chip">量化訊號：<b>{{ p.signal_status }}</b>（綜合分數 {{ p.composite }}）</div>
      </div>

      <!-- Tabs -->
      <div class="tabs">
        <button v-for="t in TABS" :key="t.key" class="tab-btn" :class="{ active: t.key === tab }" @click="tab = t.key">{{ t.label }}</button>
      </div>

      <!-- 技術線圖 -->
      <template v-if="tab === 'chart'">
        <CandleChart :dates="p.chart.dates" :candle="p.chart.candle" :mas="p.chart.ma" :log="false" :height="440" />
        <h3>量化綜合分數 (Composite)</h3>
        <TimeSeriesChart :option="compositeOption" :height="220" />
      </template>

      <!-- 基本資料 -->
      <template v-else-if="tab === 'info'">
        <div class="info-grid">
          <div class="info-card">
            <p class="lbl">所屬板塊 (Sector)</p><p class="val">{{ p.sector }}</p>
            <p class="lbl">所屬產業 (Industry)</p><p class="val">{{ p.industry }}</p>
            <p class="lbl">全職員工數</p><p class="val">{{ typeof p.employees === 'number' ? p.employees.toLocaleString() : p.employees }}</p>
            <p v-if="p.website && p.website !== 'N/A'" class="lbl">官網</p>
            <p v-if="p.website && p.website !== 'N/A'" class="val"><a :href="p.website" target="_blank">{{ p.website }}</a></p>
          </div>
          <div class="summary">
            {{ p.summary_zh || p.summary }}
            <p class="src">💡 簡介來源 FMP{{ p.summary_zh ? '｜翻譯 Google Translate' : '（翻譯暫時無法使用，顯示原文）' }}</p>
          </div>
        </div>
      </template>

      <!-- 財務報表 -->
      <template v-else-if="tab === 'finance'">
        <h3>近期財務報表（近四季）</h3>
        <div v-if="p.financials.rows.length" class="fin-wrap">
          <table class="fin">
            <thead><tr><th>指標</th><th v-for="c in p.financials.columns" :key="c">{{ c }}</th></tr></thead>
            <tbody>
              <tr v-for="row in p.financials.rows" :key="row.metric">
                <td class="metric-name">{{ row.metric }}</td>
                <td v-for="c in p.financials.columns" :key="c" class="mono">{{ fmtFin(row.metric, row[c]) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="ph">無法取得損益表資料。</p>
      </template>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { useEquityStore } from '@/stores/equity'
import MetricCard from '@/components/ui/MetricCard.vue'
import CandleChart from '@/components/charts/CandleChart.vue'
import TimeSeriesChart from '@/components/charts/TimeSeriesChart.vue'

const route = useRoute()
const store = useEquityStore()

const PERIODS = ['6mo', '1y', '2y', '5y', '10y', 'max']
const TABS = [
  { key: 'chart', label: '📈 技術線圖' },
  { key: 'info', label: '🏢 基本資料' },
  { key: 'finance', label: '📊 財務報表' },
]

const ticker = ref((route.query.q || '').toString().toUpperCase())
const period = ref('2y')
const interval = ref('1d')
const tab = ref('chart')

const p = computed(() => store.profile)
const up = computed(() => (p.value?.price.change ?? 0) >= 0)

const PCT_ROWS = new Set(['營收年增率 (YoY)', '毛利率 (Gross Margin)', '淨利率 (Net Margin)'])
const MONEY_ROWS = new Set(['營收 (Revenue)', '營運現金流 (Operating CF)', '自由現金流 (Free CF)'])
function fmtFin(metric, v) {
  if (v === null || v === undefined) return 'N/A'
  if (PCT_ROWS.has(metric)) return `${v.toFixed(2)} %`
  if (MONEY_ROWS.has(metric)) return `${v.toLocaleString()} M`
  return v.toFixed(2)
}

const compositeOption = computed(() => ({
  xAxis: { type: 'category', data: p.value?.chart.dates ?? [], axisLabel: { color: '#94a3b8' }, axisLine: { lineStyle: { color: '#1f2d40' } } },
  yAxis: { type: 'value', min: 0, max: 100, axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { color: '#1f2d40', opacity: 0.4 } } },
  grid: { left: 48, right: 20, top: 20, bottom: 30 },
  series: [{
    name: 'Composite', type: 'line', showSymbol: false, data: p.value?.chart.composite ?? [],
    lineStyle: { color: '#22d3ee', width: 2 }, itemStyle: { color: '#22d3ee' },
    markLine: { symbol: 'none', silent: true, data: [
      { yAxis: 75, lineStyle: { color: '#ef4444', type: 'dashed' } },
      { yAxis: 25, lineStyle: { color: '#22c55e', type: 'dashed' } },
    ] },
  }],
}))

function reload() {
  if (ticker.value) store.fetchProfile(ticker.value, period.value, interval.value)
}

// 從導覽列搜尋跳轉時 query 改變要重抓
watch(() => route.query.q, (q) => {
  if (q) { ticker.value = q.toString().toUpperCase(); reload() }
})

onMounted(reload)
</script>

<style scoped>
.sv { padding: 28px; max-width: 1280px; margin: 0 auto; }
.back { display: inline-block; color: var(--color-text-secondary); font-size: 13px; margin-bottom: 16px; }
.back:hover { color: var(--color-accent); }
.params { display: flex; gap: 18px; margin-bottom: 20px; }
.params label { font-size: 12px; color: var(--color-text-secondary); display: flex; flex-direction: column; gap: 6px; }
.params select { background: var(--color-bg-raised); border: 1px solid var(--color-border); color: var(--color-text-primary); padding: 8px 12px; border-radius: var(--radius-md); font-size: 13px; min-width: 140px; }
.title { font-size: 26px; margin: 0 0 4px; }
.tkr { color: var(--color-text-muted); font-size: 18px; }
.price-row { display: flex; align-items: baseline; gap: 14px; margin-bottom: 22px; }
.price { font-size: 38px; font-weight: 700; font-family: var(--font-mono); }
.chg { font-size: 18px; font-weight: 600; font-family: var(--font-mono); }
.price-row.up .price, .price-row.up .chg { color: var(--color-bull); }
.price-row.down .price, .price-row.down .chg { color: var(--color-bear); }
.metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 18px; }
.info-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 24px; }
.info-chip { background: var(--color-bg-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: 10px 14px; font-size: 13px; color: var(--color-text-secondary); }
.info-chip b { color: var(--color-text-primary); }
.tabs { display: flex; gap: 6px; margin-bottom: 18px; border-bottom: 1px solid var(--color-border); padding-bottom: 10px; }
.tab-btn { background: var(--color-bg-surface); border: 1px solid var(--color-border); color: var(--color-text-secondary); padding: 8px 16px; border-radius: var(--radius-md); font-size: 13px; cursor: pointer; }
.tab-btn.active { background: var(--color-accent); border-color: var(--color-accent); color: #fff; }
h3 { font-size: 14px; margin: 22px 0 10px; color: var(--color-text-secondary); }
.info-grid { display: grid; grid-template-columns: 1fr 2fr; gap: 20px; }
.info-card { background: var(--color-bg-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: 16px; }
.info-card .lbl { color: var(--color-text-muted); font-size: 12px; margin: 12px 0 2px; }
.info-card .lbl:first-child { margin-top: 0; }
.info-card .val { color: var(--color-text-primary); font-size: 14px; font-weight: 600; margin: 0; }
.summary { background: var(--color-bg-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: 16px; color: var(--color-text-secondary); font-size: 13px; line-height: 1.7; }
.summary .src { color: var(--color-text-muted); font-size: 11px; margin: 12px 0 0; }
.fin-wrap { overflow-x: auto; border: 1px solid var(--color-border); border-radius: var(--radius-md); }
.fin { width: 100%; border-collapse: collapse; font-size: 13px; }
.fin th { background: var(--color-bg-raised); color: var(--color-text-secondary); padding: 10px 14px; text-align: right; font-size: 11px; border-bottom: 1px solid var(--color-border); }
.fin th:first-child { text-align: left; }
.fin td { padding: 9px 14px; text-align: right; border-bottom: 1px solid var(--color-border-dim); }
.fin .metric-name { text-align: left; color: var(--color-text-secondary); }
.ph { color: var(--color-text-muted); padding: 30px 0; }
.alert { background: rgba(245, 158, 11, 0.1); border: 1px solid var(--color-warning); color: var(--color-warning); padding: 14px 18px; border-radius: var(--radius-md); }
@media (max-width: 800px) { .info-grid { grid-template-columns: 1fr; } }
</style>
