<!--
  TopNav.vue — 全站頂部導覽列 (對應 Streamlit components/ui_layout.render_navbar)
  Logo + 導覽連結 (交易工具為下拉) + 個股搜尋框 + 使用者/登出。
-->
<template>
  <header class="nav">
    <RouterLink :to="{ name: 'home' }" class="logo">🌌 BamHI Quant</RouterLink>

    <nav class="links">
      <RouterLink :to="{ name: 'home' }" class="link" active-class="active" exact-active-class="active">首頁</RouterLink>
      <RouterLink :to="{ name: 'macro' }" class="link" active-class="active">總經市場</RouterLink>

      <div class="dropdown" @mouseenter="open = true" @mouseleave="open = false">
        <span class="link" :class="{ active: toolActive }">交易工具 ▾</span>
        <div v-show="open" class="menu">
          <RouterLink v-for="t in TOOLS" :key="t.name" :to="{ name: t.name }" class="menu-item" @click="open = false">{{ t.label }}</RouterLink>
        </div>
      </div>

      <RouterLink :to="{ name: 'models' }" class="link" active-class="active">交易模型</RouterLink>
    </nav>

    <form class="search" @submit.prevent="doSearch">
      <input v-model="q" type="text" placeholder="🔍 搜尋美股代碼 (AAPL)…" />
    </form>

    <div class="user">
      <span class="email mono">{{ auth.user?.email ?? 'dev' }}</span>
      <button class="logout" @click="logout">登出</button>
    </div>
  </header>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const open = ref(false)
const q = ref('')

const TOOLS = [
  { name: 'screener', label: '🎯 BamHI 模型選股' },
  { name: 'darkPool', label: '🕳️ 暗池異常資金監控' },
  { name: 'sectorRotation', label: '🔄 板塊輪動 + VCP' },
  { name: 'sectorStrength', label: '🧭 美股板塊強弱' },
  { name: 'worldSectors', label: '🐫 全球市場強弱' },
]
const toolActive = computed(() => TOOLS.some((t) => route.name === t.name))

function doSearch() {
  const t = q.value.trim().toUpperCase()
  if (!t) return
  router.push({ name: 'search', query: { q: t } })
  q.value = ''
}

async function logout() {
  await auth.logout()
  router.replace('/login')
}
</script>

<style scoped>
.nav {
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 12px 24px;
  background: rgba(10, 14, 26, 0.92);
  border-bottom: 1px solid var(--color-border);
  backdrop-filter: blur(8px);
}
.logo { color: var(--color-accent); font-size: 18px; font-weight: 700; flex-shrink: 0; }
.links { display: flex; align-items: center; gap: 6px; }
.link {
  color: var(--color-text-secondary);
  font-size: 14px;
  padding: 7px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  white-space: nowrap;
}
.link:hover { color: var(--color-text-primary); background: var(--color-bg-surface); }
.link.active { color: #fff; background: var(--color-bg-raised); }
.dropdown { position: relative; }
.menu {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 6px;
  background: var(--color-bg-raised);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 8px;
  min-width: 280px;
  box-shadow: 0 16px 36px rgba(0, 0, 0, 0.55);
}
.menu-item {
  display: block;
  color: var(--color-text-secondary);
  font-size: 15px;
  padding: 12px 16px;
  border-radius: var(--radius-md);
  white-space: nowrap;
}
.menu-item:hover { background: var(--color-bg-surface); color: var(--color-text-primary); }
.search { margin-left: auto; }
.search input {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  color: var(--color-text-primary);
  padding: 8px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  width: 220px;
}
.search input:focus { outline: none; border-color: var(--color-accent); }
.user { display: flex; align-items: center; gap: 12px; flex-shrink: 0; }
.email { color: var(--color-text-muted); font-size: 11px; }
.logout {
  background: none;
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  padding: 6px 12px;
  border-radius: var(--radius-md);
  font-size: 12px;
  cursor: pointer;
}
.logout:hover { border-color: var(--color-bear); color: var(--color-bear); }
</style>
