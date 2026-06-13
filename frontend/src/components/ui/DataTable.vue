<!--
  DataTable.vue — 對應 st.dataframe() / st.table() (§2)
  通用資料表：欄位定義 + 列資料，支援每格自訂顏色 (漲綠跌紅) 與特殊標記 (🔥🐳🟢)。
  點欄位標題即可排序（▼ 大到小 / ▲ 小到大，再點一次切換）。

  columns: [{ key, label, align?, format?, color?, mono?, sortable? }]
    - format(value, row) → 顯示字串
    - color(value, row)  → CSS color 字串 (回傳 falsy 則用預設色)
    - sortable: false 可關閉該欄排序 (預設可排序；陣列/迷你線欄會自動關閉)
  rows:    [{ ...任意欄位 }]
-->
<template>
  <div class="dt-wrap">
    <table class="dt">
      <thead>
        <tr>
          <th
            v-for="col in columns"
            :key="col.key"
            :style="{ textAlign: col.align || 'left' }"
            :class="{ sortable: isSortable(col) }"
            @click="toggleSort(col)"
          >
            {{ col.label }}<span v-if="isSortable(col)" class="arrow">{{ arrow(col.key) }}</span>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(row, i) in sortedRows"
          :key="rowKey ? row[rowKey] : i"
          :class="{ clickable: clickable }"
          @click="clickable && emit('row-click', row)"
        >
          <td
            v-for="col in columns"
            :key="col.key"
            :class="{ mono: col.mono !== false }"
            :style="cellStyle(col, row)"
          >
            <!-- 具名 slot cell-<key> 可注入自訂渲染 (如迷你線)，否則用預設格式化 -->
            <slot :name="`cell-${col.key}`" :row="row" :value="row[col.key]">
              {{ renderCell(col, row) }}
            </slot>
          </td>
        </tr>
        <tr v-if="!sortedRows.length">
          <td :colspan="columns.length" class="dt-empty">無資料</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  columns: { type: Array, required: true },
  rows: { type: Array, default: () => [] },
  rowKey: { type: String, default: '' },
  clickable: { type: Boolean, default: false },
})
const emit = defineEmits(['row-click'])

const sortKey = ref(null)
const sortDir = ref('desc') // 'desc' = 大到小, 'asc' = 小到大

function isSortable(col) {
  if (col.sortable === false) return false
  // 抽樣第一筆判斷：陣列/物件型欄位（如迷你線 trend）不排序
  const sample = props.rows.find((r) => r[col.key] !== null && r[col.key] !== undefined)
  if (sample && typeof sample[col.key] === 'object') return false
  return true
}

function arrow(key) {
  if (sortKey.value !== key) return ' ⇅'
  return sortDir.value === 'desc' ? ' ▼' : ' ▲'
}

function toggleSort(col) {
  if (!isSortable(col)) return
  if (sortKey.value === col.key) {
    sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortKey.value = col.key
    sortDir.value = 'desc' // 新欄位預設大到小
  }
}

function compare(a, b) {
  // null / undefined 一律排到最後
  const an = a === null || a === undefined || a === ''
  const bn = b === null || b === undefined || b === ''
  if (an && bn) return 0
  if (an) return 1
  if (bn) return -1

  const na = Number(a)
  const nb = Number(b)
  const bothNum = !Number.isNaN(na) && !Number.isNaN(nb) && typeof a !== 'boolean' && typeof b !== 'boolean'
  let res
  if (bothNum) res = na - nb
  else res = String(a).localeCompare(String(b), 'zh-Hant')
  return res
}

const sortedRows = computed(() => {
  if (!sortKey.value) return props.rows
  const key = sortKey.value
  const dir = sortDir.value === 'desc' ? -1 : 1
  // null 永遠墊底（不受方向影響）：先比 null，再比值
  return [...props.rows].sort((ra, rb) => {
    const a = ra[key]
    const b = rb[key]
    const an = a === null || a === undefined || a === ''
    const bn = b === null || b === undefined || b === ''
    if (an || bn) return compare(a, b) // compare 已把 null 排到最後
    return compare(a, b) * dir
  })
})

function renderCell(col, row) {
  const v = row[col.key]
  if (typeof col.format === 'function') return col.format(v, row)
  return v ?? '—'
}

function cellStyle(col, row) {
  const style = { textAlign: col.align || 'left' }
  if (typeof col.color === 'function') {
    const c = col.color(row[col.key], row)
    if (c) style.color = c
  }
  return style
}
</script>

<style scoped>
.dt-wrap {
  width: 100%;
  overflow-x: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-surface);
}
.dt {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.dt thead th {
  position: sticky;
  top: 0;
  background: var(--color-bg-raised);
  color: var(--color-text-secondary);
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  font-weight: 600;
  padding: 10px 14px;
  border-bottom: 1px solid var(--color-border);
  white-space: nowrap;
  user-select: none;
}
.dt thead th.sortable { cursor: pointer; }
.dt thead th.sortable:hover { color: var(--color-text-primary); }
.dt thead th .arrow { color: var(--color-text-muted); font-size: 10px; }
.dt tbody td {
  padding: 9px 14px;
  border-bottom: 1px solid var(--color-border-dim);
  color: var(--color-text-primary);
  white-space: nowrap;
}
.dt tbody tr:hover td {
  background: var(--color-bg-raised);
}
.dt tbody tr.clickable { cursor: pointer; }
.dt tbody tr.clickable:hover td { background: rgba(59, 130, 246, 0.12); }
.dt-empty {
  text-align: center;
  color: var(--color-text-muted);
  padding: 24px;
}
</style>
