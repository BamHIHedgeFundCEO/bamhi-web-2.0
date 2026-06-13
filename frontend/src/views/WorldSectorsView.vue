<!--
  WorldSectorsView.vue — 全球市場強弱 (/world-sectors)
  對應 Streamlit data_engine/market/world_sectors.py · plot_chart()
  週期選擇 + 動能熱力圖 + 各區詳細排行 + 策略 A/B/C 掃描
-->
<template>
  <div class="ws-view">
    <header class="ws-head">
      <h1>🐫 龜族全景動能儀表板</h1>
      <span v-if="store.data?.as_of" class="asof mono">資料日期 {{ store.data.as_of }}</span>
    </header>

    <!-- 週期 -->
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
    <p class="hint">
      {{ store.data?.mode === 'vol_adjusted'
        ? '🛡️ 波動率調整計分 (期間總報酬 ÷ 期間標準差)'
        : '⚡ 純價格漲跌幅' }}
    </p>

    <div v-if="store.loading" class="ph">計算全球資產動能…</div>
    <div v-else-if="store.error" class="alert">⚠️ {{ store.error }}</div>

    <template v-else-if="store.data">
      <!-- 熱力圖 -->
      <section class="block">
        <Treemap :items="store.data.items" :height="540" />
      </section>

      <!-- 各區排行 (2 欄) -->
      <section class="block">
        <h2>📋 各區域詳細強弱排行</h2>
        <div class="region-grid">
          <div v-for="g in store.data.groups" :key="g" class="region">
            <h3>{{ g }}</h3>
            <DataTable :columns="regionCols" :rows="rowsByGroup(g)" row-key="ticker">
              <template #cell-trend="{ value }"><Sparkline :data="value" :width="70" :height="20" /></template>
            </DataTable>
          </div>
        </div>
      </section>

      <!-- 策略掃描 -->
      <section class="block">
        <h2>🎯 多週期量化信號掃描</h2>
        <div v-for="s in STRATEGIES" :key="s.key" class="strat">
          <h3>{{ s.label }}</h3>
          <DataTable
            v-if="store.data.strategies[s.key].length"
            :columns="stratCols"
            :rows="store.data.strategies[s.key]"
            row-key="ticker"
          >
            <template #cell-trend="{ value }"><Sparkline :data="value" :width="80" :height="22" /></template>
          </DataTable>
          <p v-else class="hint">目前無標的符合此條件。</p>
        </div>
      </section>

      <NotesPanel category="market" module="world_sectors" />
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useWorldSectorsStore } from '@/stores/worldSectors'
import DataTable from '@/components/ui/DataTable.vue'
import Treemap from '@/components/charts/Treemap.vue'
import Sparkline from '@/components/charts/Sparkline.vue'
import NotesPanel from '@/components/ui/NotesPanel.vue'

const store = useWorldSectorsStore()

const PERIODS = [
  { label: '1天', value: 1 }, { label: '3天', value: 3 }, { label: '1週', value: 5 },
  { label: '2週', value: 10 }, { label: '1個月', value: 20 }, { label: '2個月', value: 40 },
  { label: '3個月', value: 60 }, { label: '半年', value: 120 },
]
const STRATEGIES = [
  { key: 'a', label: '🔥 策略 A：動態點火 (VCP 動態突破)' },
  { key: 'b', label: '💎 策略 B：動態錯殺 (乖離過大反彈)' },
  { key: 'c', label: '⚠️ 策略 C：波段破壞 (避險與資金撤出)' },
]

const activePeriod = ref(20)

const signedColor = (v) => (v > 0 ? 'var(--color-bull)' : v < 0 ? 'var(--color-bear)' : '')
const n = (v, d = 2) => (v === null || v === undefined ? '—' : Number(v).toFixed(d))
const signed = (v, d = 2) => (v === null || v === undefined ? '—' : `${v >= 0 ? '+' : ''}${Number(v).toFixed(d)}`)

const regionCols = [
  { key: 'ticker', label: '代號', align: 'left' },
  { key: 'name', label: '名稱', align: 'left', mono: false },
  { key: 'price', label: '現價', align: 'right', format: (v) => n(v) },
  { key: 'trend', label: '60D 走勢', align: 'center' },
  { key: 'chg_pct', label: '漲跌%', align: 'right', format: (v) => signed(v), color: signedColor },
  { key: 'score', label: '強弱分', align: 'right', format: (v) => signed(v), color: signedColor },
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

const grouped = computed(() => {
  const map = {}
  for (const it of store.data?.items ?? []) {
    ;(map[it.group] ??= []).push(it)
  }
  for (const k in map) map[k].sort((a, b) => b.score - a.score)
  return map
})
function rowsByGroup(g) {
  return grouped.value[g] ?? []
}

function selectPeriod(p) {
  activePeriod.value = p
  store.fetchMomentum(p)
}

onMounted(() => store.fetchMomentum(activePeriod.value))
</script>

<style scoped>
.ws-view { padding: 28px; max-width: 1360px; margin: 0 auto; }
.ws-head { display: flex; align-items: baseline; gap: 14px; margin-bottom: 16px; }
.ws-head h1 { font-size: 22px; margin: 0; }
.asof { color: var(--color-text-muted); font-size: 12px; }
.block { margin-bottom: 36px; }
.block h2 { font-size: 16px; margin: 0 0 12px; }
.block h3 { font-size: 13px; margin: 0 0 8px; color: var(--color-text-secondary); }
.hint { color: var(--color-text-muted); font-size: 12px; margin: 6px 0 16px; }
.range-bar { display: flex; gap: 6px; flex-wrap: wrap; }
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
.region-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 20px; }
.region { min-width: 0; }
.ph { color: var(--color-text-muted); padding: 40px 0; }
.alert {
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid var(--color-warning);
  color: var(--color-warning);
  padding: 14px 18px;
  border-radius: var(--radius-md);
}
.strat { margin-bottom: 8px; }
</style>
