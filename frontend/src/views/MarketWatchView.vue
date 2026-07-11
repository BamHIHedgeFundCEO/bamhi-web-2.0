<!--
  MarketWatchView.vue — 市場觀察
  三大戰情儀表板：The Kings / Rising Stars / Macro Compass
  Universe: Russell 1000 + BamHI 板塊合并，SPY 基準
-->
<template>
  <div class="mw">
    <header class="head">
      <h1>🔭 市場觀察</h1>
      <p class="sub">Russell 1000 + BamHI 板塊合并 Universe。RS Rating = 20R/60R/120R 全市場百分位加權排名。</p>
    </header>

    <div class="tabs">
      <button v-for="t in TABS" :key="t.key" class="tab" :class="{ active: tab === t.key }" @click="switchTab(t.key)">
        {{ t.label }}
      </button>
    </div>

    <!-- 自定義篩選列（Kings / Stars 共用，條件記在 localStorage） -->
    <div v-if="tab !== 'compass'" class="filter-bar">
      <div class="f-group">
        <label>RSI</label>
        <input v-model.number="filters.rsiMin" type="number" min="0" max="100" placeholder="低" class="f-num" />
        <span class="f-sep">–</span>
        <input v-model.number="filters.rsiMax" type="number" min="0" max="100" placeholder="高" class="f-num" />
      </div>
      <div class="f-group">
        <label>RS Rank ≥</label>
        <input v-model.number="filters.rankMin" type="number" min="0" max="100" placeholder="—" class="f-num" />
      </div>
      <div v-if="tab === 'stars'" class="f-group">
        <label>加速度 ≥</label>
        <input v-model.number="filters.accelMin" type="number" min="0" placeholder="—" class="f-num" />
      </div>
      <div class="f-group f-tiers">
        <label>市值</label>
        <button
          v-for="t in TIERS" :key="t"
          class="f-chip" :class="{ on: filters.tiers.includes(t) }"
          @click="toggleTier(t)"
        >{{ t }}</button>
      </div>
      <label class="f-check"><input v-model="filters.signalOnly" type="checkbox" /> 只看訊號股</label>
      <label class="f-check"><input v-model="filters.newOnly" type="checkbox" /> 只看 🆕</label>
      <button class="f-reset" @click="resetFilters">清除</button>
      <span class="f-count">{{ tab === 'kings' ? filteredKings.length : filteredStars.length }} 檔符合</span>
    </div>

    <!-- The Kings -->
    <section v-show="tab === 'kings'">
      <div v-if="loading.kings" class="ph">套用板塊 RS 排名中…</div>
      <p v-else-if="errors.kings" class="err">⚠️ {{ errors.kings }}</p>
      <template v-else-if="kings">
        <p v-if="kings.error" class="err">⚠️ {{ kings.error }}</p>
        <div v-if="kings.items?.length" class="toolbar">
          <button class="btn-dl" @click="dlCsv(filteredKings, kingsCols, `BamHI_Kings_${today()}.csv`)">📥 CSV（篩後）</button>
          <button class="btn-dl" @click="dlImg(kingsExport, `BamHI_Kings_${today()}.png`)">🖼️ 圖片</button>
        </div>
        <div ref="kingsExport" class="export-region">
          <p class="meta">更新：{{ kings.updated_at || '—' }}　共 {{ kings.total }} 檔（RS Rank ≥ 80，每 Sub_Industry 取前 3）</p>
          <p class="hint">✅ 買點 = RSI14 介於 30–60（已降溫、未破壞）＋ 相對強勢線（個股÷SPY）&gt; 其 50 日均線（回調中仍跑贏大盤）</p>
          <details class="explain">
            <summary>📖 使用方法・條件・邏輯</summary>
            <div class="explain-body">
              <h4>這張表在幹嘛</h4>
              <p>
                從 Russell 1000 + BamHI 板塊 Universe 裡，找出<b>每個細分行業（Sub-Industry）動能最強的前 3 檔龍頭</b>，
                並標出其中「正在回調、可以接」的買點窗口。邏輯：強者恆強（IBD RS 風格），但不追高 — 等強勢股回調到均值再進。
              </p>
              <h4>選股條件（由上到下過濾）</h4>
              <p>
                ① 流動性：30 日均量 ≥ 30 萬股<br />
                ② <b>RS Rank ≥ 80</b>：全市場動能前 20% 才有資格（絕對門檻，濾掉「矮子裡的高個」）<br />
                ③ 每個 Sub-Industry 依 RS Rank 取前 3 檔
              </p>
              <h4>RS Rank 怎麼算</h4>
              <p>
                20R / 60R / 120R = 近 20 / 60 / 120 個交易日報酬率在<b>全市場的百分位</b>（0–100）。<br />
                <b>RS Rank = 20R×0.2 ＋ 60R×0.4 ＋ 120R×0.4</b> — 偏重中長期，短期權重低，避免被一週暴衝騙進去。
              </p>
              <h4>✅ 買點訊號（Pullback_Buy）— 兩條同時成立</h4>
              <p>
                ① <b>RSI14 介於 30–60</b>：已從過熱區降溫（&lt;60），但沒跌進趨勢破壞區（&gt;30）。
                RSI14 = 14 日相對強弱指標（Wilder 法），&gt;70 過熱、&lt;30 超賣。<br />
                ② <b>相對強勢線 &gt; 其 50 日均線</b>：相對強勢線 = 個股價格 ÷ SPY，這條線在自己的 50MA 之上，
                代表個股回調期間<b>仍在跑贏大盤</b> — 是強勢整理，不是資金撤離。
              </p>
              <h4>怎麼用</h4>
              <p>
                每日更新。掃 ✅ 買點欄 → 看該檔所屬 Sub-Industry 是否也有其他龍頭同步走強（板塊共振）→
                配合自己的進場紀律（止損、倉位）。RSI14 欄綠色 = 未過熱可留意，紅色（&gt;70）= 過熱勿追。
              </p>
            </div>
          </details>
          <DataTable v-if="kings.items?.length" :columns="kingsCols" :rows="filteredKings" row-key="ticker" :row-class="kingsRowClass" />
          <p v-else class="ph">目前無資料。</p>
        </div>
      </template>
    </section>

    <!-- Rising Stars -->
    <section v-show="tab === 'stars'">
      <div v-if="loading.stars" class="ph">掃描動量加速標的…</div>
      <p v-else-if="errors.stars" class="err">⚠️ {{ errors.stars }}</p>
      <template v-else-if="stars">
        <p v-if="stars.error" class="err">⚠️ {{ stars.error }}</p>
        <div v-if="stars.items?.length" class="toolbar">
          <button class="btn-dl" @click="dlCsv(filteredStars, starsCols, `BamHI_RisingStars_${today()}.csv`)">📥 CSV（篩後）</button>
          <button class="btn-dl" @click="dlImg(starsExport, `BamHI_RisingStars_${today()}.png`)">🖼️ 圖片</button>
        </div>
        <div ref="starsExport" class="export-region">
          <p class="meta">更新：{{ stars.updated_at || '—' }}　共 {{ stars.total }} 檔</p>
          <p class="hint">🚀 入選門檻：20R&gt;60R&gt;120R（動能多頭排列）+ 加速度≥30 + 20R≥75</p>
          <p class="hint">✓ 追動能：RSI 55–75 + 加速度&gt;40　｜　✓ 等回調：RSI 30–55 + 加速度&gt;40（以 55 切開，互斥）</p>
          <details class="explain">
            <summary>📖 使用方法・條件・邏輯</summary>
            <div class="explain-body">
              <h4>這張表在幹嘛</h4>
              <p>
                找<b>動能正在加速的黑馬</b>：短期排名 &gt; 中期排名 &gt; 長期排名，代表這檔股票在全市場的相對位置
                一路往上爬 — 可能是剛啟動的新主流，Kings 表還來不及收錄它。
              </p>
              <h4>入選門檻（三條全過）</h4>
              <p>
                ① <b>20R &gt; 60R &gt; 120R</b>：動能多頭排列 — 近 20 日排名比 60 日強、60 日又比 120 日強，越近越強<br />
                ② <b>加速度（Accel）= 20R − 120R ≥ 30</b>：短期排名比長期至少跳了 30 個百分位，爬升夠猛<br />
                ③ <b>20R ≥ 75</b>：短期動能已進全市場前 25%，不是從谷底反彈的雜訊
              </p>
              <h4>兩個進場訊號（RSI 55 切開，互斥 — 同一檔只會亮一個）</h4>
              <p>
                ✓ <b>追動能（RSI 55–75）</b>：動能強勁但未過熱（&lt;75），適合順勢直接進場、突破加碼的打法。<br />
                ✓ <b>等回調（RSI 30–55）</b>：加速度還在（Accel&gt;40）但價格已降溫，適合等回踩支撐、低吸的打法。<br />
                兩者都要求 <b>加速度 &gt; 40</b>（比入選門檻 30 更嚴）— 只對爬升最猛的一批給訊號。<br />
                RSI ≥ 75 = 過熱不給訊號；RSI ≤ 30 = 動能可能已壞，也不給。
              </p>
              <h4>怎麼用</h4>
              <p>
                依加速度排序，越上面爬得越快。先看訊號欄選打法（追 or 等），再看 Sub-Industry 是否成群出現 —
                同板塊多檔同時上榜，通常是板塊輪動的早期訊號，可對照 Kings 表與 Macro Compass 確認資金流向。
                Rising Stars 波動大於 Kings，倉位與止損要更保守。
              </p>
            </div>
          </details>
          <DataTable v-if="stars.items?.length" :columns="starsCols" :rows="filteredStars" row-key="ticker" :row-class="starsRowClass" />
          <p v-else class="ph">目前無符合門檻的標的。</p>
        </div>
      </template>
    </section>

    <!-- Macro Compass -->
    <section v-show="tab === 'compass'">
      <div v-if="loading.compass" class="ph">運算 Granger 因果矩陣…</div>
      <p v-else-if="errors.compass" class="err">⚠️ {{ errors.compass }}</p>
      <template v-else-if="compass">
        <p v-if="compass.error" class="err">⚠️ {{ compass.error }}</p>
        <p class="meta">運算時間：{{ compass.computed_at || '—' }}　{{ compass.nodes?.length || 0 }} 個節點，{{ compass.edges?.length || 0 }} 條因果連結（p&lt;0.05）</p>
        <p class="hint">🕸️ 各板塊 Rank #1 龍頭的 90 天日報酬 Granger 因果檢定。深綠 = 強因果（資金傳導方向：行 → 列）</p>

        <!-- Top edges table -->
        <div v-if="compass.edges?.length" class="compass-wrap">
          <div class="edge-panel">
            <h4>最強資金傳導鏈（Top {{ topEdges.length }}）</h4>
            <table class="edge-tbl">
              <thead><tr><th>來源</th><th>→</th><th>目標</th><th>p值</th><th>板塊</th></tr></thead>
              <tbody>
                <tr v-for="[frm, to, p] in topEdges" :key="`${frm}-${to}`">
                  <td class="mono bull">{{ frm }}</td>
                  <td class="arrow">→</td>
                  <td class="mono">{{ to }}</td>
                  <td class="mono" :style="{ color: pColor(p) }">{{ p }}</td>
                  <td class="muted">{{ compass.sectors?.[frm] || '' }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Heatmap -->
          <div class="heat-panel">
            <h4>因果矩陣熱力圖（行→列 = 因果方向）</h4>
            <VChart :option="heatOption" style="width:100%; height:520px" autoresize />
          </div>
        </div>
        <p v-else class="ph">目前無顯著 Granger 因果連結（需先跑 Pipeline 生成資料）。</p>
      </template>
    </section>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted, watch } from 'vue'
import VChart from 'vue-echarts'
import '@/lib/echarts'
import apiClient from '@/api/client'
import DataTable from '@/components/ui/DataTable.vue'
import { dlCsv, dlImg, today } from '@/lib/exporters'
import { TIERS, capTier, fmtCap, capColor } from '@/lib/marketcap'

const TABS = [
  { key: 'kings',   label: '👑 The Kings' },
  { key: 'stars',   label: '🚀 Rising Stars' },
  { key: 'compass', label: '🕸️ Macro Compass' },
]
const tab = ref('kings')
const loading  = reactive({ kings: false, stars: false, compass: false })
const errors   = reactive({ kings: '', stars: '', compass: '' })
const kings    = ref(null)
const stars    = ref(null)
const compass  = ref(null)

const errMsg = (e) =>
  e?.response?.status
    ? `讀取失敗 (HTTP ${e.response.status})${e.response.data?.detail ? '：' + e.response.data.detail : ''}`
    : e?.message || '讀取失敗'

async function loadKings() {
  if (kings.value || loading.kings) return
  loading.kings = true; errors.kings = ''
  try { kings.value = (await apiClient.get('/api/market-watch/kings')).data }
  catch (e) { errors.kings = errMsg(e) }
  finally { loading.kings = false }
}
async function loadStars() {
  if (stars.value || loading.stars) return
  loading.stars = true; errors.stars = ''
  try { stars.value = (await apiClient.get('/api/market-watch/rising-stars')).data }
  catch (e) { errors.stars = errMsg(e) }
  finally { loading.stars = false }
}
async function loadCompass() {
  if (compass.value || loading.compass) return
  loading.compass = true; errors.compass = ''
  try { compass.value = (await apiClient.get('/api/market-watch/adjacency')).data }
  catch (e) { errors.compass = errMsg(e) }
  finally { loading.compass = false }
}
function switchTab(k) {
  tab.value = k
  if (k === 'kings')   loadKings()
  else if (k === 'stars')   loadStars()
  else if (k === 'compass') loadCompass()
}
onMounted(loadKings)

// ── 自定義篩選（localStorage 持久化） ────────────────────────────────────
const FILTER_KEY = 'mw_filters_v1'
const DEFAULT_FILTERS = { rsiMin: null, rsiMax: null, rankMin: null, accelMin: null, tiers: [], signalOnly: false, newOnly: false }
const filters = reactive({ ...DEFAULT_FILTERS, ...(JSON.parse(localStorage.getItem(FILTER_KEY) || 'null') ?? {}) })
watch(filters, (f) => localStorage.setItem(FILTER_KEY, JSON.stringify(f)), { deep: true })

function toggleTier(t) {
  const i = filters.tiers.indexOf(t)
  if (i >= 0) filters.tiers.splice(i, 1)
  else filters.tiers.push(t)
}
function resetFilters() { Object.assign(filters, JSON.parse(JSON.stringify(DEFAULT_FILTERS))) }

function passCommon(r) {
  if (filters.rsiMin != null && filters.rsiMin !== '' && (r.RSI14 == null || r.RSI14 < filters.rsiMin)) return false
  if (filters.rsiMax != null && filters.rsiMax !== '' && (r.RSI14 == null || r.RSI14 > filters.rsiMax)) return false
  if (filters.rankMin != null && filters.rankMin !== '' && (r.Rank == null || r.Rank < filters.rankMin)) return false
  if (filters.tiers.length && !filters.tiers.includes(capTier(r.MktCap))) return false
  if (filters.newOnly && !r.Is_New) return false
  return true
}
const filteredKings = computed(() =>
  (kings.value?.items ?? []).filter((r) => passCommon(r) && (!filters.signalOnly || r.Pullback_Buy)),
)
const filteredStars = computed(() =>
  (stars.value?.items ?? []).filter(
    (r) =>
      passCommon(r) &&
      (filters.accelMin == null || filters.accelMin === '' || (r.Accel != null && r.Accel >= filters.accelMin)) &&
      (!filters.signalOnly || r.Entry_Momentum || r.Entry_Pullback),
  ),
)

// 訊號股整列高亮
const kingsRowClass = (r) => (r.Pullback_Buy ? 'row-signal' : '')
const starsRowClass = (r) => (r.Entry_Momentum ? 'row-signal' : r.Entry_Pullback ? 'row-signal-alt' : '')

// ── Kings 表 ──────────────────────────────────────────────────────────────
const kingsCols = [
  { key: 'Is_New', label: '', align: 'center', format: (v) => (v ? '🆕' : ''), sortable: false },
  { key: 'ticker', label: '代碼', align: 'left' },
  { key: 'sub_industry', label: 'Sub-Industry', align: 'left', mono: false },
  { key: 'MktCap', label: '市值', align: 'right', format: fmtCap, color: capColor },
  { key: 'Rank', label: 'RS Rank', align: 'right', format: (v) => v?.toFixed(1) ?? '—' },
  { key: '20R',  label: '20R', align: 'right', format: (v) => v?.toFixed(1) ?? '—', color: rankColor },
  { key: '60R',  label: '60R', align: 'right', format: (v) => v?.toFixed(1) ?? '—' },
  { key: '120R', label: '120R', align: 'right', format: (v) => v?.toFixed(1) ?? '—' },
  { key: 'RSI14', label: 'RSI14', align: 'right', format: (v) => v?.toFixed(1) ?? '—', color: rsiColor },
  { key: 'OffHigh', label: '離52週高', align: 'right', format: (v) => v != null ? `${v.toFixed(1)}%` : '—', color: offHighColor },
  { key: 'Price', label: '價格', align: 'right', format: (v) => v != null ? `$${v.toFixed(2)}` : '—' },
  { key: 'Pullback_Buy', label: '進場訊號', align: 'center', format: (v) => v ? '✅ 買點' : '' },
]

// ── Stars 表 ──────────────────────────────────────────────────────────────
const starsCols = [
  { key: 'Is_New', label: '', align: 'center', format: (v) => (v ? '🆕' : ''), sortable: false },
  { key: 'ticker', label: '代碼', align: 'left' },
  { key: 'sub_industry', label: 'Sub-Industry', align: 'left', mono: false },
  { key: 'MktCap', label: '市值', align: 'right', format: fmtCap, color: capColor },
  { key: '20R',  label: '20R', align: 'right', format: (v) => v?.toFixed(1) ?? '—', color: rankColor },
  { key: '60R',  label: '60R', align: 'right', format: (v) => v?.toFixed(1) ?? '—' },
  { key: '120R', label: '120R', align: 'right', format: (v) => v?.toFixed(1) ?? '—' },
  { key: 'Accel', label: '加速度', align: 'right', format: (v) => v != null ? `+${v.toFixed(1)}` : '—', color: () => 'var(--color-bull)' },
  { key: 'Rank', label: 'RS Rank', align: 'right', format: (v) => v?.toFixed(1) ?? '—' },
  { key: 'RSI14', label: 'RSI14', align: 'right', format: (v) => v?.toFixed(1) ?? '—', color: rsiColor },
  { key: 'OffHigh', label: '離52週高', align: 'right', format: (v) => v != null ? `${v.toFixed(1)}%` : '—', color: offHighColor },
  { key: 'Entry_Momentum', label: '追動能', align: 'center', format: (v) => v ? '✓' : '—', color: (v) => v ? 'var(--color-bull)' : '' },
  { key: 'Entry_Pullback', label: '等回調', align: 'center', format: (v) => v ? '✓' : '—', color: (v) => v ? 'var(--color-accent-cyan)' : '' },
  { key: 'Price', label: '價格', align: 'right', format: (v) => v != null ? `$${v.toFixed(2)}` : '—' },
]

function rankColor(v) { return v >= 80 ? 'var(--color-bull)' : v >= 60 ? 'var(--color-accent-cyan)' : '' }
function rsiColor(v)  { return v < 60 ? 'var(--color-bull)' : v > 70 ? 'var(--color-bear)' : '' }
function offHighColor(v) { return v == null ? '' : v >= -5 ? 'var(--color-bull)' : v <= -20 ? 'var(--color-bear)' : '' }

// ── CSV / 圖片下載（共用 lib/exporters，截圖含完整表格範圍） ──────────────
const kingsExport = ref(null)
const starsExport = ref(null)

// ── Macro Compass heatmap ─────────────────────────────────────────────────
const topEdges = computed(() => (compass.value?.edges ?? []).slice(0, 10))

function pColor(p) {
  if (p < 0.01) return '#00ff88'
  if (p < 0.05) return '#a3e635'
  return '#fcd34d'
}

const heatOption = computed(() => {
  if (!compass.value?.nodes?.length) return {}
  const nodes = compass.value.nodes
  const edgeMap = {}
  for (const [frm, to, p] of compass.value.edges ?? []) {
    edgeMap[`${frm}|${to}`] = p
  }
  const data = []
  for (let xi = 0; xi < nodes.length; xi++) {
    for (let yi = 0; yi < nodes.length; yi++) {
      const key = `${nodes[yi]}|${nodes[xi]}`
      const p = yi === xi ? null : (edgeMap[key] ?? null)
      data.push([xi, yi, p])
    }
  }
  return {
    backgroundColor: 'transparent',
    tooltip: {
      backgroundColor: '#1c2333',
      borderColor: '#1f2d40',
      textStyle: { color: '#f1f5f9' },
      formatter: (params) => {
        const [xi, yi, p] = params.value
        if (p === null) return ''
        return `${nodes[yi]} → ${nodes[xi]}<br/>p-value: <b>${p}</b>`
      },
    },
    grid: { left: 80, right: 30, top: 20, bottom: 100 },
    xAxis: {
      type: 'category',
      data: nodes,
      splitArea: { show: true },
      axisLabel: { color: '#94a3b8', rotate: 45, fontSize: 10 },
    },
    yAxis: {
      type: 'category',
      data: nodes,
      splitArea: { show: true },
      axisLabel: { color: '#94a3b8', fontSize: 10 },
    },
    visualMap: {
      min: 0,
      max: 0.05,
      calculable: false,
      show: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 5,
      inRange: { color: ['#00ff88', '#a3e635', '#fcd34d'] },
      outOfRange: { color: '#1e293b' },
      textStyle: { color: '#94a3b8', fontSize: 10 },
      text: ['p=0.05 (弱)', 'p=0 (強)'],
    },
    series: [{
      type: 'heatmap',
      data,
      label: { show: false },
      itemStyle: { borderColor: '#0a0e1a', borderWidth: 1 },
      emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,255,136,0.3)' } },
    }],
  }
})
</script>

<style scoped>
.mw { padding: 32px 28px; max-width: 1400px; margin: 0 auto; }
.head h1 { font-family: var(--font-display); font-size: 26px; margin: 0 0 6px; }
.sub { color: var(--color-text-secondary); font-size: 14px; margin: 0 0 22px; }
.tabs { display: flex; gap: 8px; margin-bottom: 22px; border-bottom: 1px solid var(--color-border); }
.tab {
  background: none; border: none; color: var(--color-text-secondary);
  font-size: 15px; font-weight: 600; padding: 10px 18px; cursor: pointer;
  border-bottom: 2px solid transparent; margin-bottom: -1px;
}
.tab:hover { color: var(--color-text-primary); }
.tab.active { color: var(--color-accent-cyan); border-bottom-color: var(--color-accent-cyan); }
.toolbar { display: flex; gap: 8px; justify-content: flex-end; margin-bottom: 10px; }
.btn-dl {
  background: var(--color-bg-raised);
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  font-size: 12.5px; font-weight: 600;
  padding: 6px 12px; border-radius: var(--radius-md); cursor: pointer;
}
.btn-dl:hover { color: var(--color-text-primary); border-color: var(--color-accent-cyan); }
.export-region { background: var(--color-bg-base, #0a0e1a); padding: 12px; border-radius: var(--radius-md); }
.meta { color: var(--color-text-muted); font-size: 13px; margin: 0 0 8px; }
.hint { color: var(--color-text-secondary); font-size: 12px; margin: 0 0 16px; }
.explain { margin: 0 0 16px; border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: 8px 14px; }
.explain summary { cursor: pointer; font-size: 13px; font-weight: 600; color: var(--color-text-secondary); }
.explain summary:hover { color: var(--color-text-primary); }
.explain-body { font-size: 12.5px; line-height: 1.7; color: var(--color-text-secondary); }
.explain-body h4 { font-size: 13px; color: var(--color-text-primary); margin: 12px 0 4px; }
.explain-body p { margin: 4px 0; }
.explain-body b { color: var(--color-text-primary); }

/* 自定義篩選列 */
.filter-bar {
  display: flex; flex-wrap: wrap; align-items: center; gap: 14px;
  background: var(--color-bg-raised); border: 1px solid var(--color-border);
  border-radius: var(--radius-md); padding: 10px 14px; margin-bottom: 16px;
  font-size: 12.5px;
}
.f-group { display: flex; align-items: center; gap: 6px; }
.f-group label { color: var(--color-text-secondary); white-space: nowrap; }
.f-num {
  width: 52px; background: var(--color-bg-base, #0a0e1a); border: 1px solid var(--color-border);
  border-radius: 6px; color: var(--color-text-primary); padding: 4px 6px; font-size: 12.5px;
}
.f-sep { color: var(--color-text-muted); }
.f-chip {
  background: none; border: 1px solid var(--color-border); color: var(--color-text-secondary);
  border-radius: 999px; padding: 3px 10px; font-size: 12px; cursor: pointer;
}
.f-chip.on { border-color: var(--color-accent-cyan); color: var(--color-accent-cyan); }
.f-check { display: flex; align-items: center; gap: 5px; color: var(--color-text-secondary); cursor: pointer; }
.f-reset {
  background: none; border: none; color: var(--color-text-muted); cursor: pointer;
  font-size: 12px; text-decoration: underline;
}
.f-reset:hover { color: var(--color-text-primary); }
.f-count { margin-left: auto; color: var(--color-accent-cyan); font-weight: 600; }

/* 訊號列高亮 + 表頭 sticky（長表往下捲仍看得到欄名） */
:deep(.row-signal td) { background: rgba(0, 255, 136, 0.06); }
:deep(.row-signal-alt td) { background: rgba(34, 211, 238, 0.06); }
:deep(.export-region .dt-wrap) { max-height: 72vh; overflow: auto; }
:deep(.export-region .dt thead th) { position: sticky; top: 0; background: var(--color-bg-raised); z-index: 2; }

/* 截圖模式：解除高度限制與捲動，讓 PNG 涵蓋整份表格（電腦/平板結果一致） */
.export-region.exporting { width: max-content; min-width: 100%; }
:deep(.export-region.exporting .dt-wrap) { max-height: none !important; overflow: visible !important; }
:deep(.export-region.exporting .dt thead th) { position: static; }
.ph { color: var(--color-text-muted); padding: 24px 0; }
.err { color: var(--color-warning); background: rgba(245,158,11,0.1); border: 1px solid var(--color-warning); padding: 12px 16px; border-radius: var(--radius-md); font-size: 13px; }

/* Macro Compass layout */
.compass-wrap { display: grid; grid-template-columns: 340px 1fr; gap: 24px; margin-top: 8px; }
@media (max-width: 900px) { .compass-wrap { grid-template-columns: 1fr; } }
.edge-panel h4, .heat-panel h4 { font-size: 13px; color: var(--color-text-secondary); margin: 0 0 10px; }
.edge-tbl { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.edge-tbl th, .edge-tbl td { border: 1px solid var(--color-border); padding: 6px 10px; }
.edge-tbl th { background: var(--color-bg-raised); color: var(--color-text-primary); text-align: left; }
.arrow { color: var(--color-text-muted); text-align: center; }
.bull { color: var(--color-bull); }
.muted { color: var(--color-text-muted); font-size: 11px; }
.heat-panel { background: rgba(17,24,39,0.6); border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: 12px; }
</style>
