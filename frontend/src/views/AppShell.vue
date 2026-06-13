<!-- AppShell.vue — 登入後的主框架：頂部導覽列 + 內容區 -->
<template>
  <div class="shell">
    <TopNav />
    <main class="shell-main">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { RouterView } from 'vue-router'
import TopNav from '@/components/ui/TopNav.vue'
</script>

<style scoped>
.shell { min-height: 100vh; }
.shell-main { min-height: calc(100vh - 50px); }
</style>
