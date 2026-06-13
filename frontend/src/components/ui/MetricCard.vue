<!-- MetricCard.vue — 對應 st.metric(label, value, delta) (§2 / §4.3) -->
<template>
  <div class="metric-card">
    <span class="metric-label">{{ label }}</span>
    <span class="metric-value mono">{{ formattedValue }}</span>
    <span v-if="delta !== null && delta !== undefined" class="metric-delta mono" :class="deltaClass">
      {{ delta > 0 ? '▲' : delta < 0 ? '▼' : '–' }} {{ Math.abs(delta) }}{{ deltaSuffix }}
    </span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  value: { type: [Number, String], default: '—' },
  delta: { type: Number, default: null },
  /** 數值格式：'raw' | 'currency' | 'percent' */
  format: { type: String, default: 'raw' },
  deltaSuffix: { type: String, default: '%' },
})

const formattedValue = computed(() => {
  if (props.value === null || props.value === undefined || props.value === '—') return '—'
  const n = typeof props.value === 'number' ? props.value : Number(props.value)
  if (Number.isNaN(n)) return props.value
  if (props.format === 'currency') return `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  if (props.format === 'percent') return `${n.toFixed(2)}%`
  return n.toLocaleString()
})

const deltaClass = computed(() => {
  if (props.delta > 0) return 'bull'
  if (props.delta < 0) return 'bear'
  return 'neutral'
})
</script>

<style scoped>
.metric-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 16px 20px;
}
.metric-label {
  color: var(--color-text-secondary);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.metric-value {
  color: var(--color-text-primary);
  font-size: 24px;
  font-weight: 600;
}
.metric-delta {
  font-size: 13px;
  font-weight: 500;
}
.metric-delta.bull { color: var(--color-bull); }
.metric-delta.bear { color: var(--color-bear); }
.metric-delta.neutral { color: var(--color-neutral); }
</style>
