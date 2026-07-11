<!--
  TopNav.vue — 全站頂部導覽列 (對應 Streamlit components/ui_layout.render_navbar)
  Logo + 導覽連結 (交易工具為下拉) + 個股搜尋框 + 使用者/登出。

  觸控相容：下拉在無 hover 裝置（平板/手機）用點擊開關，桌機維持懸停；
  ≤ 820px 收成漢堡選單（連結/搜尋/登出進垂直面板）。
-->
<template>
  <header class="nav" ref="navEl">
    <RouterLink :to="{ name: 'home' }" class="logo">🌌 BamHI Quant</RouterLink>

    <button class="burger" :aria-expanded="mobileOpen" aria-label="選單" @click="mobileOpen = !mobileOpen">
      {{ mobileOpen ? '✕' : '☰' }}
    </button>

    <div class="nav-body" :class="{ open: mobileOpen }">
      <nav class="links">
        <RouterLink :to="{ name: 'home' }" class="link" active-class="active" exact-active-class="active">首頁</RouterLink>
        <RouterLink :to="{ name: 'macro' }" class="link" active-class="active">總經市場</RouterLink>

        <div class="dropdown" @mouseenter="hasHover && (open = true)" @mouseleave="hasHover && (open = false)">
          <button class="link drop-btn" :class="{ active: toolActive }" @click="open = !open">
            交易工具 {{ open ? '▴' : '▾' }}
          </button>
          <div v-show="open" class="menu">
            <RouterLink v-for="t in TOOLS" :key="t.name" :to="{ name: t.name }" class="menu-item" @click="closeAll">{{ t.label }}</RouterLink>
          </div>
        </div>

        <RouterLink :to="{ name: 'models' }" class="link" active-class="active">交易模型</RouterLink>
        <RouterLink :to="{ name: 'guide' }" class="link" active-class="active">使用說明</RouterLink>
      </nav>

      <form class="search" @submit.prevent="doSearch">
        <input v-model="q" type="text" placeholder="🔍 搜尋美股代碼 (AAPL)…" />
      </form>

      <div class="user">
        <span class="email mono">{{ auth.user?.email ?? 'dev' }}</span>
        <button class="logout" @click="logout">登出</button>
      </div>
    </div>
  </header>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const open = ref(false)        // 交易工具下拉
const mobileOpen = ref(false)  // 漢堡面板
const q = ref('')
const navEl = ref(null)

// 有滑鼠（可 hover）的裝置才用懸停開關；觸控裝置用點擊
const hasHover = window.matchMedia('(hover: hover)').matches

const TOOLS = [
  { name: 'screener', label: '🎯 BamHI 模型選股' },
  { name: 'inflection', label: '📐 拐點篩選' },
  { name: 'darkPool', label: '🕳️ 暗池異常資金監控' },
  { name: 'sectorRotation', label: '🔄 板塊輪動 + VCP' },
  { name: 'sectorStrength', label: '🧭 美股板塊強弱' },
  { name: 'worldSectors', label: '🐫 全球市場強弱' },
  { name: 'insider', label: '🕵️ 內部人追蹤雷達' },
  { name: 'marketWatch', label: '🔭 市場觀察' },
  { name: 'smallCap', label: '💰 小市值策略' },
]
const toolActive = computed(() => TOOLS.some((t) => route.name === t.name))

function closeAll() {
  open.value = false
  mobileOpen.value = false
}

// 換頁自動收合（含搜尋跳轉）
watch(() => route.fullPath, closeAll)

// 點導覽列外側 → 收合下拉與面板（觸控裝置沒有 mouseleave）
function onDocClick(e) {
  if (navEl.value && !navEl.value.contains(e.target)) closeAll()
}
onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))

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
.burger {
  display: none;
  background: none; border: 1px solid var(--color-border); color: var(--color-text-primary);
  font-size: 18px; line-height: 1; padding: 6px 12px; border-radius: var(--radius-md); cursor: pointer;
}
.nav-body { display: flex; align-items: center; gap: 20px; flex: 1; min-width: 0; }
.links { display: flex; align-items: center; gap: 6px; }
.link {
  color: var(--color-text-secondary);
  font-size: 14px;
  padding: 7px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  white-space: nowrap;
}
.drop-btn { background: none; border: none; font-family: inherit; }
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

/* ── 平板 / 手機（≤ 820px）：漢堡選單 ── */
@media (max-width: 820px) {
  .burger { display: block; margin-left: auto; }
  .nav-body {
    display: none;
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
    padding: 14px 20px 18px;
    background: rgba(10, 14, 26, 0.98);
    border-bottom: 1px solid var(--color-border);
    max-height: calc(100vh - 60px);
    overflow-y: auto;
  }
  .nav-body.open { display: flex; }
  .links { flex-direction: column; align-items: stretch; }
  .link { padding: 12px 14px; font-size: 15px; }   /* 觸控目標放大 */
  .dropdown { position: static; }
  .menu {
    position: static;
    margin: 4px 0 4px 12px;
    box-shadow: none;
    min-width: 0;
    border-left: 2px solid var(--color-accent-cyan, #22d3ee);
    border-top: none; border-right: none; border-bottom: none;
    border-radius: 0;
    background: transparent;
    padding: 0;
  }
  .search { margin-left: 0; }
  .search input { width: 100%; box-sizing: border-box; }
  .user { justify-content: space-between; }
}
</style>
