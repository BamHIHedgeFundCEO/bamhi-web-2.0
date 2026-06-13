<!--
  SectorRotationView.vue — 板塊輪動與資金流向監控 (/sector-rotation)
  對應 Streamlit views/sector_rotation.py + _sector_charts.py
  全覽(熱力圖/RRG/軌跡/相關係數) + 單板塊深度(指標/K線/RS/寬度/機構流/動能/VCP)
-->
<template>
  <div class="sr-view">
    <h1>🔄 BamHI 板塊輪動與資金流向監控</h1>
    <p class="sub">結合 5D/20D 動能加速、RS 相對強度與 VCP 籌碼掃描，鎖定市場最強主線。</p>

    <!-- 控制面板 -->
    <div class="ctrl">
      <label>📂 深度掃描板塊
        <select v-model="sector" @change="loadDetail">
          <option v-for="s in store.sectors" :key="s.name" :value="s.name">{{ s.name }}</option>
        </select>
      </label>
      <label>📅 歷史區間
        <select v-model="period" @change="reloadAll">
          <option v-for="p in PERIODS" :key="p" :value="p">{{ p }}</option>
        </select>
      </label>
    </div>
    <p v-if="currentSector" class="watchlist">
      <b>追蹤清單：</b>
      <span v-for="t in currentSector.tickers" :key="t" :class="{ leader: currentSector.leaders.includes(t) }">
        {{ currentSector.leaders.includes(t) ? '⭐' + t : t }}
      </span>
    </p>

    <!-- 全覽 tabs -->
    <section class="block">
      <div class="tabs">
        <button v-for="t in OVERVIEW_TABS" :key="t.key" class="tab-btn" :class="{ active: t.key === overviewTab }" @click="overviewTab = t.key">{{ t.label }}</button>
      </div>

      <div v-if="store.overviewLoading" class="ph">正在批量下載全市場資料並計算（首次較久）…</div>
      <div v-else-if="!store.overview" class="alert">⚠️ {{ store.error || '尚無全覽資料' }}</div>
      <template v-else>
        <template v-if="overviewTab === 'heatmap'">
          <p class="hint">方塊大小一致、顏色代表動能差值 (M10 − M20)：綠＝短線動能加速，紅＝動能轉弱。👉 點任一板塊即跳轉下方深度分析。</p>
          <Treemap :items="heatmapItems" :height="520" @select="onHeatmapSelect" />
        </template>
        <RrgChart v-show="overviewTab === 'rrg'" :points="store.overview.rrg" mode="snapshot" :height="560" @select="onSectorPick" />
        <template v-if="overviewTab === 'trail'">
          <div class="note">
            💡 <b>軌跡資料說明</b>：軌跡由 <code>RS_Ratio</code>（滾動 14 日均線 ÷ 50 日均線）及
            <code>RS_Momentum</code>（RS_Ratio 的 14 日動能）計算，需至少 <b>50 個交易日</b>以上的歷史才能產生完整軌跡。
            若軌跡過短，請把上方 📅 歷史區間調到 <b>2y 以上</b>。終點＝最新位置，起點＝N 天前；可滾輪縮放。
          </div>
          <div class="range-bar">
            <span class="hint">軌跡天數</span>
            <button v-for="d in [5, 10, 15, 20]" :key="d" class="range-btn" :class="{ active: d === trailDays }" @click="trailDays = d">{{ d }}天</button>
          </div>
          <RrgChart :points="store.overview.rrg_trail" mode="trail" :trail-days="trailDays" :height="580" @select="onSectorPick" />
        </template>
        <CorrHeatmap v-show="overviewTab === 'corr'" v-if="store.overview.correlation" :labels="store.overview.correlation.labels" :matrix="store.overview.correlation.matrix" :height="560" />
      </template>
    </section>

    <!-- 單板塊深度 -->
    <section class="block" id="sector-detail">
      <h2>🔥 {{ sector }} 資金動能與擁擠度概況</h2>
      <div v-if="store.detailLoading" class="ph">計算 {{ sector }} 詳細動能與 VCP 訊號…</div>
      <div v-else-if="!detail || !detail.found" class="alert">⚠️ 資料獲取失敗。</div>
      <template v-else>
        <!-- 7 指標 -->
        <div class="metrics">
          <MetricCard label="今日漲跌幅" :value="m.daily_pct" :delta="m.daily_pct" format="percent" />
          <MetricCard label="5日極速動能" :value="m.m5" format="percent" />
          <MetricCard label="10日波段動能" :value="m.m10" format="percent" />
          <MetricCard label="20日中線動能" :value="m.m20" format="percent" />
          <MetricCard label="動能差值(M10-M20)" :value="m.momentum_diff" :delta="m.momentum_diff" />
          <MetricCard label="RS線5日斜率" :value="m.rs_slope_pct" :delta="m.rs_slope_pct" format="percent" />
          <MetricCard label="資金佔大盤均量比" :value="m.crowd" format="percent" :delta="m.overheated ? -1 : null" delta-suffix="" />
        </div>

        <!-- RRG 象限 -->
        <div v-if="m.quadrant" class="quad" :style="{ borderColor: m.quadrant.color }">
          <span :style="{ color: m.quadrant.color, fontWeight: 700 }">{{ m.quadrant.label }}</span>
          <span class="quad-desc">RS-Ratio: {{ m.rs_ratio }}｜RS-Momentum: {{ m.rs_momentum }}｜{{ m.quadrant.desc }}</span>
        </div>

        <!-- 狀態警報 -->
        <div class="status" :class="m.status.level">{{ m.status.text }}</div>

        <!-- K 線 -->
        <div class="chart-head">
          <h3>📊 {{ sector }} 綜合圖表 (K線 + 均線)</h3>
          <label class="logtoggle"><input type="checkbox" v-model="logScale" /> 對數座標</label>
        </div>
        <CandleChart :dates="c.dates" :candle="c.candle" :mas="masObj" :log="logScale" :height="460" />

        <h3>📈 {{ sector }} vs SPY（同基準指數化）</h3>
        <TimeSeriesChart :option="vsSpyOption" :height="280" />

        <h3>🧭 RS Line（相對強度，基準 = 1.0）</h3>
        <TimeSeriesChart :option="rsLineOption" :height="240" />

        <h3>📐 板塊寬度（成分股 > MA20 %）</h3>
        <div class="chart-row">
          <aside class="side">
            <div class="side-val">{{ breadth.val }}<span class="unit">%</span></div>
            <div class="side-status" :style="{ color: breadth.color }">{{ breadth.status }}</div>
            <div class="side-guide">
              📌 讀法：<br />≥ 80% = 超買過熱<br />20–80% = 健康<br />≤ 20% = 超賣注意
            </div>
          </aside>
          <div class="chart-main"><TimeSeriesChart :option="breadthOption" :height="260" /></div>
        </div>

        <h3>🐳 機構資金流向（Up/Down Dollar Volume Ratio）</h3>
        <div class="chart-row">
          <aside class="side">
            <div class="side-lbl">機構吃貨強度</div>
            <div class="side-val">{{ ud.val }}<span class="unit">x</span></div>
            <div class="side-status" :style="{ color: ud.color }">{{ ud.status }}</div>
            <div class="side-desc">{{ ud.desc }}</div>
            <div class="side-guide">
              📌 讀法：<br />&gt; 1.5x = 機構建倉<br />1.0–1.5x = 偏多<br />0.9–1.0x = 中性<br />&lt; 0.9x = 派發出貨
            </div>
          </aside>
          <div class="chart-main"><TimeSeriesChart :option="udDvOption" :height="280" /></div>
        </div>

        <h3>📊 動能三線（M5 / M10 / M20）</h3>
        <div class="chart-row">
          <aside class="side">
            <div class="side-lbl">動能狀態</div>
            <div class="side-val" :style="{ color: mom.color }">M10 {{ mom.m10 }}<span class="unit">%</span></div>
            <div class="side-status" :style="{ color: mom.color }">{{ mom.status }}</div>
            <div class="side-desc">M5: {{ mom.m5 }}%　M20: {{ mom.m20 }}%</div>
            <div class="side-guide">
              🔺 黃金交叉 = M10 上穿 M20（波段動能確立）<br />
              🔻 死亡交叉 = M10 下穿 M20（動能衰減）
            </div>
          </aside>
          <div class="chart-main"><TimeSeriesChart :option="momentumOption" :height="280" /></div>
        </div>

        <!-- VCP -->
        <h3>🎯 {{ sector }} 內部 VCP 掃描器</h3>
        <p class="hint">尋找趨勢向上、出現波動收縮與成交量枯竭的標的。</p>
        <DataTable v-if="detail.vcp.length" :columns="vcpCols" :rows="vcpRows" row-key="ticker">
          <template #cell-trend="{ value }"><Sparkline :data="value" :width="80" :height="22" /></template>
        </DataTable>
        <p v-else class="hint">目前板塊內無符合 VCP 嚴格條件的標的。</p>
      </template>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useSectorRotationStore } from '@/stores/sectorRotation'
import MetricCard from '@/components/ui/MetricCard.vue'
import DataTable from '@/components/ui/DataTable.vue'
import Treemap from '@/components/charts/Treemap.vue'
import RrgChart from '@/components/charts/RrgChart.vue'
import CorrHeatmap from '@/components/charts/CorrHeatmap.vue'
import CandleChart from '@/components/charts/CandleChart.vue'
import TimeSeriesChart from '@/components/charts/TimeSeriesChart.vue'
import Sparkline from '@/components/charts/Sparkline.vue'

const store = useSectorRotationStore()
const route = useRoute()

const PERIODS = ['6mo', '1y', '2y', '5y', '10y', 'max']
const OVERVIEW_TABS = [
  { key: 'heatmap', label: '🗺️ 動能熱力圖' },
  { key: 'rrg', label: '📡 RRG 輪動圖' },
  { key: 'trail', label: '📈 RRG 軌跡' },
  { key: 'corr', label: '🔗 相關係數' },
]

const sector = ref('')
const period = ref('2y')
const overviewTab = ref('heatmap')
const trailDays = ref(10)
const logScale = ref(true)

const detail = computed(() => store.detail)
const m = computed(() => store.detail?.metrics ?? {})
const c = computed(() => store.detail?.chart ?? { dates: [] })
const currentSector = computed(() => store.sectors.find((s) => s.name === sector.value))
const masObj = computed(() => ({ MA10: c.value.ma10, MA20: c.value.ma20, MA60: c.value.ma60, MA120: c.value.ma120, MA200: c.value.ma200 }))

// 動能熱力圖：後端回傳是各板塊扁平清單 → 轉成 Treemap 需要的格式
const heatmapItems = computed(() =>
  (store.overview?.heatmap ?? []).map((h) => ({
    ticker: h.short, name: h.sector, group: '板塊動能熱力',
    price: 0, chg_pct: h.momentum_diff, score: h.score,
  })),
)

// ── 三圖側欄：最新數值 + 狀態 ──
const lastVal = (arr) => {
  if (!arr) return null
  for (let i = arr.length - 1; i >= 0; i--) if (arr[i] !== null && arr[i] !== undefined) return arr[i]
  return null
}
const breadth = computed(() => {
  const v = lastVal(c.value.breadth)
  if (v === null) return { val: '—', status: '無資料', color: 'var(--color-neutral)' }
  if (v >= 80) return { val: v.toFixed(1), status: '⚠️ 超買過熱', color: 'var(--color-bear)' }
  if (v <= 20) return { val: v.toFixed(1), status: '🔍 超賣注意', color: 'var(--color-bull)' }
  return { val: v.toFixed(1), status: '✅ 水位健康', color: 'var(--color-bull)' }
})
const ud = computed(() => {
  const v = lastVal(c.value.ud_dv)
  if (v === null) return { val: '—', status: '無資料', desc: '', color: 'var(--color-neutral)' }
  let status, desc, color
  if (v >= 1.5) { status = '🐳 強力建倉'; desc = '大戶積極吸籌，上漲日資金遠超下跌日'; color = '#22c55e' }
  else if (v >= 1.1) { status = '📈 溫和建倉'; desc = '資金偏買方，有機構逢低承接跡象'; color = '#86efac' }
  else if (v >= 0.9) { status = '⚖️ 多空平衡'; desc = '買賣力道接近，方向不明，等待突破'; color = '#9ca3af' }
  else if (v >= 0.7) { status = '📉 溫和派發'; desc = '下跌日資金略多，注意獲利了結壓力'; color = '#fca5a5' }
  else { status = '🚨 強力派發'; desc = '下跌日資金遠超上漲日，機構可能出貨'; color = '#ef4444' }
  return { val: v.toFixed(2), status, desc, color }
})
const mom = computed(() => {
  const m5 = lastVal(c.value.m5_s), m10 = lastVal(c.value.m10_s), m20 = lastVal(c.value.m20_s)
  let status = '⚖️ 多空拉鋸', color = 'var(--color-neutral)'
  if (m10 !== null && m20 !== null) {
    if (m10 > 0 && m10 > m20) { status = '🔺 波段轉強'; color = 'var(--color-bull)' }
    else if (m10 < 0 && m10 < m20) { status = '🔻 波段衰減'; color = 'var(--color-bear)' }
  }
  return { m5: m5 === null ? '—' : m5.toFixed(1), m10: m10 === null ? '—' : m10.toFixed(1), m20: m20 === null ? '—' : m20.toFixed(1), status, color }
})

// 動能三線交叉點 (M10 穿越 M20)
const crosses = computed(() => {
  const m10 = c.value.m10_s ?? [], m20 = c.value.m20_s ?? [], dates = c.value.dates ?? []
  const up = [], down = []
  for (let i = 1; i < m10.length; i++) {
    const a = m10[i - 1], b = m20[i - 1], x = m10[i], y = m20[i]
    if ([a, b, x, y].some((v) => v === null || v === undefined)) continue
    if (a - b < 0 && x - y >= 0) up.push([dates[i], x])
    else if (a - b > 0 && x - y <= 0) down.push([dates[i], x])
  }
  return { up, down }
})

// ── 次要折線圖 option 產生器 (category x 軸) ──
const AX = { color: '#94a3b8' }
const SPLIT = { lineStyle: { color: '#1f2d40', opacity: 0.4 } }
function baseLine(yAxis, series) {
  return {
    xAxis: { type: 'category', data: c.value.dates, axisLabel: AX, axisLine: { lineStyle: { color: '#1f2d40' } } },
    yAxis,
    legend: { top: 4, textStyle: AX, inactiveColor: '#475569' },
    grid: { left: 56, right: 30, top: 32, bottom: 30 },
    series,
  }
}
const refLine = (vals, color = '#6b7280') => ({ symbol: 'none', silent: true, lineStyle: { type: 'dashed', color }, data: vals.map((y) => ({ yAxis: y })) })

const vsSpyOption = computed(() => baseLine(
  { type: 'value', scale: true, axisLabel: AX, splitLine: SPLIT },
  [
    { name: sector.value, type: 'line', showSymbol: false, data: c.value.sector_index, lineStyle: { color: '#3b82f6', width: 2 }, itemStyle: { color: '#3b82f6' } },
    { name: 'SPY', type: 'line', showSymbol: false, data: c.value.spy_index, lineStyle: { color: '#9ca3af', width: 1.5, type: 'dotted' }, itemStyle: { color: '#9ca3af' } },
  ],
))
const rsLineOption = computed(() => baseLine(
  { type: 'value', scale: true, axisLabel: AX, splitLine: SPLIT },
  [{ name: 'RS Line', type: 'line', showSymbol: false, data: c.value.rs_line, lineStyle: { color: '#22c55e', width: 2 }, itemStyle: { color: '#22c55e' }, markLine: refLine([1.0], 'rgba(255,255,255,0.3)') }],
))
const breadthOption = computed(() => baseLine(
  { type: 'value', min: 0, max: 100, axisLabel: { ...AX, formatter: '{value}%' }, splitLine: SPLIT },
  [{ name: '成分股 > MA20', type: 'line', showSymbol: false, data: c.value.breadth, lineStyle: { color: '#a78bfa', width: 2 }, itemStyle: { color: '#a78bfa' }, areaStyle: { color: '#a78bfa', opacity: 0.1 }, markLine: refLine([20, 50, 80]) }],
))
const udDvOption = computed(() => baseLine(
  { type: 'value', scale: true, axisLabel: AX, splitLine: SPLIT },
  [
    { name: 'UD Ratio', type: 'line', showSymbol: false, data: c.value.ud_dv, lineStyle: { color: '#a78bfa', width: 1.5 }, itemStyle: { color: '#a78bfa' }, markLine: refLine([1.0, 1.5], 'rgba(34,197,94,0.4)') },
    { name: '5日均線', type: 'line', showSymbol: false, data: c.value.ud_dv_sma5, lineStyle: { color: '#f59e0b', width: 2, type: 'dotted' }, itemStyle: { color: '#f59e0b' } },
  ],
))
const momentumOption = computed(() => baseLine(
  { type: 'value', axisLabel: { ...AX, formatter: '{value}%' }, splitLine: SPLIT },
  [
    { name: 'M20', type: 'line', showSymbol: false, data: c.value.m20_s, lineStyle: { color: '#6b7280', width: 1.5, type: 'dotted' }, itemStyle: { color: '#6b7280' } },
    { name: 'M10', type: 'line', showSymbol: false, data: c.value.m10_s, lineStyle: { color: '#f59e0b', width: 1.8, type: 'dashed' }, itemStyle: { color: '#f59e0b' } },
    { name: 'M5', type: 'line', showSymbol: false, data: c.value.m5_s, lineStyle: { color: '#60a5fa', width: 2.2 }, itemStyle: { color: '#60a5fa' }, markLine: refLine([0], 'rgba(255,255,255,0.2)') },
    // 黃金交叉 🔺 (M10 上穿 M20)
    { name: '黃金交叉', type: 'scatter', data: crosses.value.up, symbol: 'triangle', symbolSize: 13, itemStyle: { color: '#22c55e', borderColor: '#fff', borderWidth: 1 }, z: 5 },
    // 死亡交叉 🔻 (M10 下穿 M20)
    { name: '死亡交叉', type: 'scatter', symbol: 'triangle', symbolRotate: 180, data: crosses.value.down, symbolSize: 13, itemStyle: { color: '#ef4444', borderColor: '#fff', borderWidth: 1 }, z: 5 },
  ],
))

// ── VCP 表 ──
const signedColor = (v) => (v > 0 ? 'var(--color-bull)' : v < 0 ? 'var(--color-bear)' : '')
const pf = (v) => (v === null || v === undefined ? '—' : `${v >= 0 ? '+' : ''}${Number(v).toFixed(2)}%`)
const vcpRows = computed(() =>
  (store.detail?.vcp ?? []).map((r) => ({
    ...r,
    ticker: currentSector.value?.leaders.includes(r.ticker) ? `⭐${r.ticker}` : r.ticker,
  })),
)
const vcpCols = [
  { key: 'ticker', label: '代碼', align: 'left' },
  { key: 'price', label: '收盤價', align: 'right', format: (v) => `$${Number(v).toFixed(2)}` },
  { key: 'trend', label: '60D 走勢', align: 'center' },
  { key: 'm1', label: '日漲跌', align: 'right', format: pf, color: signedColor },
  { key: 'm10', label: '累積10日', align: 'right', format: pf, color: signedColor },
  { key: 'm20', label: '累積20日', align: 'right', format: pf, color: signedColor },
  { key: 'm60', label: '累積60日', align: 'right', format: pf, color: signedColor },
  { key: 'dist_ma20', label: '月線乖離', align: 'right', format: pf, color: signedColor },
  { key: 'rs_3m', label: 'RS 3M', align: 'right', format: pf, color: signedColor },
  { key: 'rs_rank', label: '板塊RS排行', align: 'right', format: (v) => (v >= 80 ? `🥇${v}` : v >= 50 ? `🥈${v}` : v) },
  { key: 'atr_pct', label: 'ATR%(相對)', align: 'right', format: (v) => (v < 1.5 ? `🔥${Number(v).toFixed(2)}%` : `${Number(v).toFixed(2)}%`) },
  { key: 'atr_contraction', label: '波動收縮比', align: 'right', format: (v) => (v < 0.7 ? `🔥${Number(v).toFixed(2)}` : v > 1.2 ? `⚠️${Number(v).toFixed(2)}` : Number(v).toFixed(2)) },
  { key: 'up_down_vol', label: '吃貨量比', align: 'right', format: (v) => (v > 1.2 ? `🐳${Number(v).toFixed(2)}` : Number(v).toFixed(2)) },
  { key: 'dist_to_high', label: '距52W高', align: 'right', format: (v) => `${Number(v).toFixed(1)}%`, color: signedColor },
  { key: 'trend_pass', label: '多頭趨勢', align: 'center', format: (v) => (v ? '✅' : '❌') },
  { key: 'vol_dry_up', label: '量能枯竭', align: 'center', format: (v) => (v ? '✅' : '❌') },
]

function loadDetail() {
  if (sector.value) store.fetchDetail(sector.value, period.value)
}

// 點任一全覽圖（熱力圖 / RRG / 軌跡）→ 切換板塊並捲到深度分析
function onSectorPick(name) {
  if (!name) return
  if (name === sector.value) {
    document.getElementById('sector-detail')?.scrollIntoView({ behavior: 'smooth' })
    return
  }
  sector.value = name
  loadDetail()
  setTimeout(() => document.getElementById('sector-detail')?.scrollIntoView({ behavior: 'smooth' }), 100)
}
const onHeatmapSelect = (meta) => onSectorPick(meta?.name)
function reloadAll() {
  store.fetchOverview(period.value)
  loadDetail()
}

onMounted(async () => {
  await store.fetchSectors()
  const wanted = (route.query.sector || '').toString()
  if (wanted && store.sectors.some((s) => s.name === wanted)) {
    sector.value = wanted
  } else if (store.sectors.length) {
    sector.value = store.sectors[0].name
  }
  store.fetchOverview(period.value)
  loadDetail()
})
</script>

<style scoped>
.sr-view { padding: 28px; max-width: 1360px; margin: 0 auto; }
.sr-view h1 { font-size: 22px; margin: 0 0 6px; }
.sub { color: var(--color-text-secondary); font-size: 13px; margin: 0 0 18px; }
.ctrl { display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 12px; }
.ctrl label { font-size: 12px; color: var(--color-text-secondary); display: flex; flex-direction: column; gap: 6px; }
.ctrl select {
  background: var(--color-bg-raised); border: 1px solid var(--color-border); color: var(--color-text-primary);
  padding: 8px 12px; border-radius: var(--radius-md); font-size: 13px; min-width: 220px;
}
.watchlist { font-size: 12px; color: var(--color-text-secondary); line-height: 1.9; }
.watchlist span { display: inline-block; margin-right: 8px; font-family: var(--font-mono); }
.watchlist span.leader { color: var(--color-data-gold); }
.block { margin: 28px 0; }
.block h2 { font-size: 16px; margin: 0 0 14px; }
.block h3 { font-size: 14px; margin: 24px 0 10px; color: var(--color-text-secondary); }
.tabs { display: flex; gap: 6px; margin-bottom: 14px; flex-wrap: wrap; }
.tab-btn {
  background: var(--color-bg-surface); border: 1px solid var(--color-border); color: var(--color-text-secondary);
  padding: 8px 14px; border-radius: var(--radius-md); font-size: 13px; cursor: pointer;
}
.tab-btn.active { background: var(--color-accent); border-color: var(--color-accent); color: #fff; }
.range-bar { display: flex; align-items: center; gap: 6px; margin-bottom: 10px; }
.range-btn { background: transparent; border: 1px solid var(--color-border); color: var(--color-text-secondary); padding: 4px 10px; border-radius: var(--radius-sm); font-size: 12px; cursor: pointer; }
.range-btn.active { background: var(--color-bg-raised); color: var(--color-text-primary); border-color: var(--color-accent); }
.metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 16px; }
.quad { display: flex; flex-direction: column; gap: 2px; background: linear-gradient(90deg, #1e3a5f, #1f2937); padding: 8px 16px; border-radius: 8px; border-left: 4px solid; margin-bottom: 10px; }
.quad-desc { color: var(--color-text-secondary); font-size: 12px; }
.status { padding: 12px 16px; border-radius: var(--radius-md); font-size: 13px; margin-bottom: 8px; }
.status.error { background: rgba(239, 68, 68, 0.12); border: 1px solid var(--color-bear); color: #fca5a5; }
.status.warning { background: rgba(245, 158, 11, 0.1); border: 1px solid var(--color-warning); color: var(--color-warning); }
.status.success { background: rgba(16, 185, 129, 0.1); border: 1px solid var(--color-bull); color: #6ee7b7; }
.status.info { background: rgba(59, 130, 246, 0.1); border: 1px solid var(--color-accent); color: #93c5fd; }
.chart-head { display: flex; justify-content: space-between; align-items: center; }
.logtoggle { font-size: 12px; color: var(--color-text-secondary); display: flex; align-items: center; gap: 6px; cursor: pointer; }
.ph { color: var(--color-text-muted); padding: 30px 0; }
.hint { color: var(--color-text-muted); font-size: 12px; }
.note {
  background: rgba(59, 130, 246, 0.08); border-left: 3px solid var(--color-accent);
  color: var(--color-text-secondary); font-size: 12px; line-height: 1.7;
  padding: 10px 14px; border-radius: var(--radius-sm); margin-bottom: 12px;
}
.note code { background: var(--color-bg-raised); padding: 1px 5px; border-radius: 4px; color: var(--color-data-cyan); }
.chart-row { display: flex; gap: 16px; align-items: stretch; }
.chart-main { flex: 1; min-width: 0; }
.side {
  flex-shrink: 0; width: 200px;
  background: var(--color-bg-surface); border: 1px solid var(--color-border);
  border-radius: var(--radius-md); padding: 14px 16px;
  display: flex; flex-direction: column; gap: 4px;
}
.side-lbl { color: var(--color-text-muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; }
.side-val { font-family: var(--font-mono); font-size: 28px; font-weight: 600; color: var(--color-text-primary); }
.side-val .unit { font-size: 15px; color: var(--color-text-secondary); margin-left: 2px; }
.side-status { font-size: 14px; font-weight: 600; margin: 2px 0; }
.side-desc { color: var(--color-text-secondary); font-size: 12px; line-height: 1.5; }
.side-guide {
  margin-top: auto; padding-top: 10px; border-top: 1px solid var(--color-border-dim);
  color: var(--color-text-muted); font-size: 11px; line-height: 1.7;
}
@media (max-width: 760px) { .chart-row { flex-direction: column; } .side { width: auto; } }
.alert { background: rgba(245, 158, 11, 0.1); border: 1px solid var(--color-warning); color: var(--color-warning); padding: 14px 18px; border-radius: var(--radius-md); }
</style>
