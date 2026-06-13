<!--
  Sparkline.vue — 輕量 SVG 迷你走勢線 (對應 Streamlit LineChartColumn)。
  純 SVG、零依賴，適合在表格每列渲染 60~126 日 Trend。
-->
<template>
  <svg :width="width" :height="height" class="spark" preserveAspectRatio="none">
    <polyline :points="points" fill="none" :stroke="strokeColor" stroke-width="1.2" />
  </svg>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
  width: { type: Number, default: 96 },
  height: { type: Number, default: 28 },
})

const strokeColor = computed(() => {
  const d = props.data
  if (d.length < 2) return 'var(--color-neutral)'
  return d[d.length - 1] >= d[0] ? 'var(--color-bull)' : 'var(--color-bear)'
})

const points = computed(() => {
  const d = props.data
  if (!d.length) return ''
  const min = Math.min(...d)
  const max = Math.max(...d)
  const range = max - min || 1
  const stepX = props.width / (d.length - 1 || 1)
  const pad = 2
  const usableH = props.height - pad * 2
  return d
    .map((v, i) => {
      const x = i * stepX
      const y = pad + usableH - ((v - min) / range) * usableH
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
})
</script>

<style scoped>
.spark { display: block; }
</style>
