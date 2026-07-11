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

    <details class="explain">
      <summary>📖 指標說明 — 這些欄位怎麼算、為什麼用斜率</summary>
      <div class="explain-body">
        <h3>營收端（硬閘門，淘汰用）</h3>
        <p>
          <b>營收YoY</b>：本季單季營收 ÷ 去年同季 − 1。門檻 ≥ 25%。<br />
          <b>加速t</b> = 本季YoY − 上季YoY，即成長率的變化（二階導數）。YoY 說「成長多快」，
          加速說「成長在變快還是變慢」。例：YoY 30% → 45%，加速t = +15%，成長引擎正在踩油門。<br />
          <b>加速t-1</b>：前一季的加速值。只看一季可能是基期效應（去年同季剛好很爛，今年隨便比都好看）；
          <b>連兩季加速 &gt; 0</b> 才算真拐點 — 這是唯一的淘汰性基本面條件。
        </p>
        <h3>獲利端（軟訊號，只排序不淘汰）— 為什麼用斜率不用成長率</h3>
        <p>
          淨利可以是負的，負數會讓成長率符號錯亂：淨利 −100 → −50 用成長率算是「−50%」，
          看似惡化，實際是虧損砍半、大幅改善。所以獲利端一律用<b>線性回歸斜率</b>，只看方向：
          斜率 &gt; 0 = 每季往上爬，<b>虧損收窄也算改善</b> — 這正是抓「由虧轉盈拐點」的核心，
          公司還在虧錢時成長率沒法用，斜率可以。
        </p>
        <p>
          <b>淨利率斜率</b>：近 4 季淨利率（淨利÷營收）做 OLS 線性回歸的斜率。
          用淨利率而非淨利金額，排除營收放大的干擾，看的是「賺錢效率」的改善方向。<br />
          <b>EPS斜率</b>：近 4 季稀釋 EPS 數值（level，非成長率）的 OLS 斜率。
        </p>
        <h3>分數（池內排序）</h3>
        <p>
          <b>分數 = 淨利率斜率排名 × 0.5 ＋ EPS斜率排名 × 0.3 ＋ 加速t排名 × 0.2</b>，
          排名為左側池內百分位（0～1），分數越高排越前。
          權重邏輯：營收加速已是入場門票（池內人人都有），排序主要比「誰的獲利改善最猛」。<br />
          <b>🔺旗標無條件置頂，蓋過分數</b>：🔺翻正 = 淨利上季為負、本季轉正；
          🔺近轉正 = 仍在虧損但淨利率斜率為正、外推下一季就穿零。
        </p>
      </div>
    </details>

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
.explain { margin-top: 12px; border: 1px solid var(--border, #444); border-radius: 8px; padding: 10px 14px; }
.explain summary { cursor: pointer; font-weight: 600; opacity: 0.85; }
.explain-body { margin-top: 8px; font-size: 0.88rem; line-height: 1.7; opacity: 0.85; }
.explain-body h3 { font-size: 0.95rem; margin: 14px 0 4px; opacity: 1; }
.explain-body p { margin: 4px 0; }
.tab { border: 1px solid var(--border, #444); background: transparent; color: inherit; border-radius: 8px; padding: 6px 14px; cursor: pointer; }
.tab.on { border-color: var(--accent, #2ecc71); color: var(--accent, #2ecc71); }
.block { margin-top: 12px; }
.hint { opacity: 0.7; font-size: 0.85rem; line-height: 1.5; }
.ph { padding: 40px 0; text-align: center; opacity: 0.7; }
.alert { padding: 12px; border: 1px solid #e74c3c66; border-radius: 8px; margin-top: 16px; }
.mono { font-family: ui-monospace, monospace; }
</style>
