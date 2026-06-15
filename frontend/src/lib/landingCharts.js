/* landingCharts.js — 行銷首頁用的種子化 SVG 圖表（純展示，非真實資料）。
   移植自設計交接稿 charts.jsx，回傳 SVG 字串供 LandingView 以 v-html 內嵌。
   全部 deterministic（mulberry32 種子），外觀像真實行情。 */

function mulberry32(a) {
  return function () {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

// 折線 sparkline
export function spark({ seed = 3, n = 32, stroke = '#5fcf80', w = 120, h = 34, sw = 1.6 }) {
  const r = mulberry32(seed)
  const pts = []
  let v = 0.5
  for (let i = 0; i < n; i++) {
    v += (r() - 0.46) * 0.16
    v = Math.max(0.08, Math.min(0.92, v))
    pts.push(v)
  }
  const path = pts.map((p, i) => `${(i / (n - 1)) * w},${h - p * h}`).join(' ')
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" style="display:block;overflow:visible">
    <polyline points="${path}" fill="none" stroke="${stroke}" stroke-width="${sw}" stroke-linejoin="round" stroke-linecap="round"/>
  </svg>`
}

// 含漸層填色的面積 sparkline
export function areaSpark({ seed = 7, n = 60, stroke = '#38bdf8', fill = '#38bdf8', w = 300, h = 90, sw = 2 }) {
  const r = mulberry32(seed)
  const pts = []
  let v = 0.42
  for (let i = 0; i < n; i++) {
    v += (r() - 0.44) * 0.13
    v = Math.max(0.06, Math.min(0.94, v))
    pts.push(v)
  }
  const gid = 'ag' + seed + Math.round(w)
  const line = pts.map((p, i) => `${(i / (n - 1)) * w},${h - p * h}`).join(' ')
  const area = `0,${h} ${line} ${w},${h}`
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" style="display:block" preserveAspectRatio="none">
    <defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="${fill}" stop-opacity="0.34"/>
      <stop offset="100%" stop-color="${fill}" stop-opacity="0"/>
    </linearGradient></defs>
    <polygon points="${area}" fill="url(#${gid})"/>
    <polyline points="${line}" fill="none" stroke="${stroke}" stroke-width="${sw}" stroke-linejoin="round" stroke-linecap="round"/>
  </svg>`
}

// K 線（含均線 ma）
export function candles({ seed = 11, n = 44, w = 460, h = 240, up = '#5fcf80', down = '#e25563', grid = 'rgba(255,255,255,0.05)', ma = '#e0a33e', pad = 6 }) {
  const r = mulberry32(seed)
  const c = []
  let price = 100
  for (let i = 0; i < n; i++) {
    const drift = (r() - 0.42) * 4.2
    const o = price
    const close = Math.max(20, o + drift)
    const hi = Math.max(o, close) + r() * 2.6
    const lo = Math.min(o, close) - r() * 2.6
    c.push({ o, c: close, h: hi, l: lo })
    price = close
  }
  const lo = Math.min(...c.map((d) => d.l))
  const hi = Math.max(...c.map((d) => d.h))
  const Y = (val) => pad + (1 - (val - lo) / (hi - lo)) * (h - pad * 2)
  const cw = w / n
  const bw = cw * 0.58
  const maPts = c
    .map((_, i) => {
      const s = Math.max(0, i - 6)
      const seg = c.slice(s, i + 1)
      const avg = seg.reduce((a, d) => a + d.c, 0) / seg.length
      return `${i * cw + cw / 2},${Y(avg)}`
    })
    .join(' ')
  const gridLines = [0.2, 0.4, 0.6, 0.8]
    .map((g) => `<line x1="0" x2="${w}" y1="${g * h}" y2="${g * h}" stroke="${grid}" stroke-width="1"/>`)
    .join('')
  const bars = c
    .map((d, i) => {
      const x = i * cw + cw / 2
      const col = d.c >= d.o ? up : down
      const ry = Y(Math.max(d.o, d.c))
      const rh = Math.max(1, Math.abs(Y(d.o) - Y(d.c)))
      return `<line x1="${x}" x2="${x}" y1="${Y(d.h)}" y2="${Y(d.l)}" stroke="${col}" stroke-width="1"/><rect x="${x - bw / 2}" y="${ry}" width="${bw}" height="${rh}" fill="${col}"/>`
    })
    .join('')
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" style="display:block;width:100%;height:auto">
    ${gridLines}${bars}
    <polyline points="${maPts}" fill="none" stroke="${ma}" stroke-width="1.6" opacity="0.9"/>
  </svg>`
}

// 板塊 × 期間 熱力格
export function heatmap({ seed = 21, rows = 7, cols = 12, cell = 30, gap = 3, up = '#19a974', down = '#e0556a' }) {
  const r = mulberry32(seed)
  const W = cols * (cell + gap) - gap
  const H = rows * (cell + gap) - gap
  const colorFor = (v) => {
    const a = Math.min(1, Math.abs(v))
    return v >= 0
      ? `color-mix(in srgb, ${up} ${Math.round(18 + a * 78)}%, transparent)`
      : `color-mix(in srgb, ${down} ${Math.round(18 + a * 78)}%, transparent)`
  }
  let cells = ''
  for (let ri = 0; ri < rows; ri++) {
    for (let ci = 0; ci < cols; ci++) {
      const v = (r() - 0.45) * 2
      cells += `<rect x="${ci * (cell + gap)}" y="${ri * (cell + gap)}" width="${cell}" height="${cell}" rx="2" fill="${colorFor(v)}"/>`
    }
  }
  return `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" style="display:block;max-width:100%">${cells}</svg>`
}

// 相對輪動圖 RRG（四象限 + 軌跡 + 標籤）
export function rrg({ w = 320, h = 320, grid = 'rgba(255,255,255,0.08)', text = 'rgba(255,255,255,0.5)', quad = ['#19a974', '#3b82f6', '#e0556a', '#e0a33e'] }) {
  const cx = w / 2
  const cy = h / 2
  // 四條軌跡各落一個象限，終點分開避免標籤重疊
  const trails = [
    { c: quad[0], label: '科技', pts: [[0.6, 0.5], [0.66, 0.45], [0.72, 0.4]] }, // 領先
    { c: quad[1], label: '金融', pts: [[0.56, 0.5], [0.6, 0.56], [0.64, 0.62]] }, // 轉弱
    { c: quad[2], label: '能源', pts: [[0.44, 0.52], [0.4, 0.58], [0.34, 0.64]] }, // 落後
    { c: quad[3], label: '醫療', pts: [[0.46, 0.5], [0.42, 0.45], [0.38, 0.4]] }, // 改善
  ]
  const X = (t) => t * w
  const Y = (t) => t * h
  const quads =
    `<rect x="0" y="0" width="${cx}" height="${cy}" fill="${quad[1]}" opacity="0.05"/>` +
    `<rect x="${cx}" y="0" width="${cx}" height="${cy}" fill="${quad[0]}" opacity="0.06"/>` +
    `<rect x="0" y="${cy}" width="${cx}" height="${cy}" fill="${quad[2]}" opacity="0.06"/>` +
    `<rect x="${cx}" y="${cy}" width="${cx}" height="${cy}" fill="${quad[3]}" opacity="0.05"/>`
  const axes =
    `<line x1="${cx}" y1="0" x2="${cx}" y2="${h}" stroke="${grid}" stroke-width="1"/>` +
    `<line x1="0" y1="${cy}" x2="${w}" y2="${cy}" stroke="${grid}" stroke-width="1"/>`
  const labels =
    `<text x="${w - 6}" y="14" fill="${text}" font-size="10" text-anchor="end" font-family="monospace">領先 Leading</text>` +
    `<text x="6" y="${h - 6}" fill="${text}" font-size="10" font-family="monospace">落後 Lagging</text>`
  const trailSvg = trails
    .map((t) => {
      const path = t.pts.map((p) => `${X(p[0])},${Y(p[1])}`).join(' ')
      const last = t.pts[t.pts.length - 1]
      const dots = t.pts
        .map((p, j) => {
          const isLast = j === t.pts.length - 1
          return `<circle cx="${X(p[0])}" cy="${Y(p[1])}" r="${isLast ? 5 : 2.2}" fill="${t.c}" opacity="${isLast ? 1 : 0.45}"/>`
        })
        .join('')
      return `<polyline points="${path}" fill="none" stroke="${t.c}" stroke-width="1.4" opacity="0.5" stroke-dasharray="3 2"/>${dots}<text x="${X(last[0]) + 8}" y="${Y(last[1]) + 3}" fill="${t.c}" font-size="11" font-weight="600">${t.label}</text>`
    })
    .join('')
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" style="display:block;max-width:100%">${quads}${axes}${labels}${trailSvg}</svg>`
}

// 環形分數計
export function gauge({ value = 78, size = 92, stroke = 10, color = '#38bdf8', track = 'rgba(255,255,255,0.1)', text = '#fff', label = '' }) {
  const r = (size - stroke) / 2
  const cc = 2 * Math.PI * r
  const off = cc * (1 - value / 100)
  const lbl = label
    ? `<text x="50%" y="68%" dominant-baseline="middle" text-anchor="middle" fill="${text}" opacity="0.55" font-size="${size * 0.13}">${label}</text>`
    : ''
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" style="display:block">
    <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="${track}" stroke-width="${stroke}"/>
    <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="${color}" stroke-width="${stroke}" stroke-dasharray="${cc}" stroke-dashoffset="${off}" stroke-linecap="round" transform="rotate(-90 ${size / 2} ${size / 2})"/>
    <text x="50%" y="48%" dominant-baseline="middle" text-anchor="middle" fill="${text}" font-size="${size * 0.28}" font-weight="700" font-family="monospace">${value}</text>${lbl}
  </svg>`
}

// 迷你直條
export function barMini({ seed = 5, n = 14, w = 120, h = 34, color = '#38bdf8' }) {
  const r = mulberry32(seed)
  const bw = w / n
  let bars = ''
  for (let i = 0; i < n; i++) {
    const v = 0.2 + r() * 0.8
    bars += `<rect x="${i * bw + bw * 0.15}" y="${h - v * h}" width="${bw * 0.7}" height="${v * h}" rx="1" fill="${color}" opacity="${0.5 + v * 0.5}"/>`
  }
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" style="display:block">${bars}</svg>`
}

// 正負雙向資金流條
export function flowBars({ seed = 9, n = 18, w = 240, h = 70, up = '#19a974', down = '#e0556a' }) {
  const r = mulberry32(seed)
  const bw = w / n
  const mid = h / 2
  let bars = `<line x1="0" x2="${w}" y1="${mid}" y2="${mid}" stroke="rgba(255,255,255,0.08)" stroke-width="1"/>`
  for (let i = 0; i < n; i++) {
    const v = (r() - 0.42) * 2
    const bh = Math.abs(v) * (mid - 4)
    bars += `<rect x="${i * bw + bw * 0.2}" y="${v >= 0 ? mid - bh : mid}" width="${bw * 0.6}" height="${bh}" rx="1" fill="${v >= 0 ? up : down}" opacity="0.85"/>`
  }
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" style="display:block;width:100%">${bars}</svg>`
}
