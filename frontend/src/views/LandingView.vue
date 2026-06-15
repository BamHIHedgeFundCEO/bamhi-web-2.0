<!--
  LandingView.vue — 公開行銷首頁（方向 C · 矽谷科技 SaaS / 玻璃擬態）
  像素級重建自設計交接稿 bamhi/design_handoff_bamhi_landing/landingC.jsx。
  圖表為種子化 SVG（lib/landingCharts.js），純展示。CTA 接 /login（註冊/登入）。
  全部樣式 scoped 於 .lpc，不影響 App 內部儀表板。
-->
<template>
  <div class="lpc">
    <div class="mesh">
      <div class="blob b1"></div>
      <div class="blob b2"></div>
      <div class="blob b3"></div>
      <div class="grid-ov"></div>
    </div>

    <!-- nav -->
    <div class="wrap">
      <div class="nav">
        <div class="navin">
          <div class="logo" @click="scrollTop"><span class="mk"></span>BamHI Quant</div>
          <div class="nlinks">
            <span class="nlink" @click="scrollTo('features')">總經市場</span>
            <span class="nlink" @click="scrollTo('features')">交易工具</span>
            <span class="nlink" @click="scrollTo('features')">交易模型</span>
            <span class="nlink" @click="scrollTo('pricing')">會員方案</span>
          </div>
          <div class="nright">
            <button class="btn btn-link" @click="goLogin">登入</button>
            <button class="btn btn-grad" @click="goSignup">免費開始</button>
          </div>
        </div>
      </div>
    </div>

    <!-- hero -->
    <div class="wrap">
      <div class="hero">
        <div>
          <div class="pill"><span class="tagx">LIVE</span>板塊輪動引擎 · 即時訊號運轉中</div>
          <h1 class="dis">看懂市場輪動，<br /><span class="grad-t">從今天開始</span></h1>
          <p class="lead">
            把避險基金等級的板塊輪動、即時訊號與量化研究，整合成一個現代、流暢、看得懂的儀表板——讓散戶也能用機構的方式做研究。
          </p>
          <div class="cta">
            <button class="btn btn-grad" @click="goSignup">免費開始掃描 →</button>
            <button class="btn btn-ghost" @click="goLogin">▶ 看今日 AI 戰報</button>
          </div>
          <div class="trust">
            <span class="av"><span></span><span></span><span></span></span>已有 12,000+ 投資人每天使用
          </div>
        </div>
        <div class="hv">
          <div class="glass main">
            <div class="ph"><span class="t dis">即時訊號推播</span><span class="live"><i></i>LIVE</span></div>
            <div v-for="r in heroSignals" :key="r.name" class="srow">
              <span class="nm">{{ r.name }}</span>
              <span class="bd" :class="r.dir">{{ r.label }}</span>
              <span class="pc" :style="{ color: r.dir === 'dn' ? '#fb8ca0' : '#5fe0ad' }">{{ r.pct }}</span>
            </div>
          </div>
          <div class="glass float">
            <div class="ph"><span class="t dis" style="font-size: 12px">相對輪動 RRG</span></div>
            <span v-html="rrg({ w: 228, h: 150, quad: QUAD, grid: 'rgba(255,255,255,0.08)', text: 'rgba(255,255,255,0.4)' })"></span>
          </div>
        </div>
      </div>
    </div>

    <!-- bento features -->
    <div class="wrap">
      <div id="features" class="sec">
        <div class="shead">
          <div class="eyebrow">功能總覽</div>
          <h2 class="dis">一個平台，整套研究工作流</h2>
          <p>從宏觀到個股，從訊號到執行——你需要的全在這裡。</p>
        </div>
        <div class="bento">
          <div v-for="f in FEATURES" :key="f.t" class="bcard" :class="{ s2: f.span === 2 }">
            <span class="cicon" :style="{ background: gradOf(f.g) }"><span class="cicon-d"></span></span>
            <h3 class="dis">{{ f.t }}</h3>
            <p>{{ f.d }}</p>
            <div class="bchart" v-html="miniChart(f)"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- showcase -->
    <div class="wrap">
      <div class="sec">
        <div class="shead">
          <div class="eyebrow">產品預覽</div>
          <h2 class="dis">板塊輪動工作台</h2>
          <p>RRG、K 線、熱力圖與機構資金流，全部在同一個畫面。</p>
        </div>
        <div class="frame">
          <div class="fbar">
            <span class="dots"><i></i><i></i><i></i></span>
            <span class="url">app.bamhi.quant / sector-rotation</span>
          </div>
          <div class="fbody">
            <div>
              <div class="ct"><span>SOXX · 半導體 ETF</span><span style="color: #5fe0ad">+4.21% ▲</span></div>
              <span v-html="candles({ seed: 4, w: 560, h: 240, up: '#34d399', down: '#fb7185', ma: '#3fd0e6', grid: 'rgba(255,255,255,0.05)' })"></span>
              <div class="ct" style="margin-top: 20px; margin-bottom: 12px">
                <span>機構資金流 · 5 日</span><span style="color: var(--c-mute)">淨流入 $1.2B</span>
              </div>
              <span v-html="flowBars({ seed: 6, w: 560, h: 62, up: '#34d399', down: '#fb7185' })"></span>
            </div>
            <div>
              <div class="ct"><span>相對輪動 RRG</span></div>
              <span v-html="rrg({ w: 300, h: 240, quad: QUAD, grid: 'rgba(255,255,255,0.07)', text: 'rgba(255,255,255,0.45)' })"></span>
              <div class="ct" style="margin-top: 20px; margin-bottom: 12px"><span>板塊動能熱力圖</span></div>
              <span v-html="heatmap({ seed: 31, rows: 5, cols: 11, cell: 24, gap: 4, up: '#1f9d76', down: '#cf5d6e' })"></span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- pricing -->
    <div class="wrap">
      <div id="pricing" class="sec">
        <div class="shead">
          <div class="eyebrow">會員方案</div>
          <h2 class="dis">選一個適合你的節奏</h2>
          <p>免費開始，隨時升級，隨時取消。</p>
        </div>
        <div class="pgrid">
          <div v-for="p in PLANS" :key="p.name" class="pcard" :class="{ hot: p.hot }">
            <div class="ptag">
              <span class="pname" :class="{ dis: p.hot }">{{ p.name }}</span>
              <span v-if="p.hot" class="phot">最受歡迎</span>
            </div>
            <div class="price dis" :class="{ 'grad-t': p.hot }">
              {{ p.price }}<small v-if="p.unit" :style="p.hot ? { WebkitTextFillColor: 'var(--c-dim)' } : {}"> {{ p.unit }}</small>
            </div>
            <div class="pnote">{{ p.note }}</div>
            <ul class="pfeat">
              <li v-for="t in p.feats" :key="t"><span class="check" v-html="CHECK_SVG"></span>{{ t }}</li>
            </ul>
            <button class="btn" :class="p.hot ? 'btn-grad' : 'btn-ghost'" @click="goSignup">{{ p.cta }}</button>
          </div>
        </div>
      </div>
    </div>

    <!-- cta -->
    <div class="wrap">
      <div class="ctab">
        <h2 class="dis">明天的盤，今晚就準備好</h2>
        <p>免費開通，立即看見今天的板塊輪動與即時訊號。</p>
        <div class="cta">
          <button class="btn btn-grad" style="padding: 14px 30px; font-size: 16px" @click="goSignup">免費開始 →</button>
          <button class="btn btn-ghost" style="padding: 14px 30px; font-size: 16px" @click="goLogin">登入</button>
        </div>
      </div>
    </div>

    <!-- footer -->
    <div class="wrap">
      <div class="foot">
        <div class="brand">
          <div class="logo"><span class="mk"></span>BamHI Quant</div>
          <p>本平台資訊僅供研究參考，不構成投資建議。投資有風險，請審慎評估。© 2026 BamHI Quant.</p>
        </div>
        <div class="fcol"><h4>產品</h4><a>板塊輪動</a><a>即時訊號</a><a>暗池監控</a><a>AI 戰報</a></div>
        <div class="fcol"><h4>資源</h4><a>功能教學</a><a>API 文件</a><a>市場詞典</a></div>
        <div class="fcol"><h4>公司</h4><a>關於我們</a><a>聯絡</a><a>條款</a></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { rrg, candles, flowBars, heatmap, spark, areaSpark, barMini, gauge } from '@/lib/landingCharts'

const router = useRouter()
const QUAD = ['#34d399', '#3fd0e6', '#fb7185', '#a98bff']

function goLogin() {
  router.push({ name: 'login' })
}
function goSignup() {
  router.push({ name: 'login', query: { mode: 'signup' } })
}
function scrollTo(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
function scrollTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

const heroSignals = [
  { name: '半導體', dir: 'up', label: '強勢突破', pct: '+4.2%' },
  { name: '金融', dir: 'up', label: '多頭排列', pct: '+1.8%' },
  { name: '醫療', dir: 'dn', label: '區間整理', pct: '-0.3%' },
  { name: '公用事業', dir: 'dn', label: '弱勢', pct: '-1.4%' },
]

const GRADS = {
  cy: 'var(--c-gcy)',
  vi: 'var(--c-gvi)',
  mint: 'var(--c-gmint)',
}
const COLS = { cy: '#3fd0e6', vi: '#a98bff', mint: '#34d399' }
function gradOf(g) {
  return GRADS[g]
}

const FEATURES = [
  { t: '板塊輪動 + VCP', d: 'RRG 四象限即時定位，輪動軌跡與 VCP 型態掃描一次到位。', span: 2, g: 'cy', chart: 'rrg' },
  { t: '即時訊號推播', d: 'MA 排列 + 擁擠度防護罩，全板塊進出場狀態秒級更新。', span: 1, g: 'mint', chart: 'spark' },
  { t: '暗池異常資金', d: '追蹤 Top 50 暗池成交異常，看穿機構默默布局。', span: 1, g: 'vi', chart: 'bars' },
  { t: '總經市場', d: '殖利率、利差、寬度、情緒，六大總經指標一頁掌握。', span: 1, g: 'cy', chart: 'area' },
  { t: '板塊強弱', d: '美股與全球 RS 線、動能熱力圖，鎖定領先市場。', span: 1, g: 'mint', chart: 'heat' },
  { t: 'AI 交易模型', d: 'Alpha / Genesis 雙引擎每日戰報與量化分數。', span: 1, g: 'vi', chart: 'gauge' },
]

function miniChart(f) {
  const col = COLS[f.g]
  switch (f.chart) {
    case 'rrg':
      return rrg({ w: 300, h: 170, quad: QUAD, grid: 'rgba(255,255,255,0.07)', text: 'rgba(255,255,255,0.45)' })
    case 'spark':
      return spark({ seed: 5, n: 36, w: 210, h: 56, stroke: col, sw: 2 })
    case 'bars':
      return barMini({ seed: 8, n: 16, w: 210, h: 56, color: col })
    case 'area':
      return areaSpark({ seed: 3, w: 210, h: 56, stroke: col, fill: col })
    case 'heat':
      return heatmap({ seed: 14, rows: 4, cols: 9, cell: 20, gap: 3, up: '#1f9d76', down: '#cf5d6e' })
    case 'gauge':
      return gauge({ value: 82, size: 62, color: col, track: 'rgba(255,255,255,0.1)', text: '#fff', label: 'Alpha' })
    default:
      return ''
  }
}

const PLANS = [
  {
    name: '體驗',
    price: 'NT$0',
    note: '永久免費',
    feats: ['每日板塊訊號（延遲）', '總經市場總覽', '個股基礎查詢', '社群討論區'],
    cta: '免費開始',
  },
  {
    name: '進階',
    price: 'NT$790',
    unit: '/月',
    note: '年付 8 折',
    hot: true,
    feats: ['即時訊號推播', '板塊輪動 + VCP 掃描', '暗池異常資金監控', '個股深度量化分數', '美股板塊強弱'],
    cta: '開通 Pro',
  },
  {
    name: '旗艦',
    price: 'NT$1,990',
    unit: '/月',
    note: '專業交易者',
    feats: ['Pro 全部功能', 'AI 雙引擎每日戰報', '全球市場板塊強弱', '資料 API 存取', '優先客服支援'],
    cta: '聯絡我們',
  },
]

const CHECK_SVG = `<svg width="15" height="15" viewBox="0 0 15 15" fill="none"><circle cx="7.5" cy="7.5" r="7.5" fill="oklch(.78 .13 214)" fill-opacity="0.18"/><path d="M4.5 7.6l2 2 4-4.2" stroke="oklch(.82 .12 200)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`
</script>

<style scoped>
.lpc {
  --c-bg: #0a0c12;
  --c-bg2: #0c0f17;
  --c-glass: rgba(255, 255, 255, 0.04);
  --c-glass2: rgba(255, 255, 255, 0.06);
  --c-line: rgba(255, 255, 255, 0.09);
  --c-line2: rgba(255, 255, 255, 0.06);
  --c-text: #eef1f7;
  --c-dim: #9aa3b4;
  --c-mute: #626b7c;
  --c-cy: oklch(0.78 0.13 214);
  --c-vi: oklch(0.68 0.17 292);
  --c-mint: oklch(0.78 0.15 165);
  --c-gcy: linear-gradient(135deg, oklch(0.82 0.12 200), oklch(0.66 0.16 250));
  --c-gvi: linear-gradient(135deg, oklch(0.74 0.15 300), oklch(0.6 0.19 280));
  --c-gmint: linear-gradient(135deg, oklch(0.84 0.14 160), oklch(0.7 0.15 195));
  background: var(--c-bg);
  color: var(--c-text);
  font-family: 'Noto Sans TC', sans-serif;
  font-size: 15px;
  line-height: 1.65;
  position: relative;
  overflow: hidden;
  min-height: 100vh;
}
.lpc * {
  box-sizing: border-box;
}
.lpc .dis {
  font-family: 'Space Grotesk', 'Noto Sans TC', sans-serif;
}
.lpc .mono {
  font-family: 'JetBrains Mono', monospace;
  font-variant-numeric: tabular-nums;
}
.lpc .wrap {
  max-width: 1140px;
  margin: 0 auto;
  padding: 0 40px;
  position: relative;
  z-index: 1;
}
.lpc .grad-t {
  background: var(--c-gcy);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
/* ambient bg */
.lpc .mesh {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
}
.lpc .blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
  opacity: 0.5;
}
.lpc .b1 {
  width: 560px;
  height: 560px;
  background: oklch(0.6 0.18 250);
  top: -180px;
  right: -120px;
  opacity: 0.28;
}
.lpc .b2 {
  width: 480px;
  height: 480px;
  background: oklch(0.62 0.19 300);
  top: 420px;
  left: -180px;
  opacity: 0.22;
}
.lpc .b3 {
  width: 520px;
  height: 520px;
  background: oklch(0.7 0.15 180);
  top: 1600px;
  right: -160px;
  opacity: 0.16;
}
.lpc .grid-ov {
  position: absolute;
  inset: 0;
  background-image: linear-gradient(rgba(255, 255, 255, 0.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.025) 1px, transparent 1px);
  background-size: 54px 54px;
  -webkit-mask-image: radial-gradient(120% 60% at 50% 0, #000, transparent 75%);
  mask-image: radial-gradient(120% 60% at 50% 0, #000, transparent 75%);
}
/* nav */
.lpc .nav {
  position: sticky;
  top: 0;
  z-index: 30;
  padding: 16px 0;
}
.lpc .navin {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 10px 14px 10px 18px;
  border: 1px solid var(--c-line);
  background: rgba(12, 15, 23, 0.6);
  backdrop-filter: blur(16px);
  border-radius: 16px;
}
.lpc .logo {
  display: flex;
  align-items: center;
  gap: 11px;
  font-family: 'Space Grotesk', sans-serif;
  font-weight: 700;
  font-size: 18px;
  letter-spacing: -0.01em;
  white-space: nowrap;
  cursor: pointer;
}
.lpc .logo .mk {
  width: 26px;
  height: 26px;
  border-radius: 8px;
  background: var(--c-gcy);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 14px rgba(80, 180, 230, 0.35);
}
.lpc .logo .mk::after {
  content: '';
  width: 10px;
  height: 10px;
  border-radius: 3px;
  background: #0a0c12;
  transform: rotate(45deg);
}
.lpc .nlinks {
  display: flex;
  gap: 6px;
}
.lpc .nlink {
  color: var(--c-dim);
  font-size: 14px;
  padding: 8px 13px;
  border-radius: 9px;
  cursor: pointer;
  transition: 0.15s;
}
.lpc .nlink:hover {
  color: var(--c-text);
  background: var(--c-glass);
}
.lpc .nright {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 10px;
}
.lpc .btn {
  font-family: 'Space Grotesk', 'Noto Sans TC', sans-serif;
  font-size: 14px;
  font-weight: 600;
  padding: 10px 18px;
  border-radius: 10px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: 0.18s;
  white-space: nowrap;
}
.lpc .btn-ghost {
  background: transparent;
  color: var(--c-dim);
  border-color: var(--c-line);
}
.lpc .btn-ghost:hover {
  color: var(--c-text);
  border-color: rgba(255, 255, 255, 0.2);
}
.lpc .btn-grad {
  background: var(--c-gcy);
  color: #06121a;
  box-shadow: 0 6px 20px rgba(80, 180, 230, 0.3);
}
.lpc .btn-grad:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 28px rgba(80, 180, 230, 0.42);
}
.lpc .btn-link {
  background: transparent;
  color: var(--c-dim);
}
.lpc .btn-link:hover {
  color: var(--c-text);
}
/* hero */
.lpc .hero {
  padding: 70px 0 56px;
  display: grid;
  grid-template-columns: 1.05fr 0.95fr;
  gap: 44px;
  align-items: center;
}
.lpc .pill {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  padding: 6px 14px 6px 8px;
  border: 1px solid var(--c-line);
  background: var(--c-glass);
  border-radius: 30px;
  font-size: 12.5px;
  color: var(--c-dim);
  margin-bottom: 26px;
}
.lpc .pill .tagx {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  padding: 3px 8px;
  border-radius: 20px;
  background: var(--c-gmint);
  color: #04130d;
}
.lpc h1 {
  font-family: 'Space Grotesk', 'Noto Sans TC', sans-serif;
  font-size: 56px;
  line-height: 1.08;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0 0 22px;
}
.lpc .lead {
  color: var(--c-dim);
  font-size: 17px;
  line-height: 1.75;
  max-width: 480px;
  margin: 0 0 32px;
}
.lpc .cta {
  display: flex;
  gap: 13px;
  flex-wrap: wrap;
  margin-bottom: 30px;
}
.lpc .cta .btn {
  padding: 13px 24px;
  font-size: 15px;
}
.lpc .trust {
  display: flex;
  align-items: center;
  gap: 18px;
  color: var(--c-mute);
  font-size: 13px;
}
.lpc .trust .av {
  display: flex;
}
.lpc .trust .av span {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 2px solid var(--c-bg);
  margin-left: -8px;
  background: var(--c-glass2);
}
.lpc .trust .av span:nth-child(1) {
  background: var(--c-gcy);
}
.lpc .trust .av span:nth-child(2) {
  background: var(--c-gvi);
}
.lpc .trust .av span:nth-child(3) {
  background: var(--c-gmint);
}
/* hero visual */
.lpc .hv {
  position: relative;
  height: 440px;
}
.lpc .glass {
  background: linear-gradient(160deg, var(--c-glass2), var(--c-glass));
  border: 1px solid var(--c-line);
  backdrop-filter: blur(14px);
  border-radius: 18px;
  box-shadow: 0 30px 70px rgba(0, 0, 0, 0.5);
}
.lpc .hv .main {
  position: absolute;
  top: 0;
  right: 0;
  width: 400px;
  padding: 20px;
  animation: c-float 7s ease-in-out infinite;
}
.lpc .hv .float {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 260px;
  padding: 16px;
  animation: c-float 6s ease-in-out infinite reverse;
}
@keyframes c-float {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-12px);
  }
}
@media (prefers-reduced-motion: reduce) {
  .lpc .hv .main,
  .lpc .hv .float {
    animation: none;
  }
}
.lpc .ph {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.lpc .ph .t {
  font-family: 'Space Grotesk', sans-serif;
  font-weight: 600;
  font-size: 14px;
}
.lpc .live {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--c-mint);
}
.lpc .live i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--c-mint);
  box-shadow: 0 0 8px var(--c-mint);
}
.lpc .srow {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 0;
  border-top: 1px solid var(--c-line2);
}
.lpc .srow .nm {
  font-size: 13px;
  flex: 1;
}
.lpc .srow .bd {
  font-size: 10.5px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 20px;
}
.lpc .bd.up {
  background: rgba(52, 211, 153, 0.16);
  color: #5fe0ad;
}
.lpc .bd.dn {
  background: rgba(251, 113, 133, 0.16);
  color: #fb8ca0;
}
.lpc .srow .pc {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12.5px;
}
/* sections */
.lpc .sec {
  padding: 64px 0;
}
.lpc .shead {
  text-align: center;
  max-width: 640px;
  margin: 0 auto 46px;
}
.lpc .eyebrow {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--c-cy);
  margin-bottom: 14px;
}
.lpc .shead h2 {
  font-family: 'Space Grotesk', 'Noto Sans TC', sans-serif;
  font-size: 38px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0 0 14px;
}
.lpc .shead p {
  color: var(--c-dim);
  font-size: 16px;
  margin: 0;
}
/* bento */
.lpc .bento {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.lpc .bcard {
  padding: 24px;
  border-radius: 18px;
  border: 1px solid var(--c-line);
  background: linear-gradient(160deg, var(--c-glass2), transparent);
  transition: 0.22s;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.lpc .bcard:hover {
  transform: translateY(-3px);
  border-color: rgba(255, 255, 255, 0.18);
  background: linear-gradient(160deg, var(--c-glass2), var(--c-glass));
}
.lpc .bcard.s2 {
  grid-column: span 2;
}
.lpc .cicon {
  width: 38px;
  height: 38px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}
.lpc .cicon-d {
  width: 15px;
  height: 15px;
  border-radius: 4px;
  background: rgba(6, 18, 26, 0.85);
  transform: rotate(45deg);
}
.lpc .bcard h3 {
  font-family: 'Space Grotesk', 'Noto Sans TC', sans-serif;
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 8px;
}
.lpc .bcard p {
  color: var(--c-dim);
  font-size: 13.5px;
  line-height: 1.6;
  margin: 0 0 16px;
}
.lpc .bchart {
  margin-top: auto;
}
/* showcase frame */
.lpc .frame {
  border-radius: 18px;
  border: 1px solid var(--c-line);
  background: rgba(12, 15, 23, 0.7);
  backdrop-filter: blur(14px);
  overflow: hidden;
  box-shadow: 0 40px 90px rgba(0, 0, 0, 0.55);
}
.lpc .fbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 13px 18px;
  border-bottom: 1px solid var(--c-line);
}
.lpc .fbar .dots {
  display: flex;
  gap: 6px;
}
.lpc .fbar .dots i {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  background: var(--c-line);
}
.lpc .fbar .url {
  margin: 0 auto;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: var(--c-mute);
  background: var(--c-glass);
  padding: 5px 16px;
  border-radius: 8px;
}
.lpc .fbody {
  display: grid;
  grid-template-columns: 1.5fr 1fr;
}
.lpc .fbody > div {
  padding: 24px;
}
.lpc .fbody > div:first-child {
  border-right: 1px solid var(--c-line);
}
.lpc .ct {
  display: flex;
  justify-content: space-between;
  font-family: 'Space Grotesk', sans-serif;
  font-size: 13px;
  color: var(--c-dim);
  margin-bottom: 16px;
}
/* pricing */
.lpc .pgrid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 18px;
  align-items: stretch;
}
.lpc .pcard {
  padding: 32px 28px;
  border-radius: 18px;
  border: 1px solid var(--c-line);
  background: linear-gradient(160deg, var(--c-glass2), transparent);
  display: flex;
  flex-direction: column;
}
.lpc .pcard.hot {
  border-color: transparent;
  background: linear-gradient(160deg, rgba(120, 180, 255, 0.14), rgba(160, 130, 255, 0.06));
  box-shadow: 0 0 0 1px oklch(0.7 0.14 250), 0 24px 60px rgba(90, 140, 255, 0.18);
}
.lpc .ptag {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.lpc .pname {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 15px;
  font-weight: 600;
  color: var(--c-dim);
  letter-spacing: 0.02em;
}
.lpc .pcard.hot .pname {
  color: var(--c-text);
}
.lpc .phot {
  font-size: 11px;
  font-weight: 700;
  padding: 4px 11px;
  border-radius: 20px;
  background: var(--c-gcy);
  color: #06121a;
}
.lpc .price {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 42px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 8px 0 2px;
}
.lpc .price small {
  font-size: 15px;
  color: var(--c-dim);
  font-weight: 500;
}
.lpc .pnote {
  color: var(--c-mute);
  font-size: 13px;
  margin-bottom: 22px;
}
.lpc .pfeat {
  list-style: none;
  padding: 0;
  margin: 0 0 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  font-size: 14px;
  color: var(--c-dim);
  flex: 1;
}
.lpc .pfeat li {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.lpc .pfeat li .check {
  flex-shrink: 0;
  margin-top: 3px;
  display: inline-flex;
}
.lpc .pcard .btn {
  width: 100%;
  text-align: center;
  padding: 12px;
}
/* cta */
.lpc .ctab {
  margin: 40px 0 64px;
  padding: 64px 40px;
  text-align: center;
  border-radius: 24px;
  border: 1px solid var(--c-line);
  background: linear-gradient(160deg, rgba(120, 180, 255, 0.12), rgba(160, 130, 255, 0.05));
  position: relative;
  overflow: hidden;
}
.lpc .ctab h2 {
  font-family: 'Space Grotesk', 'Noto Sans TC', sans-serif;
  font-size: 40px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0 0 16px;
}
.lpc .ctab p {
  color: var(--c-dim);
  font-size: 17px;
  margin: 0 0 30px;
}
.lpc .ctab .cta {
  justify-content: center;
}
/* footer */
.lpc .foot {
  padding: 44px 0 56px;
  border-top: 1px solid var(--c-line);
  display: flex;
  gap: 48px;
  align-items: flex-start;
}
.lpc .foot .brand .logo {
  margin-bottom: 14px;
}
.lpc .foot .brand p {
  color: var(--c-mute);
  font-size: 12.5px;
  max-width: 280px;
  line-height: 1.7;
  margin: 0;
}
.lpc .foot .fcol {
  margin-left: auto;
}
.lpc .foot .fcol + .fcol {
  margin-left: 56px;
}
.lpc .foot .fcol h4 {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 13px;
  color: var(--c-text);
  margin: 0 0 14px;
}
.lpc .foot .fcol a {
  display: block;
  color: var(--c-dim);
  font-size: 13px;
  margin-bottom: 9px;
  cursor: pointer;
}
.lpc .foot .fcol a:hover {
  color: var(--c-cy);
}
/* responsive */
@media (max-width: 900px) {
  .lpc .wrap {
    padding: 0 22px;
  }
  .lpc .hero {
    grid-template-columns: 1fr;
    gap: 28px;
    padding: 40px 0;
  }
  .lpc h1 {
    font-size: 40px;
  }
  .lpc .hv {
    height: 380px;
  }
  .lpc .bento {
    grid-template-columns: 1fr;
  }
  .lpc .bcard.s2 {
    grid-column: span 1;
  }
  .lpc .pgrid {
    grid-template-columns: 1fr;
  }
  .lpc .fbody {
    grid-template-columns: 1fr;
  }
  .lpc .fbody > div:first-child {
    border-right: none;
    border-bottom: 1px solid var(--c-line);
  }
  .lpc .nlinks {
    display: none;
  }
  .lpc .foot {
    flex-wrap: wrap;
    gap: 28px;
  }
  .lpc .foot .fcol,
  .lpc .foot .fcol + .fcol {
    margin-left: 0;
  }
}
</style>
