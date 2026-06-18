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

    <!-- The Kings -->
    <section v-show="tab === 'kings'">
      <div v-if="loading.kings" class="ph">套用板塊 RS 排名中…</div>
      <p v-else-if="errors.kings" class="err">⚠️ {{ errors.kings }}</p>
      <template v-else-if="kings">
        <p v-if="kings.error" class="err">⚠️ {{ kings.error }}</p>
        <p class="meta">更新：{{ kings.updated_at || '—' }}　共 {{ kings.total }} 檔（Top 3/Sub_Industry，依 RS Rank）</p>
        <p class="hint">✅ Pullback_Buy = RSI14&lt;60 + 相對強勢線 &gt; 50MA + 50MA 斜率向上（最佳進場窗口）</p>
        <DataTable v-if="kings.items?.length" :columns="kingsCols" :rows="kings.items" row-key="ticker" />
        <p v-else class="ph">目前無資料。</p>
      </template>
    </section>

    <!-- Rising Stars -->
    <section v-show="tab === 'stars'">
      <div v-if="loading.stars" class="ph">掃描動量加速標的…</div>
      <p v-else-if="errors.stars" class="err">⚠️ {{ errors.stars }}</p>
      <template v-else-if="stars">
        <p v-if="stars.error" class="err">⚠️ {{ stars.error }}</p>
        <p class="meta">更新：{{ stars.updated_at || '—' }}　共 {{ stars.total }} 檔</p>
        <p class="hint">🚀 門檻：20R&gt;60R&gt;120R（多頭排列）+ 加速度≥30 + 20R≥75</p>
        <DataTable v-if="stars.items?.length" :columns="starsCols" :rows="stars.items" row-key="ticker" />
        <p v-else class="ph">目前無符合門檻的標的。</p>
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
import { reactive, ref, computed, onMounted } from 'vue'
import VChart from 'vue-echarts'
import '@/lib/echarts'
import apiClient from '@/api/client'
import DataTable from '@/components/ui/DataTable.vue'

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

// ── Kings 表 ──────────────────────────────────────────────────────────────
const kingsCols = [
  { key: 'ticker', label: '代碼', align: 'left' },
  { key: 'sub_industry', label: 'Sub-Industry', align: 'left', mono: false },
  { key: 'Rank', label: 'RS Rank', align: 'right', format: (v) => v?.toFixed(1) ?? '—' },
  { key: '20R',  label: '20R', align: 'right', format: (v) => v?.toFixed(1) ?? '—', color: rankColor },
  { key: '60R',  label: '60R', align: 'right', format: (v) => v?.toFixed(1) ?? '—' },
  { key: '120R', label: '120R', align: 'right', format: (v) => v?.toFixed(1) ?? '—' },
  { key: 'RSI14', label: 'RSI14', align: 'right', format: (v) => v?.toFixed(1) ?? '—', color: rsiColor },
  { key: 'Price', label: '價格', align: 'right', format: (v) => v != null ? `$${v.toFixed(2)}` : '—' },
  { key: 'Pullback_Buy', label: '進場訊號', align: 'center', format: (v) => v ? '✅ 買點' : '' },
]

// ── Stars 表 ──────────────────────────────────────────────────────────────
const starsCols = [
  { key: 'ticker', label: '代碼', align: 'left' },
  { key: 'sub_industry', label: 'Sub-Industry', align: 'left', mono: false },
  { key: '20R',  label: '20R', align: 'right', format: (v) => v?.toFixed(1) ?? '—', color: rankColor },
  { key: '60R',  label: '60R', align: 'right', format: (v) => v?.toFixed(1) ?? '—' },
  { key: '120R', label: '120R', align: 'right', format: (v) => v?.toFixed(1) ?? '—' },
  { key: 'Accel', label: '加速度', align: 'right', format: (v) => v != null ? `+${v.toFixed(1)}` : '—', color: () => 'var(--color-bull)' },
  { key: 'Rank', label: 'RS Rank', align: 'right', format: (v) => v?.toFixed(1) ?? '—' },
  { key: 'Price', label: '價格', align: 'right', format: (v) => v != null ? `$${v.toFixed(2)}` : '—' },
]

function rankColor(v) { return v >= 80 ? 'var(--color-bull)' : v >= 60 ? 'var(--color-accent-cyan)' : '' }
function rsiColor(v)  { return v < 60 ? 'var(--color-bull)' : v > 70 ? 'var(--color-bear)' : '' }

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
.meta { color: var(--color-text-muted); font-size: 13px; margin: 0 0 8px; }
.hint { color: var(--color-text-secondary); font-size: 12px; margin: 0 0 16px; }
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
