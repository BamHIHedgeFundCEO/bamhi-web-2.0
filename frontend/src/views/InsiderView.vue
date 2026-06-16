<!--
  InsiderView.vue — 美股內部人追蹤雷達 (/insider)
  從背景累積 cache 讀取，瞬間回應；top 20 by 選擇排序。
-->
<template>
  <div class="iv">
    <header class="iv-header">
      <div>
        <h1>🕵️ 內部人追蹤雷達 — SEC Form 4 買賣紀錄</h1>
        <p class="iv-sub">鎖定近期公司內部人買賣動態，快速辨識值得關注的異動。資料來自 SEC EDGAR，背景持續累積更新。</p>
      </div>
      <div class="iv-controls">
        <div class="ctrl-group">
          <label class="ctrl-label">觀察區間</label>
          <select v-model="days" class="ctrl-select" @change="reload">
            <option :value="7">近 7 天</option>
            <option :value="30">近 30 天</option>
            <option :value="60">近 60 天</option>
            <option :value="90">近 90 天</option>
          </select>
        </div>
        <div class="ctrl-group">
          <label class="ctrl-label">排序</label>
          <select v-model="sort" class="ctrl-select" @change="reload">
            <option value="buy_amount">公開買入最多 (P)</option>
            <option value="sell_amount">公開賣出最多 (S)</option>
            <option value="net_buy">淨買入最多 (P-S)</option>
            <option value="latest_date">最近交易時間</option>
          </select>
        </div>
      </div>
    </header>

    <!-- Cache status -->
    <div class="cache-bar">
      <span v-if="store.cacheSize > 0" class="cache-ok">
        ✓ 已累積 {{ store.cacheSize.toLocaleString() }} 筆交易紀錄
        <span v-if="store.lastUpdated"> · 更新 {{ store.lastUpdated.slice(0, 16).replace('T', ' ') }}</span>
      </span>
      <span v-else class="cache-warming">⏳ 資料累積中，首次啟動需幾分鐘…</span>
    </div>

    <!-- Loading -->
    <div v-if="store.radarLoading" class="iv-skeleton">
      <div v-for="n in 10" :key="n" class="skeleton-row"></div>
    </div>

    <!-- Error -->
    <div v-else-if="store.radarError" class="iv-alert">⚠️ {{ store.radarError }}</div>

    <!-- Empty -->
    <div v-else-if="!store.radarItems.length" class="iv-alert" style="border-color:var(--color-border);color:var(--color-text-muted)">
      目前區間無 P/S 交易紀錄。資料持續累積中，請稍後重試或切換至較長觀察區間。
    </div>

    <!-- Table -->
    <template v-else>
      <p class="iv-count">Top {{ store.radarItems.length }} 筆異動紀錄（近 {{ days }} 天，依{{ sortLabel }}排序）</p>
      <div class="tbl-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th class="left">代號</th>
              <th class="left">公司</th>
              <th>最新日期</th>
              <th title="Code P — 公開市場自掏腰包買入，最強看多訊號">🟢 公開買入 (P)</th>
              <th title="Code S — 公開市場賣出，看空訊號">🔴 公開賣出 (S)</th>
              <th title="P - S 淨額（僅計真實訊號，不含行權套現）">淨買入</th>
              <th title="Code M+S — 行權後即賣出套現（中性，非看空訊號）">🟡 行權套現</th>
              <th title="Code F — 稅務代售，強制賣出抵稅，不是看空訊號">⚫ 稅務代售 (F)</th>
              <th>人數</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in store.radarItems" :key="row.symbol">
              <td class="symbol">{{ row.symbol }}</td>
              <td class="company">{{ row.company || '—' }}</td>
              <td class="mono center">{{ row.latest_date || '—' }}</td>
              <td class="center">
                <span v-if="row.buy_amount > 0" class="badge bull">${{ fmtAmt(row.buy_amount) }}</span>
                <span v-else class="badge zero">—</span>
              </td>
              <td class="center">
                <span v-if="row.sell_amount > 0" class="badge bear">${{ fmtAmt(row.sell_amount) }}</span>
                <span v-else class="badge zero">—</span>
              </td>
              <td class="mono right" :class="row.net_buy >= 0 ? 'bull-txt' : 'bear-txt'">
                {{ row.net_buy >= 0 ? '' : '-' }}${{ fmtAmt(Math.abs(row.net_buy)) }}
              </td>
              <td class="center">
                <span v-if="row.exercise_sale_amount > 0" class="badge exercise">${{ fmtAmt(row.exercise_sale_amount) }}</span>
                <span v-else class="badge zero">—</span>
              </td>
              <td class="center">
                <span v-if="row.tax_sale_amount > 0" class="badge tax">${{ fmtAmt(row.tax_sale_amount) }}</span>
                <span v-else class="badge zero">—</span>
              </td>
              <td class="center">{{ row.insider_count }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useInsiderStore } from '@/stores/insider'

const store = useInsiderStore()

const days = ref(30)
const sort = ref('buy_amount')

const SORT_LABELS = {
  buy_amount: '公開買入 (P)',
  sell_amount: '公開賣出 (S)',
  net_buy: '淨買入 (P-S)',
  latest_date: '最近交易時間',
}
const sortLabel = computed(() => SORT_LABELS[sort.value] || sort.value)

function fmtAmt(v) {
  if (!v) return '0'
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`
  return v.toLocaleString()
}

function reload() {
  store.fetchRadar(days.value, sort.value)
}

onMounted(reload)
</script>

<style scoped>
.iv { padding: 28px; max-width: 1280px; margin: 0 auto; }
.iv-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
  margin-bottom: 14px;
}
.iv-header h1 { font-size: 22px; margin: 0 0 6px; }
.iv-sub { color: var(--color-text-secondary); font-size: 13px; max-width: 700px; margin: 0; line-height: 1.6; }
.iv-controls { display: flex; gap: 14px; flex-shrink: 0; align-items: flex-end; }
.ctrl-group { display: flex; flex-direction: column; gap: 4px; }
.ctrl-label { color: var(--color-text-muted); font-size: 11px; }
.ctrl-select {
  background: var(--color-bg-raised);
  border: 1px solid var(--color-border);
  color: var(--color-text-primary);
  padding: 8px 12px;
  border-radius: var(--radius-md);
  font-size: 13px;
  min-width: 150px;
}
.cache-bar {
  font-size: 12px;
  margin-bottom: 12px;
  padding: 6px 0;
}
.cache-ok { color: var(--color-bull); }
.cache-warming { color: var(--color-text-muted); }
.iv-count { color: var(--color-text-muted); font-size: 13px; margin: 0 0 12px; }
.iv-alert {
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid var(--color-warning);
  color: var(--color-warning);
  padding: 14px 18px;
  border-radius: var(--radius-md);
}
.tbl-wrap { overflow-x: auto; border: 1px solid var(--color-border); border-radius: var(--radius-md); }
.tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.tbl th {
  background: var(--color-bg-raised);
  color: var(--color-text-secondary);
  padding: 10px 14px;
  text-align: right;
  font-size: 11px;
  border-bottom: 1px solid var(--color-border);
  white-space: nowrap;
}
.tbl th.left { text-align: left; }
.tbl td { padding: 10px 14px; text-align: right; border-bottom: 1px solid var(--color-border-dim); }
.tbl tr:last-child td { border-bottom: none; }
.tbl tr:hover td { background: var(--color-bg-surface); }
.symbol { text-align: left; color: var(--color-accent); font-weight: 600; font-family: var(--font-mono); }
.company { text-align: left; color: var(--color-text-secondary); max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mono { font-family: var(--font-mono); }
.center { text-align: center; }
.right { text-align: right; }
.bull-txt { color: var(--color-bull); }
.bear-txt { color: var(--color-bear); }
.badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
}
.badge.bull { background: rgba(34, 197, 94, 0.15); color: var(--color-bull); }
.badge.bear { background: rgba(239, 68, 68, 0.15); color: var(--color-bear); }
.badge.exercise { background: rgba(234, 179, 8, 0.15); color: #eab308; }
.badge.tax { background: rgba(100, 116, 139, 0.15); color: var(--color-text-muted); }
.badge.zero { background: transparent; color: var(--color-text-muted); }
.iv-skeleton { display: flex; flex-direction: column; gap: 8px; }
.skeleton-row {
  height: 42px;
  border-radius: var(--radius-sm);
  background: linear-gradient(90deg, var(--color-bg-surface) 25%, var(--color-bg-raised) 50%, var(--color-bg-surface) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite;
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
@media (max-width: 900px) {
  .iv-header { flex-direction: column; }
  .iv-controls { flex-wrap: wrap; }
}
</style>
