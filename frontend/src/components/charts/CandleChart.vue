<!--
  CandleChart.vue — K 線 + 多條均線 + 可選內部人買賣標記
  insiderMarks: { buys: [{date,price,name,amount}], sells: [...] }
-->
<template>
  <div class="candle-wrap">
    <VChart :option="option" :style="{ height: height + 'px', width: '100%' }" autoresize />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import '@/lib/echarts'

const props = defineProps({
  dates: { type: Array, default: () => [] },
  candle: { type: Array, default: () => [] }, // [[o,c,l,h], ...]
  mas: { type: Object, default: () => ({}) }, // { MA10:[...], MA20:[...], ... }
  log: { type: Boolean, default: true },
  height: { type: Number, default: 460 },
  insiderMarks: { type: Object, default: () => ({ buys: [], sells: [] }) },
})

const MA_COLORS = { MA10: '#f59e0b', MA20: '#fbbf24', MA60: '#ef4444', MA120: '#a855f7', MA200: '#22d3ee' }

const option = computed(() => {
  const series = [
    {
      name: '指數 K 線', type: 'candlestick', data: props.candle,
      itemStyle: { color: '#10b981', color0: '#ef4444', borderColor: '#10b981', borderColor0: '#ef4444' },
    },
  ]

  for (const [name, color] of Object.entries(MA_COLORS)) {
    if (props.mas[name]) {
      series.push({ name, type: 'line', showSymbol: false, data: props.mas[name], lineStyle: { color, width: 1.4 }, itemStyle: { color } })
    }
  }

  const buys = props.insiderMarks?.buys ?? []
  const sells = props.insiderMarks?.sells ?? []

  const mkScatter = (name, data, color, rotate = 0) => ({
    name,
    type: 'scatter',
    symbol: 'triangle',
    symbolRotate: rotate,
    symbolSize: 13,
    itemStyle: { color },
    data: data.map(m => ({ value: [m.date, m.price], name: m.name, amount: m.amount })),
    tooltip: {
      formatter: (p) => {
        const d = p.data
        return `${d.value[0]}<br><b style="color:${color}">${d.name}</b><br>$${Number(d.amount).toLocaleString()}`
      },
    },
    z: 10,
  })

  if (buys.length) series.push(mkScatter('公開買入 (P)', buys, '#22c55e'))
  if (sells.length) series.push(mkScatter('公開賣出 (S)', sells, '#ef4444', 180))

  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', backgroundColor: '#1c2333', borderColor: '#1f2d40', textStyle: { color: '#f1f5f9' } },
    legend: { top: 6, textStyle: { color: '#94a3b8' }, inactiveColor: '#475569' },
    grid: { left: 60, right: 20, top: 40, bottom: 60 },
    xAxis: { type: 'category', data: props.dates, axisLabel: { color: '#94a3b8' }, axisLine: { lineStyle: { color: '#1f2d40' } } },
    yAxis: { type: props.log ? 'log' : 'value', scale: true, axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { color: '#1f2d40', opacity: 0.4 } } },
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 18, bottom: 18, borderColor: '#1f2d40', textStyle: { color: '#94a3b8' } }],
    series,
  }
})
</script>

<style scoped>
.candle-wrap {
  background: rgba(17, 24, 39, 0.6);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 8px;
}
</style>
