<!--
  Treemap.vue — ECharts treemap 熱力圖 (對應 Streamlit px.treemap)。
  以 RdYlGn 色階依「強弱分數」上色，群組 → 標的兩層階層。
-->
<template>
  <div class="tm-wrap">
    <VChart :option="option" :style="{ height: height + 'px', width: '100%' }" autoresize @click="onClick" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import '@/lib/echarts'

const props = defineProps({
  /** items: [{ ticker, name, group, price, chg_pct, score }] */
  items: { type: Array, default: () => [] },
  height: { type: Number, default: 520 },
})
const emit = defineEmits(['select'])

// 點擊葉節點 → 把該標的的原始資料拋出（群組標題無 _meta，會被忽略）
function onClick(params) {
  if (params?.data?._meta) emit('select', params.data._meta)
}

// RdYlGn 連續色階，midpoint=0
function colorFor(score) {
  const clamp = Math.max(-8, Math.min(8, score)) / 8 // -1..1
  if (clamp >= 0) {
    // 綠：0→#fee08b ... 1→#1a9850
    return lerp([254, 224, 139], [26, 152, 80], clamp)
  }
  // 紅：0→#fee08b ... -1→#d73027
  return lerp([254, 224, 139], [215, 48, 39], -clamp)
}
function lerp(a, b, t) {
  const c = a.map((x, i) => Math.round(x + (b[i] - x) * t))
  return `rgb(${c[0]},${c[1]},${c[2]})`
}

const treeData = computed(() => {
  const groups = {}
  for (const it of props.items) {
    if (!groups[it.group]) groups[it.group] = { name: it.group, children: [] }
    groups[it.group].children.push({
      name: it.ticker,
      value: 1,
      itemStyle: { color: colorFor(it.score) },
      _meta: it,
    })
  }
  return Object.values(groups)
})

const option = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: {
    backgroundColor: '#1c2333',
    borderColor: '#1f2d40',
    textStyle: { color: '#f1f5f9' },
    formatter: (info) => {
      const m = info.data?._meta
      if (!m) return `<b>${info.name}</b>`
      return `<b>${m.ticker}</b> ${m.name}<br/>現價: ${m.price?.toFixed?.(2)}<br/>漲跌: ${m.chg_pct >= 0 ? '+' : ''}${m.chg_pct?.toFixed?.(2)}%`
    },
  },
  series: [
    {
      type: 'treemap',
      roam: false,
      nodeClick: false,
      breadcrumb: { show: false },
      label: {
        show: true,
        formatter: (p) => {
          const m = p.data?._meta
          return m ? `{t|${m.ticker}}\n{p|${m.chg_pct >= 0 ? '+' : ''}${m.chg_pct.toFixed(2)}%}` : p.name
        },
        rich: {
          t: { fontSize: 13, fontWeight: 'bold', color: '#0a0e1a', fontFamily: 'JetBrains Mono' },
          p: { fontSize: 11, color: '#0a0e1a', fontFamily: 'JetBrains Mono' },
        },
      },
      upperLabel: { show: true, height: 22, color: '#f1f5f9', fontSize: 12 },
      itemStyle: { borderColor: '#0a0e1a', borderWidth: 1, gapWidth: 1 },
      levels: [
        { itemStyle: { borderColor: '#0a0e1a', borderWidth: 3, gapWidth: 3 } },
        { itemStyle: { borderColor: '#0a0e1a', borderWidth: 1, gapWidth: 1 }, colorSaturation: [0.3, 0.6] },
      ],
      data: treeData.value,
    },
  ],
}))
</script>

<style scoped>
.tm-wrap {
  background: rgba(17, 24, 39, 0.6);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 8px;
}
</style>
