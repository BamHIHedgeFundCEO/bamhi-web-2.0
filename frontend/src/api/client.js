import axios from 'axios'
import { supabase } from '@/lib/supabase'

/**
 * 全專案唯一的 HTTP 出口 (§1.1)。
 * 元件內部禁止硬編碼 URL，一律 import apiClient 後呼叫。
 */
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// ── Request 攔截器：自動帶入 Supabase 簽發的 JWT ──
apiClient.interceptors.request.use(async (config) => {
  const {
    data: { session },
  } = await supabase.auth.getSession()
  if (session?.access_token) {
    config.headers.Authorization = `Bearer ${session.access_token}`
  }
  return config
})

// ── Response 攔截器：401 統一導回登入 ──
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      await supabase.auth.signOut()
      // 避免在非瀏覽器環境 (SSR) 出錯
      if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
        window.location.assign('/login')
      }
    }
    return Promise.reject(error)
  },
)

export default apiClient
