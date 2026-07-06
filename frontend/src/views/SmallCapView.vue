<!--
  SmallCapView.vue — 💰 小市值策略 (/app/small-cap)
  雙池選股 L3 計分卡結果呈現。

  左池 / 右池 tab，每 tab 兩區塊：
    ✅ 候選清單（gate_passed=true 且 veto 空）
    👀 池內觀察（其餘，分數排序）

  表格欄：ticker / total / 六因子 / veto 紅標 / gate 標記
  點 ticker 展開事件流（headline / event_type / specificity / direction / 日期 / source_url）
-->
<template>
  <div class="sc">
    <header class="sc-header">
      <div>
        <h1>💰 小市值策略 — 雙池選股計分卡</h1>
        <p class="sc-sub">
          L3 評分每日夜間批次更新。左池：底部拐頭催化劑驅動；右池：動能趨勢強勢股。
          <br />
          <span class="note">institution 因子（stage 5）未就緒，顯示「—」。</span>
        </p>
      </div>
      <div class="tab-bar">
        <button
          v-for="s in SIDES"
          :key="s.value"
          class="tab-btn"
          :class="{ active: store.currentSide === s.value }"
          @click="switchSide(s.value)"
        >
          {{ s.label }}
        </button>
      </div>
    </header>

    <!-- Loading -->
    <div v-if="store.scoresLoading" class="skeleton-wrap">
      <div v-for="n in 8" :key="n" class="skeleton-row" />
    </div>

    <!-- Error -->
    <div v-else-if="store.scoresError" class="alert-box">⚠️ {{ store.scoresError }}</div>

    <!-- Empty -->
    <div v-else-if="!store.scores.length" class="alert-box muted">
      目前無評分資料。請等待夜間批次更新（UTC 22:00）或手動執行 run_stage3。
    </div>

    <!-- 兩區塊 -->
    <template v-else>
      <!-- ✅ 候選清單 -->
      <section class="pool-section">
        <h2 class="section-title">✅ 候選清單 <span class="badge-count">{{ candidates.length }}</span></h2>
        <p class="section-desc">gate_passed = true 且無 veto，可行動名單。</p>
        <ScoreTable
          :rows="candidates"
          :expanded="expanded"
          @toggle="toggleExpand"
          @load-events="loadEvents"
          :events-map-fn="store.getEvents"
        />
        <p v-if="!candidates.length" class="empty-note">
          目前無 Gate 通過 + 無 veto 標的。左池 specificity≥4 在小型股稀有，此為設計行為。
        </p>
      </section>

      <!-- 👀 池內觀察 -->
      <section class="pool-section">
        <h2 class="section-title">👀 池內觀察 <span class="badge-count">{{ watchlist.length }}</span></h2>
        <p class="section-desc">等催化劑落地，依分數排序。</p>
        <ScoreTable
          :rows="watchlist"
          :expanded="expanded"
          @toggle="toggleExpand"
          @load-events="loadEvents"
          :events-map-fn="store.getEvents"
        />
      </section>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, defineComponent, h } from 'vue'
import { useDualPoolStore } from '@/stores/dualPool'

const store = useDualPoolStore()

const SIDES = [
  { value: 'left',  label: '⬅ 左池（初期底部）' },
  { value: 'right', label: '➡ 右池（右側動能）' },
]

const expanded = ref({})  // { ticker: boolean }

function switchSide(side) {
  store.clearEvents()
  expanded.value = {}
  store.fetchScores(side)
}

function toggleExpand(ticker) {
  expanded.value[ticker] = !expanded.value[ticker]
}

async function loadEvents(ticker) {
  await store.fetchEvents(ticker, 90)
}

const candidates = computed(() =>
  store.scores.filter(
    (r) => r.gate_passed && (!r.veto_flags || r.veto_flags.length === 0)
  )
)

const watchlist = computed(() =>
  store.scores.filter(
    (r) => !r.gate_passed || (r.veto_flags && r.veto_flags.length > 0)
  )
)

onMounted(() => store.fetchScores('left'))

// ── 子元件：ScoreTable ─────────────────────────────────────────────────────
const ScoreTable = defineComponent({
  name: 'ScoreTable',
  props: {
    rows: { type: Array, default: () => [] },
    expanded: { type: Object, default: () => ({}) },
    eventsMapFn: { type: Function, required: true },
  },
  emits: ['toggle', 'load-events'],
  setup(props, { emit }) {
    function fmtFactor(v) {
      if (v === null || v === undefined) return '—'
      return Number(v).toFixed(2)
    }
    function fmtTotal(v) {
      if (v === null || v === undefined) return '—'
      return Number(v).toFixed(1)
    }
    function fmtMktCap(v) {
      if (!v) return '—'
      if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`
      if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`
      return `$${v.toFixed(0)}`
    }
    function fmtAdv(v) {
      if (!v) return '—'
      if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`
      return `$${v.toFixed(0)}`
    }

    function handleToggle(ticker) {
      emit('toggle', ticker)
      emit('load-events', ticker)
    }

    return () => {
      if (!props.rows.length) return null

      return h('div', { class: 'tbl-wrap' }, [
        h('table', { class: 'tbl' }, [
          h('thead', {}, [
            h('tr', {}, [
              h('th', { class: 'left sticky-col' }, '代號'),
              h('th', {}, '總分'),
              h('th', {}, '催化劑'),
              h('th', {}, '營運槓桿'),
              h('th', {}, '夥伴'),
              h('th', {}, '內部人'),
              h('th', {}, '板塊'),
              h('th', { title: 'stage 5 未就緒' }, '機構'),
              h('th', {}, 'Gate'),
              h('th', {}, 'Veto'),
              h('th', {}, '市值'),
              h('th', {}, 'ADV'),
            ])
          ]),
          h('tbody', {}, props.rows.flatMap((row) => {
            const isExpanded = props.expanded[row.ticker]
            const evState = props.eventsMapFn(row.ticker, 90)

            const mainRow = h('tr', {
              key: row.ticker,
              class: [
                'data-row',
                row.veto_flags?.length ? 'veto-row' : '',
                isExpanded ? 'expanded' : '',
              ],
            }, [
              // ticker
              h('td', { class: 'sticky-col' }, [
                h('button', {
                  class: 'ticker-btn',
                  onClick: () => handleToggle(row.ticker),
                  title: '展開 / 收起事件流',
                }, [
                  h('span', { class: 'expand-arrow' }, isExpanded ? '▼' : '▶'),
                  ' ',
                  row.ticker,
                ])
              ]),
              h('td', { class: 'total-cell' }, fmtTotal(row.total)),
              h('td', { class: 'center' }, fmtFactor(row.catalyst)),
              h('td', { class: 'center' }, fmtFactor(row.op_leverage)),
              h('td', { class: 'center' }, fmtFactor(row.partnership)),
              h('td', { class: 'center' }, fmtFactor(row.insider)),
              h('td', { class: 'center' }, fmtFactor(row.narrative)),
              h('td', { class: 'center muted' }, '—'),
              // gate
              h('td', { class: 'center' }, row.gate_passed
                ? h('span', { class: 'badge gate-pass' }, '✅ Gate')
                : h('span', { class: 'badge gate-fail' }, '觀察')
              ),
              // veto
              h('td', { class: 'center' }, row.veto_flags?.length
                ? h('span', { class: 'badge veto', title: row.veto_flags.join(', ') },
                    '🔴 ' + row.veto_flags.join(','))
                : h('span', { class: 'text-muted' }, '—')
              ),
              h('td', { class: 'center mono' }, fmtMktCap(row.market_cap)),
              h('td', { class: 'center mono' }, fmtAdv(row.adv_dollar)),
            ])

            if (!isExpanded) return [mainRow]

            // 展開行：事件流
            const evRow = h('tr', { key: `${row.ticker}_ev`, class: 'event-row' }, [
              h('td', { colspan: 12, class: 'event-cell' }, [
                evState.loading
                  ? h('p', { class: 'ev-loading' }, '⏳ 載入事件流中…')
                  : evState.error
                    ? h('p', { class: 'ev-error' }, `⚠️ ${evState.error}`)
                    : !evState.items?.length
                      ? h('p', { class: 'ev-empty' }, '近 90 天無事件')
                      : h('table', { class: 'ev-tbl' }, [
                          h('thead', {}, [h('tr', {}, [
                            h('th', {}, '日期'),
                            h('th', {}, '類型'),
                            h('th', { title: '1-5' }, '明確度'),
                            h('th', {}, '方向'),
                            h('th', {}, '標題'),
                            h('th', {}, '來源'),
                          ])]),
                          h('tbody', {}, evState.items.map((ev) =>
                            h('tr', { key: ev.id ?? ev.event_date, class: `ev-${ev.direction}` }, [
                              h('td', { class: 'mono' }, (ev.event_date || ev.known_at || '').slice(0, 10)),
                              h('td', {}, ev.event_type || '—'),
                              h('td', { class: 'center' }, ev.specificity ?? '—'),
                              h('td', {}, directionBadge(ev.direction)),
                              h('td', { class: 'ev-headline' }, ev.headline || '—'),
                              h('td', {}, ev.source_url
                                ? h('a', { href: ev.source_url, target: '_blank', rel: 'noreferrer', class: 'ev-link' }, '連結')
                                : '—'
                              ),
                            ])
                          ))
                        ])
              ])
            ])

            return [mainRow, evRow]
          }))
        ])
      ])
    }

    function directionBadge(dir) {
      if (dir === 'bullish') return h('span', { class: 'badge dir-bull' }, '看多')
      if (dir === 'bearish') return h('span', { class: 'badge dir-bear' }, '看空')
      return h('span', { class: 'badge dir-neu' }, '中性')
    }
  }
})
</script>

<style scoped>
.sc { padding: 24px; max-width: 1400px; margin: 0 auto; }

.sc-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}
h1 { font-size: 20px; font-weight: 700; margin: 0 0 6px; }
.sc-sub { color: var(--color-text-secondary); font-size: 13px; margin: 0; line-height: 1.6; }
.note { color: var(--color-text-muted); font-size: 12px; }

.tab-bar { display: flex; gap: 8px; flex-shrink: 0; }
.tab-btn {
  padding: 8px 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  background: var(--color-bg-surface);
  color: var(--color-text-secondary);
  font-size: 14px;
  cursor: pointer;
}
.tab-btn.active {
  background: var(--color-accent);
  border-color: var(--color-accent);
  color: #fff;
  font-weight: 600;
}

.pool-section { margin-bottom: 36px; }
.section-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.badge-count {
  display: inline-block;
  background: var(--color-bg-raised);
  border: 1px solid var(--color-border);
  color: var(--color-text-muted);
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 12px;
}
.section-desc { color: var(--color-text-muted); font-size: 12px; margin: 0 0 12px; }
.empty-note { color: var(--color-text-muted); font-size: 13px; font-style: italic; padding: 12px 0; }

.skeleton-wrap { display: flex; flex-direction: column; gap: 10px; margin-top: 20px; }
.skeleton-row { height: 38px; background: var(--color-bg-raised); border-radius: var(--radius-md); animation: pulse 1.4s ease-in-out infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }

.alert-box {
  margin-top: 20px;
  padding: 16px;
  border: 1px solid var(--color-bear, #ef4444);
  border-radius: var(--radius-md);
  color: var(--color-bear, #ef4444);
  font-size: 14px;
}
.alert-box.muted { border-color: var(--color-border); color: var(--color-text-muted); }

/* 主表格 */
.tbl-wrap { overflow-x: auto; border: 1px solid var(--color-border); border-radius: var(--radius-md); }
.tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.tbl th {
  background: var(--color-bg-raised);
  color: var(--color-text-muted);
  font-weight: 600;
  padding: 10px 12px;
  text-align: center;
  border-bottom: 1px solid var(--color-border);
  white-space: nowrap;
}
.tbl th.left { text-align: left; }
.tbl td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--color-border);
  vertical-align: middle;
  color: var(--color-text-primary);
}
.tbl tr:last-child td { border-bottom: none; }
.tbl tr.data-row:hover td { background: var(--color-bg-surface); }
.tbl tr.veto-row > td { background: rgba(239, 68, 68, 0.06); }

.sticky-col { position: sticky; left: 0; background: var(--color-bg-base); z-index: 1; }
.tbl tr:hover .sticky-col { background: var(--color-bg-surface); }

.ticker-btn {
  background: none;
  border: none;
  color: var(--color-accent);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  padding: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}
.ticker-btn:hover { text-decoration: underline; }
.expand-arrow { font-size: 10px; color: var(--color-text-muted); }

.total-cell { font-weight: 700; text-align: center; font-size: 14px; }
.center { text-align: center; }
.mono { font-family: monospace; font-size: 12px; text-align: center; }
.muted { color: var(--color-text-muted); }
.text-muted { color: var(--color-text-muted); }

/* badge */
.badge {
  display: inline-block;
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 10px;
  white-space: nowrap;
}
.gate-pass { background: rgba(34,197,94,0.15); color: #22c55e; }
.gate-fail { background: var(--color-bg-raised); color: var(--color-text-muted); }
.veto { background: rgba(239,68,68,0.15); color: #ef4444; max-width: 160px; overflow: hidden; text-overflow: ellipsis; }
.dir-bull { background: rgba(34,197,94,0.12); color: #22c55e; }
.dir-bear { background: rgba(239,68,68,0.12); color: #ef4444; }
.dir-neu  { background: var(--color-bg-raised); color: var(--color-text-muted); }

/* 事件展開行 */
.event-row td { padding: 0 !important; background: var(--color-bg-surface) !important; }
.event-cell { padding: 16px 20px !important; }
.ev-loading, .ev-error, .ev-empty { color: var(--color-text-muted); font-size: 13px; margin: 0; }
.ev-error { color: var(--color-bear, #ef4444); }

.ev-tbl { width: 100%; border-collapse: collapse; font-size: 12px; }
.ev-tbl th {
  background: var(--color-bg-raised);
  color: var(--color-text-muted);
  font-size: 11px;
  padding: 6px 10px;
  text-align: left;
  border-bottom: 1px solid var(--color-border);
  white-space: nowrap;
}
.ev-tbl td { padding: 7px 10px; border-bottom: 1px solid var(--color-border); vertical-align: top; }
.ev-tbl tr:last-child td { border-bottom: none; }
.ev-tbl tr.ev-bullish td { background: rgba(34,197,94,0.04); }
.ev-tbl tr.ev-bearish td { background: rgba(239,68,68,0.04); }

.ev-headline { max-width: 320px; }
.ev-link { color: var(--color-accent); font-size: 11px; }
.ev-link:hover { text-decoration: underline; }
</style>
