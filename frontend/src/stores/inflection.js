import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '@/api/client'

/**
 * 拐點篩選（Inflection Screener）— 左側池（基本面拐點）/ 右側池（技術確認）。
 * 資料由每週 GitHub Actions pipeline 寫入 Supabase，後端 /api/inflection 讀出。
 */
export const useInflectionStore = defineStore('inflection', () => {
  const runs = ref([])
  const runDate = ref(null)
  const left = ref([])
  const right = ref([])
  const loading = ref(false)
  const error = ref(null)

  async function fetchRuns() {
    try {
      const res = await apiClient.get('/api/inflection/runs')
      runs.value = res.data.runs ?? []
      if (!runDate.value && runs.value.length) runDate.value = runs.value[0]
    } catch (err) {
      error.value = err.response?.data?.detail ?? '取得 run 清單失敗'
    }
  }

  async function fetchPools(date = null) {
    loading.value = true
    error.value = null
    try {
      const params = date ? { run_date: date } : {}
      const [l, r] = await Promise.all([
        apiClient.get('/api/inflection/pool', { params: { side: 'left', ...params } }),
        apiClient.get('/api/inflection/pool', { params: { side: 'right', ...params } }),
      ])
      left.value = l.data.items ?? []
      right.value = r.data.items ?? []
      runDate.value = l.data.run_date ?? date
      if (l.data.error) error.value = l.data.error
    } catch (err) {
      error.value = err.response?.data?.detail ?? '請求失敗，請稍後再試'
      left.value = []
      right.value = []
    } finally {
      loading.value = false
    }
  }

  return { runs, runDate, left, right, loading, error, fetchRuns, fetchPools }
})
