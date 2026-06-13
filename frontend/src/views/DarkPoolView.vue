<!--
  DarkPoolView.vue — 暗池異常資金監控 (/dark-pool)
  對應 Streamlit views/trading_tools.py · render_darkpool_scanner()
  條件式上色完整移植：color_chg / color_rsi / color_surx
-->
<template>
  <div class="dp-view">
    <header class="dp-header">
      <div>
        <h1>🎯 暗池異常資金監控</h1>
        <p class="dp-sub">
          每日盤後全自動運算，捕捉暗池成交量異常放大 (Surx)，整合趨勢 (VCP) 與反彈雙軌技術濾網。
        </p>
      </div>
      <div class="dp-actions">
        <span v-if="store.asOf" class="dp-asof mono">資料日期 {{ store.asOf }}</span>
        <button class="btn-ghost" :disabled="store.loading" @click="store.fetchSurgeList">
          ↻ 重新整理
        </button>
        <button class="btn-primary" :disabled="!store.items.length" @click="downloadCsv">
          📥 下載 CSV
        </button>
      </div>
    </header>

    <!-- Loading: skeleton -->
    <div v-if="store.loading" class="dp-skeleton">
      <div v-for="n in 8" :key="n" class="skeleton-row"></div>
    </div>

    <!-- Error -->
    <div v-else-if="store.error" class="dp-alert">
      ⚠️ {{ store.error }}
    </div>

    <!-- Data -->
    <template v-else>
      <p class="dp-count">
        ✅ 最新 Top {{ store.items.length }} 異常與技術型態觀察名單
      </p>
      <DataTable :columns="columns" :rows="store.items" row-key="ticker">
        <template #cell-trend="{ value }"><Sparkline :data="value" :width="84" :height="22" /></template>
      </DataTable>
    </template>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useDarkPoolStore } from '@/stores/darkPool'
import { useToastStore } from '@/stores/toast'
import DataTable from '@/components/ui/DataTable.vue'
import Sparkline from '@/components/charts/Sparkline.vue'

const store = useDarkPoolStore()
const toast = useToastStore()

// ── 條件式上色 (移植自 Streamlit color_* 函式) ──
const chgColor = (v) =>
  v > 0 ? 'var(--color-bull)' : v < 0 ? 'var(--color-bear)' : ''

const rsiColor = (v) => {
  if (v > 70) return 'var(--color-bear)' // 超買
  if (v < 30) return 'var(--color-bull)' // 超賣
  return ''
}

const surxColor = (v) => {
  if (v >= 3.0) return '#ff851b' // 強烈異常 (橘)
  if (v >= 1.5) return 'var(--color-data-gold)' // 注意 (黃)
  return ''
}

const num = (v, digits = 2) =>
  v === null || v === undefined ? '—' : Number(v).toFixed(digits)

const columns = [
  { key: 'ticker', label: 'Ticker', align: 'left' },
  { key: 'price', label: 'Price', align: 'right', format: (v) => `$${num(v)}` },
  { key: 'trend', label: '60D 走勢', align: 'center' },
  { key: 'chg_pct', label: 'Chg%', align: 'right', format: (v) => `${num(v)}%`, color: chgColor },
  { key: 'surx', label: 'Surx', align: 'right', format: (v) => `${num(v)}x`, color: surxColor },
  { key: 'short_pct', label: 'Short%', align: 'right', format: (v) => `${num(v)}%` },
  { key: 'above_ma200', label: '> MA200', align: 'center', format: (v) => (v ? '🟢' : '–') },
  { key: 'dist_52w_high_pct', label: 'Dist 52WH%', align: 'right', format: (v) => `${num(v)}%` },
  { key: 'dist_ma200_pct', label: 'Dist MA200%', align: 'right', format: (v) => `${num(v)}%` },
  { key: 'dist_52w_low_pct', label: 'Dist 52WL%', align: 'right', format: (v) => `${num(v)}%` },
  { key: 'rsi_14', label: 'RSI 14', align: 'right', format: (v) => num(v), color: rsiColor },
]

function downloadCsv() {
  // 走勢欄是陣列，排除以免破壞 CSV
  const expCols = columns.filter((c) => c.key !== 'trend')
  const header = expCols.map((c) => c.label)
  const lines = store.items.map((row) =>
    expCols.map((c) => row[c.key] ?? '').join(','),
  )
  const csv = '﻿' + [header.join(','), ...lines].join('\n') // BOM for Excel
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'BamHI_DarkPool_Technical_Top50.csv'
  a.click()
  URL.revokeObjectURL(url)
  toast.success('已下載報表')
}

onMounted(store.fetchSurgeList)
</script>

<style scoped>
.dp-view { padding: 28px; max-width: 1280px; margin: 0 auto; }
.dp-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
  margin-bottom: 20px;
}
.dp-header h1 { font-size: 22px; margin: 0 0 6px; }
.dp-sub { color: var(--color-text-secondary); font-size: 13px; max-width: 640px; margin: 0; }
.dp-actions { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.dp-asof { color: var(--color-text-muted); font-size: 12px; }
.btn-ghost,
.btn-primary {
  border-radius: var(--radius-md);
  padding: 8px 14px;
  font-size: 13px;
  cursor: pointer;
  border: 1px solid var(--color-border);
}
.btn-ghost { background: var(--color-bg-surface); color: var(--color-text-secondary); }
.btn-ghost:hover:not(:disabled) { border-color: var(--color-accent); color: var(--color-text-primary); }
.btn-primary { background: var(--color-accent); color: #fff; border-color: var(--color-accent); }
.btn-primary:hover:not(:disabled) { background: var(--color-accent-dim); }
.btn-ghost:disabled,
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.dp-count { color: var(--color-bull); font-size: 13px; margin: 0 0 12px; }
.dp-alert {
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid var(--color-warning);
  color: var(--color-warning);
  padding: 14px 18px;
  border-radius: var(--radius-md);
  font-size: 14px;
}
.dp-skeleton { display: flex; flex-direction: column; gap: 8px; }
.skeleton-row {
  height: 38px;
  border-radius: var(--radius-sm);
  background: linear-gradient(90deg, var(--color-bg-surface) 25%, var(--color-bg-raised) 50%, var(--color-bg-surface) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite;
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
