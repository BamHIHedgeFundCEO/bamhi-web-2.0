import { RECESSION_FILL } from '@/lib/echarts'

/** 美國衰退期間 (對應 Streamlit plot_chart 內的 recessions 常數)。 */
export const RECESSIONS = [
  ['1990-07-01', '1991-03-31'],
  ['2001-03-01', '2001-11-30'],
  ['2007-12-01', '2009-06-30'],
  ['2020-02-01', '2020-04-30'],
]

/**
 * 產生掛在某條 series 上的 markArea，用來畫灰色衰退遮罩。
 * @param {string[][]} ranges 預設使用全部 RECESSIONS
 */
export function recessionMarkArea(ranges = RECESSIONS) {
  return {
    silent: true,
    itemStyle: { color: RECESSION_FILL },
    data: ranges.map(([start, end]) => [{ xAxis: start }, { xAxis: end }]),
  }
}
