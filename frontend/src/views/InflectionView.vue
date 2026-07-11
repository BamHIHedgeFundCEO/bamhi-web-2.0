<!--
  InflectionView.vue — 拐點篩選 (/app/inflection)
  左側池 = 營收高成長且加速（二階導數為正），獲利只看改善方向（允許為負）。
  右側池 = 左側池 ∩ 週線 Stage 2 ∩ 日線 Minervini 模板 ∩ RS_rank ≥ 80。
  資料：每週六 GitHub Actions → Supabase → /api/inflection。
-->
<template>
  <div class="inf-view">
    <header class="inf-head">
      <h1>📐 拐點篩選</h1>
      <div class="head-right">
        <select v-if="store.runs.length" v-model="selectedRun" class="run-sel" @change="onRunChange">
          <option v-for="d in store.runs" :key="d" :value="d">{{ d }}</option>
        </select>
        <span v-if="store.runDate" class="asof mono">篩選日 {{ store.runDate }}</span>
      </div>
    </header>

    <div class="tabs">
      <button class="tab" :class="{ on: tab === 'right' }" @click="tab = 'right'">
        ✅ 右側池（技術確認）{{ store.right.length ? `· ${store.right.length}` : '' }}
      </button>
      <button class="tab" :class="{ on: tab === 'left' }" @click="tab = 'left'">
        🌱 左側池（基本面拐點）{{ store.left.length ? `· ${store.left.length}` : '' }}
      </button>
    </div>

    <div v-if="store.loading" class="ph">載入篩選結果…</div>
    <div v-else-if="store.error" class="alert">⚠️ {{ store.error }}</div>

    <template v-else>
      <section v-if="tab === 'right'" class="block">
        <p class="hint">
          左側池成員中同時通過：週線（收盤 > MA30↑、MA10 > MA30）＋ 日線趨勢模板（close > MA50 > MA150 > MA200 等五條）＋ RS 百分位 ≥ 80。
          🔺RS領先 = RS Line 創 126 日新高但價格未創高（最純左側訊號）。
        </p>
        <DataTable :columns="rightCols" :rows="store.right" row-key="ticker" />
      </section>

      <section v-else class="block">
        <p class="hint">
          硬閘門：營收 YoY ≥ 25% 且連兩季加速；流動性（市值 ≥ 1 億、價 ≥ $3、20 日均額 ≥ $30M）。
          🔺翻正 = 淨利剛由負轉正；🔺近轉正 = 虧損收窄且外推下季穿零。旗標無條件置頂。
        </p>
        <DataTable :columns="leftCols" :rows="store.left" row-key="ticker" />
      </section>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useInflectionStore } from '@/stores/inflection'
import DataTable from '@/components/ui/DataTable.vue'

const store = useInflectionStore()
const tab = ref('right')
const selectedRun = ref(null)

const fmtPct = (v) => (v == null ? '—' : `${(v * 100).toFixed(1)}%`)
const fmtUsd = (v) => {
  if (v == null) return '—'
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`
  if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`
  return `$${Number(v).toFixed(0)}`
}
const fmtNum = (d) => (v) => (v == null ? '—' : Number(v).toFixed(d))
const fmtBool = (v) => (v ? '✅' : '—')
const upDown = (v) => (v == null ? null : v > 0 ? 'var(--up, #2ecc71)' : 'var(--down, #e74c3c)')

const baseCols = [
  { key: 'flags', label: '🔺', sortable: false },
  { key: 'ticker', label: '代碼' },
  { key: 'name', label: '公司', mono: false },
  { key: 'price', label: '價格', align: 'right', format: fmtNum(2) },
  { key: 'market_cap', label: '市值', align: 'right', format: fmtUsd },
  { key: 'yoy_t', label: '營收YoY', align: 'right', format: fmtPct, color: upDown },
  { key: 'accel_t', label: '加速t', align: 'right', format: fmtPct, color: upDown },
  { key: 'accel_t1', label: '加速t-1', align: 'right', format: fmtPct, color: upDown },
  { key: 'margin_slope', label: '淨利率斜率', align: 'right', format: fmtNum(4), color: upDown },
  { key: 'eps_slope', label: 'EPS斜率', align: 'right', format: fmtNum(3), color: upDown },
]

const leftCols = [
  ...baseCols,
  { key: 'score', label: '分數', align: 'right', format: fmtNum(3) },
  { key: 'latest_period', label: '最新季' },
  { key: 'data_quality', label: '資料' },
]

const rightCols = [
  ...baseCols,
  { key: 'rs_rank', label: 'RS百分位', align: 'right', format: fmtNum(0) },
  { key: 'vol_confirm', label: '量能', align: 'center', format: fmtBool },
  { key: 'obv_confirm', label: 'OBV', align: 'center', format: fmtBool },
  { key: 'vcp_proxy', label: 'VCP', align: 'center', format: fmtBool },
]

function onRunChange() {
  store.fetchPools(selectedRun.value)
}

onMounted(async () => {
  await store.fetchRuns()
  selectedRun.value = store.runDate
  await store.fetchPools(selectedRun.value)
})
</script>

<style scoped>
.inf-view { padding: 20px 24px; max-width: 1400px; margin: 0 auto; }
.inf-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.inf-head h1 { margin: 0; font-size: 1.4rem; }
.head-right { display: flex; align-items: center; gap: 10px; }
.run-sel { background: transparent; border: 1px solid var(--border, #444); border-radius: 6px; padding: 4px 8px; color: inherit; }
.asof { opacity: 0.7; font-size: 0.85rem; }
.tabs { display: flex; gap: 8px; margin: 16px 0 4px; }
.tab { border: 1px solid var(--border, #444); background: transparent; color: inherit; border-radius: 8px; padding: 6px 14px; cursor: pointer; }
.tab.on { border-color: var(--accent, #2ecc71); color: var(--accent, #2ecc71); }
.block { margin-top: 12px; }
.hint { opacity: 0.7; font-size: 0.85rem; line-height: 1.5; }
.ph { padding: 40px 0; text-align: center; opacity: 0.7; }
.alert { padding: 12px; border: 1px solid #e74c3c66; border-radius: 8px; margin-top: 16px; }
.mono { font-family: ui-monospace, monospace; }
</style>
