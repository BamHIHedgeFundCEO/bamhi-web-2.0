import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * 全局篩選狀態 (§2 對應 st.date_input / st.selectbox)。
 * 跨頁面共享的 ticker 與日期範圍統一放這裡，
 * 各模組元件讀取後組進 API 查詢參數。
 */
export const useFilterStore = defineStore('filter', () => {
  const ticker = ref('')

  // 預設日期範圍：近一年
  const today = new Date()
  const oneYearAgo = new Date()
  oneYearAgo.setFullYear(today.getFullYear() - 1)

  const dateRange = ref({
    start: oneYearAgo.toISOString().slice(0, 10),
    end: today.toISOString().slice(0, 10),
  })

  function setTicker(value) {
    ticker.value = (value || '').trim().toUpperCase()
  }

  function setDateRange(start, end) {
    dateRange.value = { start, end }
  }

  return { ticker, dateRange, setTicker, setDateRange }
})
