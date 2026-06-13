import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '@/api/client'

/** 個股深度檔案狀態。 */
export const useEquityStore = defineStore('equity', () => {
  const loading = ref(false)
  const error = ref(null)
  const profile = ref(null)

  async function fetchProfile(ticker, period = '2y', interval = '1d') {
    loading.value = true
    error.value = null
    profile.value = null
    try {
      const res = await apiClient.get('/api/equity/profile', { params: { ticker, period, interval } })
      profile.value = res.data
    } catch (err) {
      error.value = err.response?.data?.detail ?? '查詢失敗，請稍後再試'
    } finally {
      loading.value = false
    }
  }

  return { loading, error, profile, fetchProfile }
})
