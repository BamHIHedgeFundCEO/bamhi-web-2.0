import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '@/api/client'

/** 板塊輪動狀態。運算全在後端 (§3.1)，前端只請求 → 渲染。 */
export const useSectorRotationStore = defineStore('sectorRotation', () => {
  const sectors = ref([]) // [{ name, tickers, leaders }]
  const signals = ref(null) // { period, signals: [...] }
  const signalsLoading = ref(false)
  const overview = ref(null)
  const detail = ref(null)
  const overviewLoading = ref(false)
  const detailLoading = ref(false)
  const error = ref(null)

  async function fetchSectors() {
    try {
      const res = await apiClient.get('/api/sector-rotation/sectors')
      sectors.value = res.data.sectors
    } catch (err) {
      error.value = err.response?.data?.detail ?? '板塊清單載入失敗'
    }
  }

  async function fetchOverview(period) {
    overviewLoading.value = true
    error.value = null
    try {
      const res = await apiClient.get('/api/sector-rotation/overview', { params: { period } })
      overview.value = res.data
    } catch (err) {
      error.value = err.response?.data?.detail ?? '全覽資料載入失敗'
      overview.value = null
    } finally {
      overviewLoading.value = false
    }
  }

  async function fetchDetail(sector, period) {
    detailLoading.value = true
    error.value = null
    try {
      const res = await apiClient.get('/api/sector-rotation/detail', { params: { sector, period } })
      detail.value = res.data
    } catch (err) {
      error.value = err.response?.data?.detail ?? '板塊明細載入失敗'
      detail.value = null
    } finally {
      detailLoading.value = false
    }
  }

  async function fetchSignals(period = '1y') {
    signalsLoading.value = true
    error.value = null
    try {
      const res = await apiClient.get('/api/sector-rotation/signals', { params: { period } })
      signals.value = res.data
    } catch (err) {
      error.value = err.response?.data?.detail ?? '訊號載入失敗'
      signals.value = null
    } finally {
      signalsLoading.value = false
    }
  }

  return {
    sectors, signals, signalsLoading, overview, detail, overviewLoading, detailLoading, error,
    fetchSectors, fetchSignals, fetchOverview, fetchDetail,
  }
})
