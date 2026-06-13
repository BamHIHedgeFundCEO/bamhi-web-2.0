import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

/**
 * 路由表。需登入的頁面標記 meta.requiresAuth = true，
 * 由下方 navigation guard 統一攔截 (§1.3)。
 * 各功能 View 先以動態 import 佔位，模組遷移時逐一補上。
 */
const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true },
  },
  // 登入後的頁面共用 AppShell（頂部導覽列）
  {
    path: '/',
    component: () => import('@/views/AppShell.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', name: 'home', component: () => import('@/views/HomeView.vue') },
      { path: 'macro', name: 'macro', component: () => import('@/views/MacroMarketView.vue') },
      { path: 'dark-pool', name: 'darkPool', component: () => import('@/views/DarkPoolView.vue') },
      { path: 'sector-strength', name: 'sectorStrength', component: () => import('@/views/SectorStrengthView.vue') },
      { path: 'world-sectors', name: 'worldSectors', component: () => import('@/views/WorldSectorsView.vue') },
      { path: 'models', name: 'models', component: () => import('@/views/TradingModelsView.vue') },
      { path: 'sector-rotation', name: 'sectorRotation', component: () => import('@/views/SectorRotationView.vue') },
      { path: 'search', name: 'search', component: () => import('@/views/SearchView.vue') },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// ⚠️ 僅本地開發預覽用：VITE_AUTH_DISABLED=true 時略過登入檢查。
// import.meta.env.DEV 確保此 bypass 不會出現在 production build。
const AUTH_DISABLED = import.meta.env.DEV && import.meta.env.VITE_AUTH_DISABLED === 'true'

// ── Navigation Guard：未登入者導向 /login ──
router.beforeEach(async (to) => {
  if (AUTH_DISABLED) return true

  const auth = useAuthStore()
  if (!auth.initialized) {
    await auth.initialize()
  }

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  // 已登入者不該再看到登入頁
  if (to.name === 'login' && auth.isAuthenticated) {
    return { name: 'home' }
  }

  return true
})

export default router
