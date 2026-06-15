<!-- LoginView.vue — Supabase Auth 登入/註冊 (§1.3) -->
<template>
  <div class="login-page">
    <div class="login-card">
      <h1 class="brand">🌌 BamHI Quant</h1>
      <p class="subtitle">避險基金級量化交易儀表板</p>

      <div v-if="!isSupabaseConfigured" class="cfg-notice">
        ⚠️ Supabase 金鑰尚未設定，登入功能停用。<br />
        請在 <code>frontend/.env.development</code> 填入 <code>VITE_SUPABASE_URL</code> 與
        <code>VITE_SUPABASE_ANON_KEY</code>，並設 <code>VITE_AUTH_DISABLED=false</code> 後重啟。
      </div>

      <form class="form" @submit.prevent="submit">
        <label class="field">
          <span>Email</span>
          <input v-model="email" type="email" autocomplete="email" required placeholder="you@example.com" />
        </label>
        <label class="field">
          <span>密碼</span>
          <input v-model="password" type="password" autocomplete="current-password" required placeholder="••••••••" />
        </label>

        <button class="submit-btn" type="submit" :disabled="auth.loading || !isSupabaseConfigured">
          {{ auth.loading ? '處理中…' : mode === 'login' ? '登入' : '註冊' }}
        </button>
      </form>

      <button class="toggle" type="button" @click="toggleMode">
        {{ mode === 'login' ? '還沒有帳號？前往註冊' : '已有帳號？前往登入' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { isSupabaseConfigured } from '@/lib/supabase'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const toast = useToastStore()

const mode = ref(route.query.mode === 'signup' ? 'signup' : 'login')
const email = ref('')
const password = ref('')

function toggleMode() {
  mode.value = mode.value === 'login' ? 'signup' : 'login'
}

async function submit() {
  try {
    if (mode.value === 'login') {
      await auth.login(email.value, password.value)
      toast.success('登入成功')
      router.replace(route.query.redirect || { name: 'home' })
    } else {
      await auth.signup(email.value, password.value)
      toast.success('註冊成功，請查收驗證信後登入')
      mode.value = 'login'
    }
  } catch (err) {
    toast.error(err?.message ?? '驗證失敗，請稍後再試')
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle at 50% 0%, #131c33 0%, var(--color-bg-base) 60%);
}
.login-card {
  width: 360px;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 36px 32px;
}
.brand {
  margin: 0;
  color: var(--color-accent);
  font-size: 22px;
}
.subtitle {
  margin: 6px 0 28px;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.cfg-notice {
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid var(--color-warning);
  color: var(--color-warning);
  padding: 12px 14px;
  border-radius: var(--radius-md);
  font-size: 12px;
  line-height: 1.6;
  margin-bottom: 20px;
}
.cfg-notice code { background: rgba(0, 0, 0, 0.3); padding: 1px 5px; border-radius: 4px; font-size: 11px; }
.form { display: flex; flex-direction: column; gap: 16px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field span {
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-secondary);
}
.field input {
  background: var(--color-bg-base);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 10px 12px;
  color: var(--color-text-primary);
  font-family: var(--font-mono);
  font-size: 14px;
}
.field input:focus {
  outline: none;
  border-color: var(--color-accent);
}
.submit-btn {
  margin-top: 8px;
  background: var(--grad-cyan);
  color: #06121a;
  border: none;
  border-radius: var(--radius-md);
  padding: 11px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: var(--shadow-glow);
}
.submit-btn:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 10px 28px rgba(80, 180, 230, 0.42); }
.submit-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.toggle {
  margin-top: 18px;
  width: 100%;
  background: none;
  border: none;
  color: var(--color-text-secondary);
  font-size: 12px;
  cursor: pointer;
}
.toggle:hover { color: var(--color-accent); }
</style>
