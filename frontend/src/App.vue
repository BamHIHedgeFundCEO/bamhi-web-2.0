<template>
  <RouterView />
  <Toast />
</template>

<script setup>
import { onMounted } from 'vue'
import { RouterView } from 'vue-router'
import Toast from '@/components/ui/Toast.vue'
import { useAuthStore } from '@/stores/auth'

// App 啟動時還原 Supabase session
const auth = useAuthStore()
onMounted(() => auth.initialize())
</script>
