<!--
  MacroMarketView.vue — 總經市場指標 (/macro)
  對應 Streamlit views/macro_market.py + components/charts.py
  指標切換 (radio) + 時間區間過濾 + 最新值/漲跌 + ECharts 圖 (情緒含雙 tab)
-->
<template>
  <div class="macro-view">
    <h1>📊 總經市場指標</h1>

    <!-- 指標選擇 (對應 st.radio horizontal) -->
    <div class="seg">
      <button
        v-for="opt in INDICATORS"
        :key="opt.id"
        class="seg-btn"
        :class="{ active: opt.id === activeId }"
        @click="selectIndicator(opt.id)"
      >
        {{ opt.label }}
      </button>
    </div>

    <hr class="divider" />

    <div v-if="store.loading" class="ph">載入中…</div>
    <div v-else-if="store.error" class="alert">⚠️ {{ store.error }}</div>

    <template v-else-if="store.current">
      <div class="head-row">
        <h2 class="subtitle">📉 {{ store.current.name }}</h2>
        <MetricCard
          v-if="store.current.latest.value !== null"
          class="metric"
          :label="latestLabel"
          :value="store.current.latest.value"
          :delta="store.current.latest.change"
          :delta-suffix="store.current.latest.change_type === 'pct' ? '%' : ''"
        />
      </div>

      <!-- 時間區間過濾 (對應 st.radio All/6m/YTD/...) -->
      <div class="range-bar">
        <button
          v-for="r in RANGES"
          :key="r"
          class="range-btn"
          :class="{ active: r === activeRange }"
          @click="activeRange = r"
        >
          {{ r }}
        </button>
      </div>

      <!-- 情緒：雙 tab -->
      <div v-if="subTabs" class="tabs">
        <button
          v-for="t in subTabs"
          :key="t.key"
          class="tab-btn"
          :class="{ active: t.key === activeSubTab }"
          @click="activeSubTab = t.key"
        >
          {{ t.label }}
        </button>
      </div>

      <TimeSeriesChart :option="chartOption" :height="subTabs ? 520 : 440" />

      <NotesPanel v-if="noteRef" :category="noteRef.category" :module="noteRef.module" />
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useMacroStore } from '@/stores/macro'
import MetricCard from '@/components/ui/MetricCard.vue'
import TimeSeriesChart from '@/components/charts/TimeSeriesChart.vue'
import NotesPanel from '@/components/ui/NotesPanel.vue'
import { buildMacroOption, HAS_SUBTABS } from '@/lib/macroChartSpecs'

const store = useMacroStore()

const INDICATORS = [
  { id: 'DGS10', label: '10年期美債殖利率' },
  { id: 'DGS2', label: '2年期美債殖利率' },
  { id: 'SPREAD_10_2', label: '10-2 Spread' },
  { id: 'MACRO_TRIO', label: '核心經濟指標' },
  { id: 'BREADTH_SP500', label: '市場寬度' },
  { id: 'SENTIMENT_COMBO', label: '情緒方向' },
]
const RANGES = ['All', '6m', 'YTD', '1Y', '3Y', '5Y', '10Y']

const activeId = ref('DGS10')
const activeRange = ref('1Y')
const activeSubTab = ref('naaim')

const subTabs = computed(() => HAS_SUBTABS[activeId.value] ?? null)

// 指標 → 筆記 (category/module)，對應 notes 套件
const NOTE_REF = {
  DGS10: { category: 'rates', module: 'treasury' },
  DGS2: { category: 'rates', module: 'treasury' },
  SPREAD_10_2: { category: 'rates', module: 'treasury' },
  MACRO_TRIO: { category: 'rates', module: 'gdp_fedfunds_rstar' },
  BREADTH_SP500: { category: 'market', module: 'breadth' },
  SENTIMENT_COMBO: { category: 'market', module: 'naaim' },
}
const noteRef = computed(() => NOTE_REF[activeId.value] ?? null)

const latestLabel = computed(() =>
  store.current?.latest.change_type === 'raw' ? '最新數值 (季變動)' : '最新數值',
)

async function selectIndicator(id) {
  activeId.value = id
  if (HAS_SUBTABS[id]) activeSubTab.value = HAS_SUBTABS[id][0].key
  await store.fetchSeries(id)
}

// ── 時間區間過濾 (client-side，對應 Streamlit 切片) ──
const filteredRows = computed(() => {
  const rows = store.current?.data ?? []
  if (!rows.length || activeRange.value === 'All') return rows
  const end = new Date(rows[rows.length - 1].date)
  let start = new Date(end)
  switch (activeRange.value) {
    case '6m': start.setMonth(end.getMonth() - 6); break
    case 'YTD': start = new Date(end.getFullYear(), 0, 1); break
    case '1Y': start.setFullYear(end.getFullYear() - 1); break
    case '3Y': start.setFullYear(end.getFullYear() - 3); break
    case '5Y': start.setFullYear(end.getFullYear() - 5); break
    case '10Y': start.setFullYear(end.getFullYear() - 10); break
  }
  const startStr = start.toISOString().slice(0, 10)
  return rows.filter((r) => r.date >= startStr)
})

const chartOption = computed(() =>
  buildMacroOption(activeId.value, filteredRows.value, activeSubTab.value),
)

onMounted(() => store.fetchSeries(activeId.value))
</script>

<style scoped>
.macro-view { padding: 28px; max-width: 1280px; margin: 0 auto; }
.macro-view h1 { font-size: 22px; margin: 0 0 18px; }
.seg { display: flex; flex-wrap: wrap; gap: 8px; }
.seg-btn {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  padding: 8px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  cursor: pointer;
}
.seg-btn:hover { border-color: var(--color-accent); color: var(--color-text-primary); }
.seg-btn.active { background: var(--color-accent); border-color: var(--color-accent); color: #fff; }
.divider { border: none; border-top: 1px solid var(--color-border); margin: 18px 0; }
.head-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; margin-bottom: 14px; }
.subtitle { font-size: 17px; margin: 0; }
.metric { min-width: 200px; }
.range-bar, .tabs { display: flex; gap: 6px; margin-bottom: 12px; flex-wrap: wrap; }
.range-btn, .tab-btn {
  background: transparent;
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  padding: 5px 12px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-family: var(--font-mono);
  cursor: pointer;
}
.range-btn.active, .tab-btn.active { background: var(--color-bg-raised); color: var(--color-text-primary); border-color: var(--color-accent); }
.tab-btn { font-family: var(--font-sans); }
.ph { color: var(--color-text-muted); padding: 40px 0; }
.alert {
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid var(--color-warning);
  color: var(--color-warning);
  padding: 14px 18px;
  border-radius: var(--radius-md);
}
</style>
