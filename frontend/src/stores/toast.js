import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * Toast 通知 (§2 對應 st.error / st.warning / st.success)。
 * 任何元件呼叫 push() 即可彈出提示，由 <Toast> 容器渲染。
 */
let _id = 0

export const useToastStore = defineStore('toast', () => {
  const items = ref([])

  function push(message, type = 'info', timeout = 4000) {
    const id = ++_id
    items.value.push({ id, message, type })
    if (timeout > 0) {
      setTimeout(() => dismiss(id), timeout)
    }
    return id
  }

  function dismiss(id) {
    items.value = items.value.filter((t) => t.id !== id)
  }

  // 語義捷徑
  const success = (msg, t) => push(msg, 'success', t)
  const error = (msg, t) => push(msg, 'error', t)
  const warning = (msg, t) => push(msg, 'warning', t)
  const info = (msg, t) => push(msg, 'info', t)

  return { items, push, dismiss, success, error, warning, info }
})
