import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '@/api/client'

export const useDualPoolStore = defineStore('dualPool', () => {
  // scores
  const scores = ref([])
  const scoresLoading = ref(false)
  const scoresError = ref(null)
  const currentSide = ref('left')

  // events（展開明細）
  const eventsMap = ref({})   // { [ticker]: { loading, error, items } }

  async function fetchScores(side = 'left') {
    currentSide.value = side
    scoresLoading.value = true
    scoresError.value = null
    try {
      const res = await apiClient.get('/api/dual-pool/scores', { params: { side } })
      scores.value = res.data.items ?? []
    } catch (err) {
      scoresError.value = err.response?.data?.detail ?? '請求失敗，請稍後再試'
      scores.value = []
    } finally {
      scoresLoading.value = false
    }
  }

  async function fetchEvents(ticker, days = 90) {
    if (!ticker) return
    const key = `${ticker}_${days}`
    if (eventsMap.value[key]?.items?.length) return   // 已快取

    eventsMap.value[key] = { loading: true, error: null, items: [] }
    try {
      const res = await apiClient.get(`/api/dual-pool/events/${ticker}`, { params: { days } })
      eventsMap.value[key] = { loading: false, error: null, items: res.data.events ?? [] }
    } catch (err) {
      eventsMap.value[key] = {
        loading: false,
        error: err.response?.data?.detail ?? '請求失敗',
        items: [],
      }
    }
  }

  function getEvents(ticker, days = 90) {
    return eventsMap.value[`${ticker}_${days}`] ?? { loading: false, error: null, items: [] }
  }

  function clearEvents() {
    eventsMap.value = {}
  }

  return {
    scores,
    scoresLoading,
    scoresError,
    currentSide,
    fetchScores,
    fetchEvents,
    getEvents,
    clearEvents,
  }
})
