import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '@/api/client'

/** 交易模型每日戰報狀態 (Alpha / Genesis 雙引擎 + 時光機)。 */
export const useModelsStore = defineStore('models', () => {
  const dates = ref([]) // [{ raw, label }]
  const reports = ref({}) // key `${engine}:${date}` → report
  const loading = ref(false)
  const error = ref(null)

  async function fetchDates() {
    try {
      const res = await apiClient.get('/api/models/dates')
      dates.value = res.data.dates
    } catch (err) {
      error.value = err.response?.data?.detail ?? '日期載入失敗'
    }
  }

  async function fetchReport(engine, date) {
    const key = `${engine}:${date}`
    loading.value = true
    error.value = null
    try {
      const res = await apiClient.get('/api/models/report', { params: { engine, date } })
      reports.value[key] = res.data
      return res.data
    } catch (err) {
      error.value = err.response?.data?.detail ?? '戰報載入失敗'
    } finally {
      loading.value = false
    }
  }

  return { dates, reports, loading, error, fetchDates, fetchReport }
})
