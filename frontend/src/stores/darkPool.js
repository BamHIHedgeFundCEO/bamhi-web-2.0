import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '@/api/client'

/**
 * 暗池異常資金監控狀態。
 * 前端只負責請求 → 接收 JSON → 渲染 (§3.1)，不做任何運算。
 */
export const useDarkPoolStore = defineStore('darkPool', () => {
  const items = ref([])
  const asOf = ref(null)
  const loading = ref(false)
  const error = ref(null)

  async function fetchSurgeList() {
    loading.value = true
    error.value = null
    try {
      const res = await apiClient.get('/api/dark-pool/surge-list')
      items.value = res.data.items
      asOf.value = res.data.as_of
    } catch (err) {
      error.value = err.response?.data?.detail ?? '請求失敗，請稍後再試'
      items.value = []
    } finally {
      loading.value = false
    }
  }

  return { items, asOf, loading, error, fetchSurgeList }
})
