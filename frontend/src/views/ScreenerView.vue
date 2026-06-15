<!--
  ScreenerView.vue — BamHI 模型選股
  三類候選：VCP(跨板塊彙整) / Alpha(市值分級) / Genesis(市值分級)。
  篩選邏輯見 SCREENING_PLAYBOOK.md，說明內嵌於頁面下方。
-->
<template>
  <div class="scr">
    <header class="head">
      <h1>🎯 BamHI 模型選股</h1>
      <p class="sub">三套模型篩出的候選清單：VCP 結構、Alpha 戰報、Genesis 戰報。皆為篩選器，請配合你的紀律與停損。</p>
    </header>

    <!-- 分頁 -->
    <div class="tabs">
      <button v-for="t in TABS" :key="t.key" class="tab" :class="{ active: tab === t.key }" @click="switchTab(t.key)">
        {{ t.label }}
      </button>
    </div>

    <!-- VCP -->
    <section v-show="tab === 'vcp'">
      <div v-if="loading.vcp" class="ph">彙整全板塊 VCP 候選中…</div>
      <template v-else-if="vcp">
        <p class="meta">共 {{ vcp.count }} 檔（VCP 分數 ≥ {{ vcp.min_score }} 或 🎯 強訊），跨板塊去重後依分數排序。</p>
        <DataTable v-if="vcpRows.length" :columns="vcpCols" :rows="vcpRows" row-key="ticker" />
        <p v-else class="ph">目前無符合的標的。</p>
      </template>
    </section>

    <!-- Alpha / Genesis (分級) -->
    <section v-for="eng in ['alpha', 'genesis']" :key="eng" v-show="tab === eng">
      <div v-if="loading[eng]" class="ph">套用市值分級篩選中…</div>
      <template v-else-if="models[eng]">
        <p class="meta">
          更新：{{ models[eng].updated_at || '—' }}　共選出 {{ models[eng].total_picked }} 檔（每級最多 10 檔，依 Resonance_Score）
        </p>
        <div v-for="ti in models[eng].tiers" :key="ti.tier" class="tier">
          <h3>
            {{ tierLabel(ti.tier) }}
            <span class="gate">流動性≥${{ ti.gate.dollar_vol_min }}M · 套牢&lt;{{ ti.gate.ov_supply_max }}% <template v-if="ti.gate.need_confirm">· 須當日確認</template></span>
            <span class="cnt">{{ ti.count }} 檔</span>
          </h3>
          <DataTable v-if="ti.count" :columns="eng === 'alpha' ? alphaCols : genesisCols" :rows="ti.items" row-key="Ticker" />
          <p v-else class="ph small">本級無符合門檻的標的。</p>
        </div>
      </template>
    </section>

    <!-- 使用方法 / Playbook 說明 -->
    <details class="playbook">
      <summary>📖 選股器使用方法 + 篩選邏輯（Playbook）</summary>
      <div class="pb-body">
        <h4>怎麼用</h4>
        <ol>
          <li><b>VCP</b>：跨 17 板塊彙整。先看 <b>🎯 強訊</b>（趨勢過＋連續收斂＋吸籌＋跑贏大盤），再看 <b>VCP 分數 ≥70</b>；配收縮段數、吃貨量比、貼近 52 週高。等<b>帶量突破</b>才進場。</li>
          <li><b>Alpha / Genesis</b>：依市值分五級，各級不同門檻，每級取 Resonance_Score 前 10。Win_Prob 僅參考、不主篩。</li>
          <li>出場一律用 <b>ATR</b>（停損＝進場 − 1.5×ATR），別用死的百分比。</li>
        </ol>
        <h4>市值分級門檻</h4>
        <table class="pb-tbl">
          <thead><tr><th>級別</th><th>市值</th><th>流動性閘門</th><th>套牢上限</th><th>當日確認</th><th>部位</th></tr></thead>
          <tbody>
            <tr><td>Mega</td><td>≥$100B</td><td>$200M</td><td>8%</td><td>—</td><td>可重壓、抱久</td></tr>
            <tr><td>Large</td><td>$10–100B</td><td>$50M</td><td>8%</td><td>—</td><td>標準偏大</td></tr>
            <tr><td>Mid</td><td>$2–10B</td><td>$20M</td><td>5%</td><td>—</td><td>標準（最肥區）</td></tr>
            <tr><td>Small</td><td>$0.3–2B</td><td>$10M</td><td>3%</td><td>✅ 須</td><td>砍小、停損緊</td></tr>
            <tr><td>Micro</td><td>&lt;$0.3B</td><td>$5M</td><td>3%</td><td>✅ 須</td><td>極小或不碰</td></tr>
          </tbody>
        </table>
        <p class="note">當日確認：Alpha 看海龜突破 Turtle=1；Genesis 看底部爆量 Vol_Z&gt;1.5。Alpha 另剔除 RS_Rating≥300 的新股雜訊。</p>
        <p class="note">⚠️ 鐵則：Genesis 勝率僅 ~22%、會連敗 → 每筆 ≤2% 總資金。AI 勝率是相對信心、非真實勝率。這是篩選器＋你的紀律，不是無腦印鈔機。</p>
      </div>
    </details>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import apiClient from '@/api/client'
import DataTable from '@/components/ui/DataTable.vue'

const TABS = [
  { key: 'vcp', label: '🌀 VCP 結構' },
  { key: 'alpha', label: '🅰️ Alpha 戰報' },
  { key: 'genesis', label: '🅶 Genesis 戰報' },
]
const tab = ref('vcp')
const loading = reactive({ vcp: false, alpha: false, genesis: false })
const vcp = ref(null)
const models = reactive({ alpha: null, genesis: null })

const signed = (v) => (v > 0 ? 'var(--color-bull)' : v < 0 ? 'var(--color-bear)' : '')
const fixed = (d) => (v) => (v === null || v === undefined ? '—' : Number(v).toFixed(d))

function tierLabel(t) {
  return { Mega: '🐘 Mega 巨型', Large: '🦏 Large 大型', Mid: '🦌 Mid 中型', Small: '🐇 Small 小型', Micro: '🐜 Micro 微型' }[t] || t
}

async function loadVcp() {
  if (vcp.value || loading.vcp) return
  loading.vcp = true
  try {
    vcp.value = (await apiClient.get('/api/screener/vcp', { params: { min_score: 60 } })).data
  } finally {
    loading.vcp = false
  }
}
async function loadModels(eng) {
  if (models[eng] || loading[eng]) return
  loading[eng] = true
  try {
    models[eng] = (await apiClient.get('/api/screener/models', { params: { engine: eng } })).data
  } finally {
    loading[eng] = false
  }
}
function switchTab(k) {
  tab.value = k
  if (k === 'vcp') loadVcp()
  else loadModels(k)
}

onMounted(loadVcp)

// ── VCP 表 ──
const vcpRows = computed(() =>
  (vcp.value?.items ?? []).map((r) => ({ ...r, flag: r.vcp_pass ? '🎯' : '' })),
)
const vcpCols = [
  { key: 'ticker', label: '代碼', align: 'left' },
  { key: 'flag', label: '強訊', align: 'center' },
  { key: 'vcp_score', label: 'VCP分數', align: 'right', format: (v) => (v >= 70 ? `🔥${v}` : v) },
  { key: 'sector', label: '板塊', align: 'left', mono: false },
  { key: 'contractions', label: '收縮段數', align: 'right', format: (v) => (v >= 2 ? `🔥${v}` : v) },
  { key: 'up_down_vol', label: '吃貨量比', align: 'right', format: (v) => (v > 1.2 ? `🐳${fixed(2)(v)}` : fixed(2)(v)) },
  { key: 'rs_rank', label: '板塊RS排行', align: 'right', format: (v) => (v >= 80 ? `🥇${v}` : v >= 50 ? `🥈${v}` : v) },
  { key: 'dist_to_high', label: '距52W高', align: 'right', format: (v) => `${fixed(1)(v)}%`, color: signed },
  { key: 'price', label: '收盤價', align: 'right', format: (v) => `$${fixed(2)(v)}` },
]

// ── Alpha / Genesis 表 ──
const pct = (v) => (v === null || v === undefined ? '—' : `${Number(v).toFixed(1)}%`)
const alphaCols = [
  { key: 'Ticker', label: '代碼', align: 'left' },
  { key: 'Resonance_Score', label: '共振分', align: 'right', format: fixed(1) },
  { key: 'Win_Prob', label: 'AI勝率', align: 'right', format: pct },
  { key: 'Price', label: '價格', align: 'right', format: (v) => `$${fixed(2)(v)}` },
  { key: 'RS_Rating', label: 'RS評級', align: 'right', format: fixed(0) },
  { key: 'Dollar_Vol_M', label: '成交額M', align: 'right', format: fixed(1) },
  { key: 'MktCap_B', label: '市值B', align: 'right', format: fixed(2) },
  { key: 'Ov_Supply', label: '套牢%', align: 'right', format: fixed(1) },
  { key: 'Turtle', label: '海龜', align: 'center', format: (v) => (v === 1 || v === '1' ? '🐢' : '') },
  { key: 'ATR_Pct', label: 'ATR%', align: 'right', format: fixed(1) },
]
const genesisCols = [
  { key: 'Ticker', label: '代碼', align: 'left' },
  { key: 'Resonance_Score', label: '共振分', align: 'right', format: fixed(1) },
  { key: 'Win_Prob', label: 'AI勝率', align: 'right', format: pct },
  { key: 'Price', label: '價格', align: 'right', format: (v) => `$${fixed(2)(v)}` },
  { key: 'MA_Conv', label: '均線糾結', align: 'right', format: fixed(2) },
  { key: 'Vol_Z', label: '爆量Z', align: 'right', format: (v) => (v > 1.5 ? `🔥${fixed(2)(v)}` : fixed(2)(v)) },
  { key: 'Dollar_Vol_M', label: '成交額M', align: 'right', format: fixed(1) },
  { key: 'MktCap_B', label: '市值B', align: 'right', format: fixed(2) },
  { key: 'Ov_Supply', label: '套牢%', align: 'right', format: fixed(1) },
  { key: 'ATR_Pct', label: 'ATR%', align: 'right', format: fixed(1) },
]
</script>

<style scoped>
.scr { padding: 32px 28px; max-width: 1320px; margin: 0 auto; }
.head h1 { font-family: var(--font-display); font-size: 26px; margin: 0 0 6px; letter-spacing: -0.01em; }
.sub { color: var(--color-text-secondary); font-size: 14px; margin: 0 0 22px; }
.tabs { display: flex; gap: 8px; margin-bottom: 22px; border-bottom: 1px solid var(--color-border); }
.tab {
  background: none; border: none; color: var(--color-text-secondary);
  font-size: 15px; font-weight: 600; padding: 10px 18px; cursor: pointer;
  border-bottom: 2px solid transparent; margin-bottom: -1px;
}
.tab:hover { color: var(--color-text-primary); }
.tab.active { color: var(--color-accent-cyan); border-bottom-color: var(--color-accent-cyan); }
.meta { color: var(--color-text-muted); font-size: 13px; margin: 0 0 16px; }
.tier { margin-bottom: 26px; }
.tier h3 { font-size: 15px; margin: 0 0 10px; display: flex; align-items: center; gap: 12px; }
.tier .gate { font-size: 12px; font-weight: 400; color: var(--color-text-muted); }
.tier .cnt { margin-left: auto; font-size: 12px; color: var(--color-text-secondary); background: var(--color-bg-raised); padding: 2px 10px; border-radius: 10px; }
.ph { color: var(--color-text-muted); padding: 24px 0; }
.ph.small { padding: 8px 0; font-size: 13px; }
.playbook { margin-top: 30px; border: 1px solid var(--color-border); border-radius: var(--radius-lg); background: var(--color-bg-surface); }
.playbook summary { cursor: pointer; padding: 14px 18px; font-weight: 600; font-size: 14px; }
.pb-body { padding: 4px 18px 18px; color: var(--color-text-secondary); font-size: 13px; line-height: 1.7; }
.pb-body h4 { color: var(--color-text-primary); font-size: 13px; margin: 14px 0 6px; }
.pb-body ol { margin: 0; padding-left: 20px; }
.pb-tbl { width: 100%; border-collapse: collapse; margin-top: 6px; font-size: 12.5px; }
.pb-tbl th, .pb-tbl td { border: 1px solid var(--color-border); padding: 6px 10px; text-align: left; }
.pb-tbl th { background: var(--color-bg-raised); color: var(--color-text-primary); }
.note { color: var(--color-text-muted); font-size: 12px; margin: 10px 0 0; }
</style>
