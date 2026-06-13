<!--
  TimeSeriesChart.vue — 可複用的 ECharts 時間序列封裝 (§1.1)
  純渲染：接收完整 ECharts option，套用深色主題預設並自動 resize。
  後續所有統計圖表模組共用此元件。
-->
<template>
  <div class="ts-chart">
    <VChart
      :option="mergedOption"
      :style="{ height: height + 'px', width: '100%' }"
      autoresize
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import '@/lib/echarts'
import { DARK_GRID, DARK_AXIS_LABEL } from '@/lib/echarts'

const props = defineProps({
  /** 完整 ECharts option（series / yAxis / 其餘軸設定由呼叫端提供） */
  option: { type: Object, required: true },
  height: { type: Number, default: 440 },
})

// 深色主題基底，呼叫端的 option 會覆蓋同名欄位
const BASE = {
  backgroundColor: 'transparent',
  textStyle: { color: DARK_AXIS_LABEL, fontFamily: 'Inter, sans-serif' },
  grid: { left: 56, right: 56, top: 48, bottom: 40, containLabel: false },
  tooltip: {
    trigger: 'axis',
    backgroundColor: '#1c2333',
    borderColor: DARK_GRID,
    textStyle: { color: '#f1f5f9' },
  },
  legend: {
    top: 8,
    textStyle: { color: DARK_AXIS_LABEL },
    inactiveColor: '#475569',
  },
  xAxis: {
    type: 'time',
    axisLine: { lineStyle: { color: DARK_GRID } },
    axisLabel: { color: DARK_AXIS_LABEL },
    splitLine: { show: true, lineStyle: { color: DARK_GRID, opacity: 0.4 } },
  },
}

const mergedOption = computed(() => ({ ...BASE, ...props.option }))
</script>

<style scoped>
.ts-chart {
  background: rgba(17, 24, 39, 0.6);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 8px;
}
</style>
