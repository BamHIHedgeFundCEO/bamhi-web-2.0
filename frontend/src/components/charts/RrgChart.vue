<!--
  RrgChart.vue — RRG 板塊輪動圖 (對應 _sector_charts.render_rrg_tab / trail)
  四象限背景 + 角落象限標籤 + 中軸 100 + 散點/軌跡，支援滑鼠滾輪縮放。
  mode: 'snapshot' = 即時點位；'trail' = N 日軌跡線。
-->
<template>
  <div class="rrg-wrap">
    <VChart :option="option" :style="{ height: height + 'px', width: '100%' }" autoresize @click="onClick" />
    <p v-if="hasAbsTrend" class="rrg-legend">
      <span class="dot solid"></span>實心＝絕對趨勢多頭（Close &gt; MA60 &gt; MA200）
      <span class="dot hollow"></span>空心＝非多頭，相對位置可能只是抗跌
    </p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import '@/lib/echarts'

const props = defineProps({
  points: { type: Array, default: () => [] },
  mode: { type: String, default: 'snapshot' },
  trailDays: { type: Number, default: 10 },
  height: { type: Number, default: 560 },
})
const emit = defineEmits(['select'])

function onClick(params) {
  const sector = params?.data?._sector
  if (sector) emit('select', sector)
}

// 舊版預算 JSON 沒有 abs_up 欄位 → 不顯示圖例，避免說明與實際樣式不符
const hasAbsTrend = computed(() => props.points.some((p) => p.abs_up === true || p.abs_up === false))

// 動態軸範圍 (留較大 padding 避免標籤被切)
const bounds = computed(() => {
  const rs = []
  const ms = []
  for (const p of props.points) {
    if (props.mode === 'trail') {
      p.points.slice(-props.trailDays).forEach(([r, m]) => { rs.push(r); ms.push(m) })
    } else {
      rs.push(p.rs_ratio); ms.push(p.rs_momentum)
    }
  }
  if (!rs.length) return { xMin: 90, xMax: 110, yMin: 90, yMax: 110 }
  const pad = 4
  return {
    xMin: +(Math.min(...rs, 99) - pad).toFixed(1), xMax: +(Math.max(...rs, 101) + pad).toFixed(1),
    yMin: +(Math.min(...ms, 99) - pad).toFixed(1), yMax: +(Math.max(...ms, 101) + pad).toFixed(1),
  }
})

// 絕對趨勢樣式：實心＝Close > MA60 > MA200(真多頭)；空心＝非多頭。
// RRG 兩軸已除以 SPY，只看象限無法分辨「強勢」與「抗跌但絕對在跌」——空心點就是後者。
// abs_up 為 null/undefined(區間不足算 MA200、或舊版預算 JSON)時退回實心，維持原樣式。
function markStyle(p) {
  return p.abs_up === false
    ? { color: 'transparent', borderColor: p.color, borderWidth: 2.5 }
    : { color: p.color, borderColor: '#fff', borderWidth: 1.5 }
}
function absTrendText(p) {
  if (p.abs_up === true) return '絕對趨勢：<b>多頭</b>（Close &gt; MA60 &gt; MA200）'
  if (p.abs_up === false) return '絕對趨勢：<b style="color:#f87171">非多頭</b> — 相對位置可能只是抗跌'
  return ''
}

const QUAD_AREAS = {
  silent: true,
  data: [
    [{ xAxis: 100, yAxis: 100, itemStyle: { color: 'rgba(34,197,94,0.07)' } }, { xAxis: 200, yAxis: 200 }],
    [{ xAxis: 100, yAxis: 0, itemStyle: { color: 'rgba(234,179,8,0.07)' } }, { xAxis: 200, yAxis: 100 }],
    [{ xAxis: 0, yAxis: 0, itemStyle: { color: 'rgba(239,68,68,0.07)' } }, { xAxis: 100, yAxis: 100 }],
    [{ xAxis: 0, yAxis: 100, itemStyle: { color: 'rgba(59,130,246,0.07)' } }, { xAxis: 100, yAxis: 200 }],
  ],
}
const CENTER_LINES = {
  silent: true, symbol: 'none',
  lineStyle: { type: 'dashed', color: 'rgba(255,255,255,0.25)' },
  data: [{ xAxis: 100 }, { yAxis: 100 }],
}

const option = computed(() => {
  const b = bounds.value
  const series = []

  if (props.mode === 'trail') {
    for (const p of props.points) {
      const tail = p.points.slice(-props.trailDays)
      if (tail.length < 2) continue
      series.push({
        type: 'line', showSymbol: false, data: tail, silent: true, z: 2,
        lineStyle: { color: p.color, width: 2.5, type: p.abs_up === false ? 'dashed' : 'solid' },
      })
      series.push({
        type: 'scatter', data: [{ value: tail[tail.length - 1], _sector: p.sector }], symbolSize: 13,
        itemStyle: markStyle(p),
        label: { show: true, formatter: p.short, position: 'right', color: p.color, fontSize: 10 },
        name: p.sector, z: 3,
        tooltip: { formatter: `<b>${p.sector}</b><br/>${absTrendText(p)}<br/>點擊查看深度分析` },
      })
    }
  } else {
    for (const p of props.points) {
      series.push({
        type: 'scatter', data: [{ value: [p.rs_ratio, p.rs_momentum], _sector: p.sector }], symbolSize: 14,
        itemStyle: markStyle(p),
        label: { show: true, formatter: p.short, position: 'right', color: p.color, fontSize: 10 },
        name: p.sector,
        tooltip: { formatter: `<b>${p.sector}</b><br/>RS-Ratio: ${p.rs_ratio}<br/>RS-Momentum: ${p.rs_momentum}<br/>${p.label}<br/>${absTrendText(p)}<br/>點擊查看深度分析` },
        z: 3,
      })
    }
  }

  // 四象限角落標籤（放在可視範圍四角）
  const cornerLabel = (x, y, text, color, align, vAlign) => ({
    value: [x, y], symbolSize: 0, silent: true,
    label: { show: true, formatter: text, color, fontWeight: 'bold', fontSize: 12, align, verticalAlign: vAlign },
  })
  series.push({
    type: 'scatter', z: 1, silent: true,
    data: [
      cornerLabel(b.xMax, b.yMax, '領先 Leading', '#22c55e', 'right', 'top'),
      cornerLabel(b.xMax, b.yMin, '轉弱 Weakening', '#eab308', 'right', 'bottom'),
      cornerLabel(b.xMin, b.yMin, '落後 Lagging', '#ef4444', 'left', 'bottom'),
      cornerLabel(b.xMin, b.yMax, '改善 Improving', '#3b82f6', 'left', 'top'),
    ],
  })

  if (series.length) {
    series[0] = { ...series[0], markArea: QUAD_AREAS, markLine: CENTER_LINES }
  }

  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item', backgroundColor: '#1c2333', borderColor: '#1f2d40', textStyle: { color: '#f1f5f9' } },
    grid: { left: 64, right: 72, top: 24, bottom: 50 },
    dataZoom: [
      { type: 'inside', xAxisIndex: 0, filterMode: 'none' },
      { type: 'inside', yAxisIndex: 0, filterMode: 'none' },
    ],
    xAxis: { type: 'value', name: 'RS-Ratio（強度）', min: b.xMin, max: b.xMax, nameLocation: 'middle', nameGap: 28, nameTextStyle: { color: '#94a3b8' }, axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { color: '#1f2d40', opacity: 0.4 } } },
    yAxis: { type: 'value', name: 'RS-Momentum（動能）', min: b.yMin, max: b.yMax, nameTextStyle: { color: '#94a3b8' }, axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { color: '#1f2d40', opacity: 0.4 } } },
    series,
  }
})
</script>

<style scoped>
.rrg-wrap {
  background: rgba(17, 24, 39, 0.6);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 8px;
}
.rrg-legend {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin: 4px 0 2px;
  padding-left: 4px;
  font-size: 12px;
  color: #94a3b8;
}
.rrg-legend .dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex: none;
}
.rrg-legend .dot:not(:first-child) {
  margin-left: 12px;
}
.rrg-legend .dot.solid {
  background: #94a3b8;
  border: 1.5px solid #fff;
}
.rrg-legend .dot.hollow {
  background: transparent;
  border: 2px solid #94a3b8;
}
</style>
