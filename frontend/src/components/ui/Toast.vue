<!-- Toast.vue — 全域通知容器，掛在 App.vue 根節點一次即可 (§2) -->
<template>
  <div class="toast-stack">
    <transition-group name="toast">
      <div
        v-for="t in toast.items"
        :key="t.id"
        class="toast"
        :class="t.type"
        @click="toast.dismiss(t.id)"
      >
        <span class="toast-icon">{{ icon(t.type) }}</span>
        <span class="toast-msg">{{ t.message }}</span>
      </div>
    </transition-group>
  </div>
</template>

<script setup>
import { useToastStore } from '@/stores/toast'

const toast = useToastStore()

function icon(type) {
  return { success: '✅', error: '🚨', warning: '⚠️', info: 'ℹ️' }[type] || 'ℹ️'
}
</script>

<style scoped>
.toast-stack {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 10px;
  pointer-events: none;
}
.toast {
  pointer-events: auto;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 260px;
  max-width: 380px;
  padding: 12px 16px;
  background: var(--color-bg-raised);
  border: 1px solid var(--color-border);
  border-left-width: 3px;
  border-radius: var(--radius-md);
  color: var(--color-text-primary);
  font-size: 13px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}
.toast.success { border-left-color: var(--color-bull); }
.toast.error   { border-left-color: var(--color-bear); }
.toast.warning { border-left-color: var(--color-warning); }
.toast.info    { border-left-color: var(--color-accent); }
.toast-msg { flex: 1; }

.toast-enter-active,
.toast-leave-active {
  transition: all 0.25s ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
</style>
