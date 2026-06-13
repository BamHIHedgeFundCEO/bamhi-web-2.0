import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '@/api/client'

/**
 * 總經市場狀態。各指標取回的原始序列快取在 cache 中避免重複請求。
 * 前端只請求 → 接收 → 渲染 (§3.1)。
 */
export const useMacroStore = defineStore('macro', () => {
  const loading = ref(false)
  const error = ref(null)
  const current = ref(null) // { id, name, latest, data }
  const cache = ref({})

  async function fetchSeries(indicator) {
    error.value = null
    if (cache.value[indicator]) {
      current.value = cache.value[indicator]
      return
    }
    loading.value = true
    try {
      const res = await apiClient.get('/api/macro/series', { params: { indicator } })
      cache.value[indicator] = res.data
      current.value = res.data
    } catch (err) {
      error.value = err.response?.data?.detail ?? '請求失敗，請稍後再試'
      current.value = null
    } finally {
      loading.value = false
    }
  }

  return { loading, error, current, fetchSeries }
})
