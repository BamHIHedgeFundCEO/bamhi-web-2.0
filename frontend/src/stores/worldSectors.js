import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '@/api/client'

/** 全球市場強弱狀態。運算全在後端，前端只請求 → 渲染 (§3.1)。 */
export const useWorldSectorsStore = defineStore('worldSectors', () => {
  const loading = ref(false)
  const error = ref(null)
  const data = ref(null) // { as_of, period, mode, items, strategies, groups }

  async function fetchMomentum(period) {
    loading.value = true
    error.value = null
    try {
      const res = await apiClient.get('/api/world-sectors/momentum', { params: { period } })
      data.value = res.data
    } catch (err) {
      error.value = err.response?.data?.detail ?? '請求失敗，請稍後再試'
      data.value = null
    } finally {
      loading.value = false
    }
  }

  return { loading, error, data, fetchMomentum }
})
