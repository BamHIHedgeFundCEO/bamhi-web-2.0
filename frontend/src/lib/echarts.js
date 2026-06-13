/**
 * ECharts 按需註冊 (§1.1 統計圖表引擎)。
 * 只註冊用到的元件以控制 bundle 體積；vue-echarts 的 <VChart> 由此驅動。
 */
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import {
  LineChart,
  BarChart,
  TreemapChart,
  CandlestickChart,
  ScatterChart,
  HeatmapChart,
} from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,
  DataZoomComponent,
  VisualMapComponent,
} from 'echarts/components'

use([
  CanvasRenderer,
  LineChart,
  BarChart,
  TreemapChart,
  CandlestickChart,
  ScatterChart,
  HeatmapChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,
  DataZoomComponent,
  VisualMapComponent,
])

// 深色主題共用樣式 (對應 plotly_dark + Design Tokens)
export const DARK_GRID = '#1f2d40'
export const DARK_AXIS_LABEL = '#94a3b8'
export const RECESSION_FILL = 'rgba(127, 140, 141, 0.30)'
