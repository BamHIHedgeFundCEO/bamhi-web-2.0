/**
 * 總經各指標 → ECharts option 產生器。
 * 移植自 data_engine 各模組的 plot_chart()，樣式集中在前端。
 * 後端只供原始 data；此處負責顏色 / 軸 / 衰退帶 / 參考線。
 */
import { recessionMarkArea } from '@/lib/recessions'
import { DARK_GRID, DARK_AXIS_LABEL } from '@/lib/echarts'

/** rows → [[date, value], ...]，略過 null */
function toPairs(rows, col) {
  return rows
    .filter((r) => r[col] !== null && r[col] !== undefined)
    .map((r) => [r.date, r[col]])
}

const pctAxis = (name) => ({
  type: 'value',
  name,
  nameTextStyle: { color: DARK_AXIS_LABEL },
  axisLabel: { color: DARK_AXIS_LABEL, formatter: '{value}%' },
  splitLine: { lineStyle: { color: DARK_GRID, opacity: 0.4 } },
})

const refLine = (values) => ({
  symbol: 'none',
  silent: true,
  lineStyle: { type: 'dashed', color: '#6b7280', width: 1 },
  data: values.map((y) => ({ yAxis: y })),
})

// ── 各指標 builder ──
const builders = {
  _single(rows, col, name, color) {
    return {
      yAxis: pctAxis('Yield (%)'),
      series: [
        {
          name,
          type: 'line',
          showSymbol: false,
          data: toPairs(rows, col),
          lineStyle: { color, width: 1.8 },
          itemStyle: { color },
          areaStyle: { color, opacity: 0.1 },
          markArea: recessionMarkArea(),
        },
      ],
    }
  },

  DGS10(rows) {
    return builders._single(rows, 'DGS10', '10Y Yield', '#3b82f6')
  },
  DGS2(rows) {
    return builders._single(rows, 'DGS2', '2Y Yield', '#ef4444')
  },

  SPREAD_10_2(rows) {
    return {
      yAxis: [
        pctAxis('Yield (%)'),
        { ...pctAxis('Spread (%)'), position: 'right', splitLine: { show: false } },
      ],
      series: [
        { name: '10Y', type: 'line', showSymbol: false, yAxisIndex: 0, data: toPairs(rows, 'DGS10'), lineStyle: { color: '#3b82f6', width: 1.5 }, itemStyle: { color: '#3b82f6' }, markArea: recessionMarkArea() },
        { name: '2Y', type: 'line', showSymbol: false, yAxisIndex: 0, data: toPairs(rows, 'DGS2'), lineStyle: { color: '#ef4444', width: 1.5 }, itemStyle: { color: '#ef4444' } },
        { name: 'Spread', type: 'line', showSymbol: false, yAxisIndex: 1, data: toPairs(rows, 'Spread'), lineStyle: { color: '#fbbf24', width: 1 }, itemStyle: { color: '#fbbf24' }, areaStyle: { color: '#fbbf24', opacity: 0.25 } },
      ],
    }
  },

  MACRO_TRIO(rows) {
    const series = [
      { name: '名目 GDP 成長率 (g)', type: 'line', showSymbol: false, data: toPairs(rows, 'GDP_Growth'), lineStyle: { color: '#3b82f6', width: 2.5 }, itemStyle: { color: '#3b82f6' }, markArea: recessionMarkArea() },
      { name: '名目利率 (i)', type: 'line', showSymbol: false, data: toPairs(rows, 'FEDFUNDS'), lineStyle: { color: '#10b981', width: 2.2, type: 'dashed' }, itemStyle: { color: '#10b981' } },
    ]
    if (rows.some((r) => r.r_star !== null && r.r_star !== undefined)) {
      series.push({ name: '自然利率 (r-star)', type: 'line', showSymbol: false, connectNulls: true, data: toPairs(rows, 'r_star'), lineStyle: { color: '#fbbf24', width: 1.5, type: 'dotted' }, itemStyle: { color: '#fbbf24' } })
    }
    return { yAxis: pctAxis('百分比 (%)'), series }
  },

  BREADTH_SP500(rows) {
    return {
      yAxis: [
        { type: 'log', name: 'S&P 500', scale: true, nameTextStyle: { color: DARK_AXIS_LABEL }, axisLabel: { color: DARK_AXIS_LABEL }, splitLine: { lineStyle: { color: DARK_GRID, opacity: 0.4 } } },
        { type: 'value', name: '% Above MA', position: 'right', min: 0, max: 100, nameTextStyle: { color: DARK_AXIS_LABEL }, axisLabel: { color: DARK_AXIS_LABEL, formatter: '{value}%' }, splitLine: { show: false } },
      ],
      series: [
        { name: 'S&P 500', type: 'line', showSymbol: false, yAxisIndex: 0, data: toPairs(rows, 'value'), lineStyle: { color: '#ffffff', width: 2 }, itemStyle: { color: '#ffffff' }, markArea: recessionMarkArea([['2007-12-01', '2009-06-30'], ['2020-02-01', '2020-04-30']]) },
        { name: '% > 200MA', type: 'line', showSymbol: false, yAxisIndex: 1, data: toPairs(rows, 'breadth_200'), lineStyle: { color: '#1abc9c', width: 1.5 }, itemStyle: { color: '#1abc9c' }, markLine: refLine([15, 50, 85]) },
        { name: '% > 50MA', type: 'line', showSymbol: false, yAxisIndex: 1, data: toPairs(rows, 'breadth_50'), lineStyle: { color: '#e67e22', width: 1.5 }, itemStyle: { color: '#e67e22' } },
      ],
    }
  },

  // 情緒為雙 tab，subTab: 'naaim' | 'aaii'
  SENTIMENT_COMBO(rows, subTab = 'naaim') {
    const spSeries = {
      name: 'S&P 500', type: 'line', showSymbol: false, yAxisIndex: 1,
      data: toPairs(rows, 'SP500'),
      lineStyle: { color: 'rgba(255,255,255,0.4)', width: 1.5 }, itemStyle: { color: 'rgba(255,255,255,0.5)' },
      connectNulls: true,
    }
    const spAxis = { type: 'log', name: 'S&P 500 (Log)', position: 'right', scale: true, nameTextStyle: { color: DARK_AXIS_LABEL }, axisLabel: { color: DARK_AXIS_LABEL }, splitLine: { show: false } }

    if (subTab === 'aaii') {
      return {
        yAxis: [{ type: 'value', name: 'AAII Spread', nameTextStyle: { color: DARK_AXIS_LABEL }, axisLabel: { color: DARK_AXIS_LABEL }, splitLine: { lineStyle: { color: DARK_GRID, opacity: 0.4 } } }, spAxis],
        series: [
          { name: 'AAII Spread (Weekly)', type: 'line', showSymbol: false, yAxisIndex: 0, connectNulls: true, data: toPairs(rows, 'AAII_Spread'), lineStyle: { color: 'rgba(102,255,204,0.6)', width: 1 }, itemStyle: { color: 'rgba(102,255,204,0.6)' }, markLine: refLine([-25, 25]) },
          { name: 'MA20', type: 'line', showSymbol: false, yAxisIndex: 0, connectNulls: true, data: toPairs(rows, 'AAII_MA20'), lineStyle: { color: '#00cc66', width: 2.5 }, itemStyle: { color: '#00cc66' } },
          spSeries,
        ],
      }
    }
    // naaim
    return {
      yAxis: [{ type: 'value', name: 'NAAIM Exposure', nameTextStyle: { color: DARK_AXIS_LABEL }, axisLabel: { color: DARK_AXIS_LABEL }, splitLine: { lineStyle: { color: DARK_GRID, opacity: 0.4 } } }, spAxis],
      series: [
        { name: 'NAAIM (Weekly)', type: 'line', showSymbol: false, yAxisIndex: 0, connectNulls: true, data: toPairs(rows, 'NAAIM'), lineStyle: { color: 'rgba(255,204,102,0.8)', width: 1 }, itemStyle: { color: 'rgba(255,204,102,0.8)' }, markLine: refLine([40, 100]) },
        { name: 'MA20', type: 'line', showSymbol: false, yAxisIndex: 0, connectNulls: true, data: toPairs(rows, 'NAAIM_MA20'), lineStyle: { color: '#ff4d4d', width: 2.5 }, itemStyle: { color: '#ff4d4d' } },
        spSeries,
      ],
    }
  },
}

export function buildMacroOption(indicatorId, rows, subTab) {
  const builder = builders[indicatorId]
  if (!builder) return { series: [] }
  return builder(rows, subTab)
}

/** 情緒指標需要雙 tab */
export const HAS_SUBTABS = {
  SENTIMENT_COMBO: [
    { key: 'naaim', label: '👔 機構情緒 (NAAIM)' },
    { key: 'aaii', label: '🧑‍🤝‍🧑 散戶情緒 (AAII)' },
  ],
}
