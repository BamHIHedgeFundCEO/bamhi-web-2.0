import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '@/api/client'

export const useInsiderStore = defineStore('insider', () => {
  // radar
  const radarItems = ref([])
  const radarLoading = ref(false)
  const radarError = ref(null)
  const cacheSize = ref(0)
  const lastUpdated = ref('')

  // stock
  const stockItems = ref([])
  const stockLoading = ref(false)
  const stockError = ref(null)
  const stockSymbol = ref('')

  async function fetchRadar(days = 30, sort = 'buy_amount') {
    radarLoading.value = true
    radarError.value = null
    try {
      const res = await apiClient.get('/api/insider/radar', { params: { days, sort } })
      radarItems.value = res.data.items
      cacheSize.value = res.data.cache_size ?? 0
      lastUpdated.value = res.data.last_updated ?? ''
    } catch (err) {
      radarError.value = err.response?.data?.detail ?? '請求失敗，請稍後再試'
      radarItems.value = []
    } finally {
      radarLoading.value = false
    }
  }

  async function fetchStock(symbol) {
    if (stockSymbol.value === symbol && stockItems.value.length) return
    stockLoading.value = true
    stockError.value = null
    stockSymbol.value = symbol
    try {
      const res = await apiClient.get('/api/insider/stock', { params: { symbol, limit: 50 }, timeout: 60000 })
      stockItems.value = res.data.items
    } catch (err) {
      stockError.value = err.response?.data?.detail ?? '請求失敗，請稍後再試'
      stockItems.value = []
    } finally {
      stockLoading.value = false
    }
  }

  function resetStock() {
    stockItems.value = []
    stockSymbol.value = ''
    stockError.value = null
  }

  return {
    radarItems, radarLoading, radarError, cacheSize, lastUpdated,
    stockItems, stockLoading, stockError, stockSymbol,
    fetchRadar, fetchStock, resetStock,
  }
})
