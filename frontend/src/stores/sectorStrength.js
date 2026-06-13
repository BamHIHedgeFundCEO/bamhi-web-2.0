import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '@/api/client'

/**
 * 美股板塊強弱狀態。重運算全在後端，前端只請求 → 渲染 (§3.1)。
 */
export const useSectorStrengthStore = defineStore('sectorStrength', () => {
  const loading = ref(false)
  const error = ref(null)
  const overview = ref(null) // { as_of, items, strategies }

  const heatmap = ref(null) // { period, items }
  const heatmapLoading = ref(false)

  const rs = ref(null) // { benchmark, series }
  const rsLoading = ref(false)

  const holdings = ref(null) // { etf, holdings_count, golden, all }
  const holdingsLoading = ref(false)
  const holdingsError = ref(null)

  async function fetchOverview() {
    loading.value = true
    error.value = null
    try {
      const res = await apiClient.get('/api/sector-strength/metrics')
      overview.value = res.data
    } catch (err) {
      error.value = err.response?.data?.detail ?? '請求失敗，請稍後再試'
    } finally {
      loading.value = false
    }
  }

  async function fetchHeatmap(period) {
    heatmapLoading.value = true
    try {
      const res = await apiClient.get('/api/sector-strength/heatmap', { params: { period } })
      heatmap.value = res.data
    } catch (err) {
      error.value = err.response?.data?.detail ?? '熱力圖載入失敗'
    } finally {
      heatmapLoading.value = false
    }
  }

  async function fetchRelativeStrength(tickers) {
    if (!tickers.length) {
      rs.value = { benchmark: 'VTI', series: [] }
      return
    }
    rsLoading.value = true
    try {
      const res = await apiClient.get('/api/sector-strength/relative-strength', {
        params: { tickers: tickers.join(',') },
      })
      rs.value = res.data
    } catch (err) {
      error.value = err.response?.data?.detail ?? '相對強度載入失敗'
    } finally {
      rsLoading.value = false
    }
  }

  async function fetchHoldings(etf) {
    holdingsLoading.value = true
    holdingsError.value = null
    holdings.value = null
    try {
      const res = await apiClient.get('/api/sector-strength/holdings', { params: { etf } })
      holdings.value = res.data
    } catch (err) {
      holdingsError.value = err.response?.data?.detail ?? '成分股載入失敗'
    } finally {
      holdingsLoading.value = false
    }
  }

  return {
    loading, error, overview,
    heatmap, heatmapLoading, fetchHeatmap,
    rs, rsLoading, fetchRelativeStrength,
    holdings, holdingsLoading, holdingsError, fetchHoldings,
    fetchOverview,
  }
})
