<!--
  TradingModelsView.vue — 量化模型庫與每日戰報 (/models)
  對應 Streamlit views/trading_models.py + components/ai_models.py
  時光機日期選擇 + Alpha/Genesis 雙引擎 (戰況速覽 + AI 嚴選名單 + 下載)
-->
<template>
  <div class="tm-view">
    <h1>🤖 BamHI 量化模型庫與每日戰報</h1>
    <p class="sub">揭開 BamHI 交易決策背後的 AI 大腦，展示兩大引擎每日最新（或歷史）輸出的狙擊名單。</p>

    <!-- 時光機 -->
    <div class="datebar">
      <label>📅 戰報日期</label>
      <select v-model="activeDate" @change="reload">
        <option value="latest">🔥 最新戰報 (Latest)</option>
        <option v-for="d in store.dates" :key="d.raw" :value="d.raw">🕰️ {{ d.label }}</option>
      </select>
    </div>

    <!-- 引擎 tab -->
    <div class="tabs">
      <button
        v-for="t in ENGINES"
        :key="t.key"
        class="tab-btn"
        :class="{ active: t.key === activeEngine }"
        @click="selectEngine(t.key)"
      >
        {{ t.label }}
      </button>
    </div>

    <div class="engine-meta">
      <h2>{{ activeEngineInfo.title }}</h2>
      <p class="arch">架構：<code>LightGBM Classifier</code> + <code>Optuna 最佳化</code>｜{{ activeEngineInfo.goal }}</p>
    </div>

    <div v-if="store.loading" class="ph">載入戰報中…</div>
    <div v-else-if="store.error" class="alert">⚠️ {{ store.error }}</div>

    <template v-else-if="report">
      <!-- 戰況速覽 -->
      <h3>📊 今日戰況速覽</h3>
      <div class="metrics">
        <MetricCard label="今日狙擊標的數" :value="report.stats.total" delta-suffix="" />
        <MetricCard label="榜首最高共振分" :value="report.stats.max_resonance ?? '—'" delta-suffix="" />
        <MetricCard label="入榜平均勝率" :value="report.stats.avg_win_prob ?? '—'" format="percent" />
      </div>

      <!-- AI 嚴選名單 -->
      <div class="list-head">
        <h3>🎯 AI 嚴選名單 {{ report.date }}</h3>
        <button class="btn-primary" :disabled="!report.items.length" @click="downloadCsv">📥 下載戰報 CSV</button>
      </div>
      <p v-if="report.updated_at" class="updated mono">🔄 最後更新：{{ report.updated_at }}</p>
      <DataTable :columns="cols" :rows="report.items" row-key="Ticker" />
      <p v-if="!report.items.length" class="hint">⏳ 該引擎資料尚未產生或同步中…</p>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useModelsStore } from '@/stores/models'
import MetricCard from '@/components/ui/MetricCard.vue'
import DataTable from '@/components/ui/DataTable.vue'

const store = useModelsStore()

const ENGINES = [
  { key: 'alpha', label: '🌊 Alpha 趨勢大腦' },
  { key: 'genesis', label: '🌋 Genesis 創世紀大腦' },
]
const ENGINE_INFO = {
  alpha: { title: 'Alpha 趨勢追蹤模型 (V7.3)', goal: '尋找均線多頭排列、準備進入主升段的強勢股，目標捕獲 10% 波段。' },
  genesis: { title: 'Genesis 底部翻轉模型 (V1.0)', goal: '專攻均線極度糾結、底部帶量突破的潛在轉折股，追求極致盈虧比。' },
}

const activeEngine = ref('alpha')
const activeDate = ref('latest')

const activeEngineInfo = computed(() => ENGINE_INFO[activeEngine.value])
const report = computed(() => store.reports[`${activeEngine.value}:${activeDate.value}`] ?? null)

const n = (v, d = 2) => (v === null || v === undefined ? '—' : Number(v).toFixed(d))
const signedColor = (v) => (v > 0 ? 'var(--color-bull)' : v < 0 ? 'var(--color-bear)' : '')

// 共用欄位
const COMMON = {
  Ticker: { key: 'Ticker', label: '代碼', align: 'left' },
  Resonance_Score: { key: 'Resonance_Score', label: '🔥 共振總分', align: 'right', format: (v) => n(v, 1), color: () => 'var(--color-data-gold)' },
  Win_Prob: { key: 'Win_Prob', label: '🤖 AI 勝率', align: 'right', format: (v) => `${n(v, 1)}%` },
  Price: { key: 'Price', label: '價格($)', align: 'right', format: (v) => n(v) },
  Ov_Supply: { key: 'Ov_Supply', label: '套牢%', align: 'right', format: (v) => `${n(v, 1)}%` },
  POC_Dist: { key: 'POC_Dist', label: 'POC距離%', align: 'right', format: (v) => `${n(v, 1)}%` },
}
const ALPHA_COLS = [
  COMMON.Ticker, COMMON.Resonance_Score, COMMON.Win_Prob, COMMON.Price,
  { key: 'RS_Rating', label: 'RS強度', align: 'right', format: (v) => n(v, 0) },
  COMMON.Ov_Supply, COMMON.POC_Dist,
  { key: 'MA20_DP', label: 'MA20乖離', align: 'right', format: (v) => n(v, 2), color: signedColor },
  { key: 'Vol_Dry_Up', label: '量縮', align: 'right', format: (v) => n(v, 2) },
  { key: 'Turtle', label: '海龜突破', align: 'center', format: (v) => (Number(v) ? '✅' : '—') },
]
const GENESIS_COLS = [
  COMMON.Ticker, COMMON.Resonance_Score, COMMON.Win_Prob, COMMON.Price,
  { key: 'MA_Conv', label: '均線糾結%', align: 'right', format: (v) => `${n(v, 2)}%` },
  { key: 'Vol_Z', label: '爆量Z', align: 'right', format: (v) => n(v, 2) },
  { key: 'Breakout', label: '破線位階%', align: 'right', format: (v) => `${n(v, 1)}%` },
  { key: 'MA20_Slope', label: '20MA拐頭%', align: 'right', format: (v) => n(v, 2), color: signedColor },
  COMMON.Ov_Supply, COMMON.POC_Dist,
]
const cols = computed(() => (activeEngine.value === 'alpha' ? ALPHA_COLS : GENESIS_COLS))

async function ensureReport() {
  const key = `${activeEngine.value}:${activeDate.value}`
  if (!store.reports[key]) await store.fetchReport(activeEngine.value, activeDate.value)
}
function selectEngine(k) {
  activeEngine.value = k
  ensureReport()
}
function reload() {
  ensureReport()
}

function downloadCsv() {
  const r = report.value
  if (!r?.items.length) return
  const header = cols.value.map((c) => c.label)
  const lines = r.items.map((row) => cols.value.map((c) => row[c.key] ?? '').join(','))
  const csv = '﻿' + [header.join(','), ...lines].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `BamHI_${activeEngine.value}_Report_${r.date.replace(/[()/]/g, '')}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(async () => {
  await store.fetchDates()
  await ensureReport()
})
</script>

<style scoped>
.tm-view { padding: 28px; max-width: 1280px; margin: 0 auto; }
.tm-view h1 { font-size: 22px; margin: 0 0 6px; }
.sub { color: var(--color-text-secondary); font-size: 13px; margin: 0 0 20px; }
.datebar { display: flex; align-items: center; gap: 12px; margin-bottom: 18px; }
.datebar label { font-size: 12px; color: var(--color-text-secondary); }
.datebar select {
  background: var(--color-bg-raised);
  border: 1px solid var(--color-border);
  color: var(--color-text-primary);
  padding: 8px 12px;
  border-radius: var(--radius-md);
  font-size: 13px;
  min-width: 240px;
}
.tabs { display: flex; gap: 6px; margin-bottom: 16px; }
.tab-btn {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  padding: 8px 16px;
  border-radius: var(--radius-md);
  font-size: 13px;
  cursor: pointer;
}
.tab-btn.active { background: var(--color-accent); border-color: var(--color-accent); color: #fff; }
.engine-meta { margin-bottom: 20px; }
.engine-meta h2 { font-size: 17px; margin: 0 0 4px; }
.arch { color: var(--color-text-secondary); font-size: 12px; margin: 0; }
.arch code { background: var(--color-bg-raised); padding: 1px 6px; border-radius: 4px; color: var(--color-data-cyan); }
.metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 28px; }
.list-head { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.list-head h3 { margin: 0; }
h3 { font-size: 15px; margin: 0 0 12px; }
.updated { color: var(--color-text-muted); font-size: 11px; margin: 4px 0 12px; }
.btn-primary {
  background: var(--color-accent);
  color: #fff;
  border: 1px solid var(--color-accent);
  border-radius: var(--radius-md);
  padding: 8px 14px;
  font-size: 13px;
  cursor: pointer;
}
.btn-primary:hover:not(:disabled) { background: var(--color-accent-dim); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.ph { color: var(--color-text-muted); padding: 40px 0; }
.hint { color: var(--color-text-muted); font-size: 12px; }
.alert {
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid var(--color-warning);
  color: var(--color-warning);
  padding: 14px 18px;
  border-radius: var(--radius-md);
}
</style>
