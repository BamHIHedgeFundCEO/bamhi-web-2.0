<!--
  CorrHeatmap.vue — 相關係數矩陣熱力圖 (對應 _sector_charts.render_correlation_heatmap)
  RdBu 色階，zmid=0，-1..1。
-->
<template>
  <div class="corr-wrap">
    <VChart :option="option" :style="{ height: height + 'px', width: '100%' }" autoresize />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import '@/lib/echarts'

const props = defineProps({
  labels: { type: Array, default: () => [] },
  matrix: { type: Array, default: () => [] }, // matrix[i][j]
  height: { type: Number, default: 560 },
})

const cells = computed(() => {
  const out = []
  for (let i = 0; i < props.matrix.length; i++) {
    for (let j = 0; j < props.matrix[i].length; j++) {
      out.push([j, i, props.matrix[i][j]])
    }
  }
  return out
})

const option = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: {
    backgroundColor: '#1c2333', borderColor: '#1f2d40', textStyle: { color: '#f1f5f9' },
    formatter: (p) => `${props.labels[p.value[1]]} × ${props.labels[p.value[0]]}<br/>相關係數: <b>${p.value[2]}</b>`,
  },
  grid: { left: 110, right: 30, top: 20, bottom: 110 },
  xAxis: { type: 'category', data: props.labels, axisLabel: { color: '#94a3b8', rotate: 40, fontSize: 10 }, splitArea: { show: true } },
  yAxis: { type: 'category', data: props.labels, axisLabel: { color: '#94a3b8', fontSize: 10 }, splitArea: { show: true } },
  visualMap: {
    min: -1, max: 1, calculable: true, orient: 'vertical', right: 0, top: 'center',
    inRange: { color: ['#ef4444', '#1c2333', '#3b82f6'] },
    textStyle: { color: '#94a3b8' },
  },
  series: [{
    type: 'heatmap', data: cells.value,
    label: { show: true, formatter: (p) => p.value[2], fontSize: 9, color: '#f1f5f9' },
    itemStyle: { borderColor: '#0a0e1a', borderWidth: 1 },
  }],
}))
</script>

<style scoped>
.corr-wrap {
  background: rgba(17, 24, 39, 0.6);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 8px;
}
</style>
