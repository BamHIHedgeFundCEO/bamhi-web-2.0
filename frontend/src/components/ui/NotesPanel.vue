<!--
  NotesPanel.vue — 交易筆記 (對應 Streamlit render_dynamic_chart 下方筆記區)
  依 category/module 向後端取 Markdown，轉換 Streamlit :color[..] 語法後渲染。
-->
<template>
  <section v-if="loading || hasNote" class="notes">
    <h3>📝 交易筆記與紀錄</h3>
    <div v-if="loading" class="ph">載入筆記…</div>
    <div v-else class="md" v-html="html"></div>
  </section>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { marked } from 'marked'
import apiClient from '@/api/client'

const props = defineProps({
  category: { type: String, required: true },
  module: { type: String, required: true },
})

const loading = ref(false)
const hasNote = ref(false)
const markdown = ref('')

// Streamlit :color[text] → 帶色 span
const COLOR_MAP = {
  green: '#16a34a', red: '#ef4444', orange: '#f59e0b', blue: '#3b82f6',
  violet: '#a855f7', brown: '#b45309', gray: '#6b7280',
}
function preprocess(md) {
  return md
    // :green[文字] → <span style=color:..>
    .replace(/:(\w+)\[([^\]]*)\]/g, (m, color, text) =>
      COLOR_MAP[color] ? `<span style="color:${COLOR_MAP[color]};font-weight:600">${text}</span>` : text,
    )
    // 簡單清掉 LaTeX 箭頭
    .replace(/\$\\rightarrow\$/g, '→')
    .replace(/\$\\to\$/g, '→')
}

const html = computed(() => marked.parse(preprocess(markdown.value)))

async function load() {
  loading.value = true
  hasNote.value = false
  try {
    const res = await apiClient.get('/api/notes', { params: { category: props.category, module: props.module } })
    hasNote.value = res.data.has_note
    markdown.value = res.data.has_note ? res.data.markdown : ''
  } catch {
    hasNote.value = false
  } finally {
    loading.value = false
  }
}

watch(() => [props.category, props.module], load, { immediate: true })
</script>

<style scoped>
.notes {
  margin-top: 28px;
  padding: 20px 24px;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}
.notes h3 { font-size: 15px; margin: 0 0 14px; color: var(--color-text-secondary); }
.ph { color: var(--color-text-muted); font-size: 13px; }
.md { color: var(--color-text-secondary); font-size: 13px; line-height: 1.75; }
.md :deep(h3) { color: var(--color-text-primary); font-size: 15px; margin: 18px 0 8px; }
.md :deep(h4) { color: var(--color-text-primary); font-size: 14px; margin: 14px 0 6px; }
.md :deep(h5) { color: var(--color-text-secondary); font-size: 13px; margin: 12px 0 6px; }
.md :deep(strong) { color: var(--color-text-primary); }
.md :deep(code) { background: var(--color-bg-raised); padding: 1px 6px; border-radius: 4px; color: var(--color-data-cyan); font-size: 12px; }
.md :deep(ul) { padding-left: 20px; margin: 6px 0; }
.md :deep(li) { margin: 3px 0; }
.md :deep(hr) { border: none; border-top: 1px solid var(--color-border); margin: 16px 0; }
.md :deep(a) { color: var(--color-accent); }
</style>
