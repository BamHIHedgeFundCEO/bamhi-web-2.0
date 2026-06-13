<!--
  HomeView.vue — 首頁 (對應 Streamlit render_hero_section + render_sector_signals_panel)
  Hero 封面 + 板塊即時訊號推播面板 (點卡片 → 板塊輪動該板塊)
-->
<template>
  <div class="home">
    <!-- Hero -->
    <section class="hero">
      <div class="hero-left">
        <div class="tag">▲ BAMHI QUANT 趨勢追蹤器</div>
        <h1 class="hero-title">更早看懂市場，<br />少走研究彎路</h1>
        <p class="hero-sub">
          BamHI Quant 把全市場掃描、板塊輪動、趨勢雷達、回測驗證、機構與內部人追蹤，
          整合出一套每天可以直接執行的研究工作流。
        </p>
        <div class="cta">
          <RouterLink to="/sector-rotation" class="btn-primary">🔄 板塊輪動掃描</RouterLink>
          <RouterLink to="/models" class="btn-ghost">🤖 今日 AI 戰報</RouterLink>
          <RouterLink to="/macro" class="btn-ghost">📊 總經市場</RouterLink>
        </div>
      </div>
      <div class="hero-right">
        <div class="bento">
          <div class="tag">會員專區亮點</div>
          <h3>會員專區 + AI 工作流，讓你更早看到研究過程</h3>
          <p class="bento-sub">不只看整理後結論，而是更早看到題材追蹤、資料整理、部位記錄與持續追蹤。</p>
          <div class="bento-item"><b>第一手研究紀錄</b><br /><span>交易想法、部位變化與事件追蹤，持續更新。</span></div>
          <div class="bento-item"><b>AI 工作流拆解</b><br /><span>直接看到如何用 AI 協助研究、建立觀察名單。</span></div>
          <div class="bento-item"><b>從想法到執行一條龍</b><br /><span>先用工具找機會，再回專區持續跟進。</span></div>
        </div>
      </div>
    </section>

    <!-- 板塊訊號 -->
    <section class="signals">
      <div class="signals-head">
        <h2>⚡ 板塊即時訊號推播</h2>
        <p>基於板塊指數 MA 排列 + 擁擠度防護罩，快速瀏覽所有板塊進出場狀態</p>
      </div>

      <div v-if="store.signalsLoading" class="ph">正在快速掃描所有板塊訊號（首次需 bulk 下載，稍候）…</div>
      <div v-else-if="!store.signals" class="alert">⚠️ {{ store.error || '尚無訊號資料' }}</div>
      <div v-else class="grid">
        <div v-for="s in store.signals.signals" :key="s.sector" class="card" :class="s.color" @click="goSector(s.sector)">
          <div class="card-head">
            <span class="emoji">{{ s.emoji }}</span>
            <span class="sname">{{ s.sector }}</span>
            <span class="badge">{{ s.status }}</span>
          </div>
          <p class="detail">{{ s.detail }}</p>
          <p v-if="s.leaders.length" class="leaders">👑 龍頭：{{ s.leaders.join(' · ') }}</p>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { useSectorRotationStore } from '@/stores/sectorRotation'

const router = useRouter()
const store = useSectorRotationStore()

function goSector(sector) {
  router.push({ name: 'sectorRotation', query: { sector } })
}

onMounted(() => {
  if (!store.signals) store.fetchSignals('2y')
})
</script>

<style scoped>
.home { padding: 32px 28px; max-width: 1320px; margin: 0 auto; }
.hero { display: grid; grid-template-columns: 1.2fr 1fr; gap: 36px; margin-bottom: 44px; }
.tag { color: var(--color-accent); font-size: 12px; letter-spacing: 0.1em; font-weight: 600; margin-bottom: 14px; }
.hero-title { font-size: 40px; line-height: 1.15; margin: 0 0 18px; font-weight: 700; }
.hero-sub { color: var(--color-text-secondary); font-size: 15px; line-height: 1.7; margin: 0 0 26px; }
.cta { display: flex; gap: 12px; flex-wrap: wrap; }
.btn-primary, .btn-ghost {
  padding: 11px 18px; border-radius: var(--radius-md); font-size: 14px; font-weight: 600; cursor: pointer;
  border: 1px solid var(--color-border);
}
.btn-primary { background: var(--color-accent); color: #fff; border-color: var(--color-accent); }
.btn-primary:hover { background: var(--color-accent-dim); }
.btn-ghost { background: var(--color-bg-surface); color: var(--color-text-secondary); }
.btn-ghost:hover { color: var(--color-text-primary); border-color: var(--color-accent); }
.bento { background: var(--color-bg-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: 24px; }
.bento h3 { color: #fff; font-size: 17px; margin: 8px 0 10px; }
.bento-sub { color: var(--color-text-secondary); font-size: 13px; line-height: 1.5; margin: 0 0 18px; }
.bento-item { background: var(--color-bg-raised); padding: 13px 15px; border-radius: var(--radius-md); margin-bottom: 9px; font-size: 13px; }
.bento-item b { color: #fff; }
.bento-item span { color: var(--color-text-secondary); font-size: 12px; }

.signals-head h2 { font-size: 18px; margin: 0 0 4px; }
.signals-head p { color: var(--color-text-muted); font-size: 13px; margin: 0 0 18px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 14px; }
.card {
  background: var(--color-bg-surface); border: 1px solid var(--color-border); border-left-width: 3px;
  border-radius: var(--radius-md); padding: 14px 16px; cursor: pointer; transition: transform 0.1s;
}
.card:hover { transform: translateY(-2px); border-color: var(--color-accent); }
.card.green { border-left-color: #16a34a; }
.card.blue { border-left-color: #3b82f6; }
.card.yellow { border-left-color: #ca8a04; }
.card.orange { border-left-color: #ea580c; }
.card.red { border-left-color: #dc2626; }
.card.gray { border-left-color: #4b5563; }
.card-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.emoji { font-size: 16px; }
.sname { font-weight: 600; font-size: 14px; flex: 1; }
.badge { font-size: 11px; color: var(--color-text-secondary); background: var(--color-bg-raised); padding: 2px 8px; border-radius: 10px; }
.detail { color: var(--color-text-secondary); font-size: 12px; line-height: 1.5; margin: 0; }
.leaders { color: var(--color-data-gold); font-size: 11px; margin: 6px 0 0; }
.ph { color: var(--color-text-muted); padding: 30px 0; }
.alert { background: rgba(245, 158, 11, 0.1); border: 1px solid var(--color-warning); color: var(--color-warning); padding: 14px 18px; border-radius: var(--radius-md); }

@media (max-width: 900px) { .hero { grid-template-columns: 1fr; } }
</style>
