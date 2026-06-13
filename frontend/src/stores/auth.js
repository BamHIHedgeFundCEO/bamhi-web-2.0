import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { supabase } from '@/lib/supabase'

/**
 * 認證狀態 (§1.3)。
 * Supabase Auth 簽發 JWT → 這裡持有 session/user，
 * Axios client 從 supabase.auth.getSession() 取 token，
 * router guard 依 isAuthenticated 決定是否放行。
 */
export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const session = ref(null)
  const loading = ref(false)
  const initialized = ref(false)

  const isAuthenticated = computed(() => !!session.value?.access_token)

  /** App 啟動時呼叫一次：還原既有 session 並訂閱變動 */
  async function initialize() {
    if (initialized.value) return
    const {
      data: { session: existing },
    } = await supabase.auth.getSession()
    session.value = existing
    user.value = existing?.user ?? null

    supabase.auth.onAuthStateChange((_event, newSession) => {
      session.value = newSession
      user.value = newSession?.user ?? null
    })
    initialized.value = true
  }

  async function login(email, password) {
    loading.value = true
    try {
      const { data, error } = await supabase.auth.signInWithPassword({ email, password })
      if (error) throw error
      session.value = data.session
      user.value = data.user
      return data
    } finally {
      loading.value = false
    }
  }

  async function signup(email, password) {
    loading.value = true
    try {
      const { data, error } = await supabase.auth.signUp({ email, password })
      if (error) throw error
      return data
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    await supabase.auth.signOut()
    session.value = null
    user.value = null
  }

  return {
    user,
    session,
    loading,
    initialized,
    isAuthenticated,
    initialize,
    login,
    signup,
    logout,
  }
})
