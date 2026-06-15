/* charts.jsx — reusable, themeable SVG chart primitives for BamHI Quant landings.
   All deterministic (seeded) so they look like real market data.
   Theme via explicit color props so the same chart reskins per direction.
   Exports to window: Spark, AreaSpark, Candles, Heatmap, RRG, Gauge, BarMini, FlowBars */

function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ── Sparkline ──────────────────────────────────────────────
function Spark({ seed = 3, n = 32, stroke = '#5fcf80', w = 120, h = 34, sw = 1.6 }) {
  const r = mulberry32(seed);
  const pts = [];
  let v = 0.5;
  for (let i = 0; i < n; i++) { v += (r() - 0.46) * 0.16; v = Math.max(0.08, Math.min(0.92, v)); pts.push(v); }
  const path = pts.map((p, i) => `${(i / (n - 1)) * w},${h - p * h}`).join(' ');
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ display: 'block', overflow: 'visible' }}>
      <polyline points={path} fill="none" stroke={stroke} strokeWidth={sw} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

// ── Area sparkline with gradient fill ─────────────────────
function AreaSpark({ seed = 7, n = 60, stroke = '#38bdf8', fill = '#38bdf8', w = 300, h = 90, sw = 2 }) {
  const r = mulberry32(seed);
  const pts = [];
  let v = 0.42;
  for (let i = 0; i < n; i++) { v += (r() - 0.44) * 0.13; v = Math.max(0.06, Math.min(0.94, v)); pts.push(v); }
  const gid = 'ag' + seed + Math.round(w);
  const line = pts.map((p, i) => `${(i / (n - 1)) * w},${h - p * h}`).join(' ');
  const area = `0,${h} ${line} ${w},${h}`;
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ display: 'block' }} preserveAspectRatio="none">
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={fill} stopOpacity="0.34" />
          <stop offset="100%" stopColor={fill} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={area} fill={`url(#${gid})`} />
      <polyline points={line} fill="none" stroke={stroke} strokeWidth={sw} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

// ── Candlestick chart ─────────────────────────────────────
function Candles({ seed = 11, n = 44, w = 460, h = 240, up = '#5fcf80', down = '#e25563', grid = 'rgba(255,255,255,0.05)', ma = '#e0a33e', pad = 6 }) {
  const r = mulberry32(seed);
  const c = [];
  let price = 100;
  for (let i = 0; i < n; i++) {
    const drift = (r() - 0.42) * 4.2;
    const o = price;
    const close = Math.max(20, o + drift);
    const hi = Math.max(o, close) + r() * 2.6;
    const lo = Math.min(o, close) - r() * 2.6;
    c.push({ o, c: close, h: hi, l: lo });
    price = close;
  }
  const lo = Math.min(...c.map((d) => d.l));
  const hi = Math.max(...c.map((d) => d.h));
  const Y = (v) => pad + (1 - (v - lo) / (hi - lo)) * (h - pad * 2);
  const cw = w / n;
  const bw = cw * 0.58;
  // moving average
  const maPts = c.map((_, i) => {
    const s = Math.max(0, i - 6);
    const seg = c.slice(s, i + 1);
    const avg = seg.reduce((a, d) => a + d.c, 0) / seg.length;
    return `${i * cw + cw / 2},${Y(avg)}`;
  }).join(' ');
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ display: 'block', width: '100%', height: 'auto' }}>
      {[0.2, 0.4, 0.6, 0.8].map((g) => (
        <line key={g} x1="0" x2={w} y1={g * h} y2={g * h} stroke={grid} strokeWidth="1" />
      ))}
      {c.map((d, i) => {
        const x = i * cw + cw / 2;
        const col = d.c >= d.o ? up : down;
        return (
          <g key={i}>
            <line x1={x} x2={x} y1={Y(d.h)} y2={Y(d.l)} stroke={col} strokeWidth="1" />
            <rect x={x - bw / 2} y={Y(Math.max(d.o, d.c))} width={bw} height={Math.max(1, Math.abs(Y(d.o) - Y(d.c)))} fill={col} />
          </g>
        );
      })}
      <polyline points={maPts} fill="none" stroke={ma} strokeWidth="1.6" opacity="0.9" />
    </svg>
  );
}

// ── Heatmap grid (sector × period) ────────────────────────
function Heatmap({ seed = 21, rows = 7, cols = 12, cell = 30, gap = 3, up = '#19a974', down = '#e0556a', text = 'rgba(255,255,255,0.55)', labels = [] }) {
  const r = mulberry32(seed);
  const W = cols * (cell + gap) - gap;
  const H = rows * (cell + gap) - gap;
  const colorFor = (v) => {
    // v in [-1,1]
    const a = Math.min(1, Math.abs(v));
    return v >= 0
      ? `color-mix(in srgb, ${up} ${Math.round(18 + a * 78)}%, transparent)`
      : `color-mix(in srgb, ${down} ${Math.round(18 + a * 78)}%, transparent)`;
  };
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ display: 'block', maxWidth: '100%' }}>
      {Array.from({ length: rows }).map((_, ri) =>
        Array.from({ length: cols }).map((__, ci) => {
          const v = (r() - 0.45) * 2;
          return (
            <rect key={`${ri}-${ci}`} x={ci * (cell + gap)} y={ri * (cell + gap)} width={cell} height={cell}
              rx="2" fill={colorFor(v)} />
          );
        })
      )}
    </svg>
  );
}

// ── Relative Rotation Graph (RRG) ─────────────────────────
function RRG({ w = 320, h = 320, grid = 'rgba(255,255,255,0.08)', text = 'rgba(255,255,255,0.5)',
  quad = ['#19a974', '#3b82f6', '#e0556a', '#e0a33e'], dots = null }) {
  const cx = w / 2, cy = h / 2;
  const trails = dots || [
    { c: quad[0], label: '科技', pts: [[0.66, 0.34], [0.70, 0.40], [0.74, 0.46]] },
    { c: quad[1], label: '金融', pts: [[0.40, 0.58], [0.46, 0.56], [0.54, 0.52]] },
    { c: quad[2], label: '能源', pts: [[0.34, 0.66], [0.32, 0.62], [0.36, 0.56]] },
    { c: quad[3], label: '醫療', pts: [[0.58, 0.62], [0.56, 0.58], [0.52, 0.50]] },
  ];
  const X = (t) => t * w;
  const Y = (t) => t * h;
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ display: 'block', maxWidth: '100%' }}>
      <rect x="0" y="0" width={cx} height={cy} fill={quad[1]} opacity="0.05" />
      <rect x={cx} y="0" width={cx} height={cy} fill={quad[0]} opacity="0.06" />
      <rect x="0" y={cy} width={cx} height={cy} fill={quad[2]} opacity="0.06" />
      <rect x={cx} y={cy} width={cx} height={cy} fill={quad[3]} opacity="0.05" />
      <line x1={cx} y1="0" x2={cx} y2={h} stroke={grid} strokeWidth="1" />
      <line x1="0" y1={cy} x2={w} y2={cy} stroke={grid} strokeWidth="1" />
      <text x={w - 6} y="14" fill={text} fontSize="10" textAnchor="end" fontFamily="monospace">領先 Leading</text>
      <text x="6" y={h - 6} fill={text} fontSize="10" fontFamily="monospace">落後 Lagging</text>
      {trails.map((t, i) => {
        const path = t.pts.map((p) => `${X(p[0])},${Y(p[1])}`).join(' ');
        const last = t.pts[t.pts.length - 1];
        return (
          <g key={i}>
            <polyline points={path} fill="none" stroke={t.c} strokeWidth="1.4" opacity="0.5" strokeDasharray="3 2" />
            {t.pts.map((p, j) => (
              <circle key={j} cx={X(p[0])} cy={Y(p[1])} r={j === t.pts.length - 1 ? 5 : 2.2}
                fill={t.c} opacity={j === t.pts.length - 1 ? 1 : 0.45} />
            ))}
            <text x={X(last[0]) + 8} y={Y(last[1]) + 3} fill={t.c} fontSize="11" fontWeight="600">{t.label}</text>
          </g>
        );
      })}
    </svg>
  );
}

// ── Radial gauge / score ──────────────────────────────────
function Gauge({ value = 78, size = 92, stroke = 10, color = '#38bdf8', track = 'rgba(255,255,255,0.1)', text = '#fff', label = '' }) {
  const r = (size - stroke) / 2;
  const cc = 2 * Math.PI * r;
  const off = cc * (1 - value / 100);
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ display: 'block' }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={track} strokeWidth={stroke} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke}
        strokeDasharray={cc} strokeDashoffset={off} strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      <text x="50%" y="48%" dominantBaseline="middle" textAnchor="middle" fill={text}
        fontSize={size * 0.28} fontWeight="700" fontFamily="monospace">{value}</text>
      {label && <text x="50%" y="68%" dominantBaseline="middle" textAnchor="middle" fill={text} opacity="0.55" fontSize={size * 0.13}>{label}</text>}
    </svg>
  );
}

// ── Mini vertical bars ────────────────────────────────────
function BarMini({ seed = 5, n = 14, w = 120, h = 34, color = '#38bdf8' }) {
  const r = mulberry32(seed);
  const bw = w / n;
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ display: 'block' }}>
      {Array.from({ length: n }).map((_, i) => {
        const v = 0.2 + r() * 0.8;
        return <rect key={i} x={i * bw + bw * 0.15} y={h - v * h} width={bw * 0.7} height={v * h} rx="1" fill={color} opacity={0.5 + v * 0.5} />;
      })}
    </svg>
  );
}

// ── Institutional flow bars (pos/neg) ─────────────────────
function FlowBars({ seed = 9, n = 18, w = 240, h = 70, up = '#19a974', down = '#e0556a' }) {
  const r = mulberry32(seed);
  const bw = w / n;
  const mid = h / 2;
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ display: 'block', width: '100%' }}>
      <line x1="0" x2={w} y1={mid} y2={mid} stroke="rgba(255,255,255,0.08)" strokeWidth="1" />
      {Array.from({ length: n }).map((_, i) => {
        const v = (r() - 0.42) * 2;
        const bh = Math.abs(v) * (mid - 4);
        return <rect key={i} x={i * bw + bw * 0.2} y={v >= 0 ? mid - bh : mid} width={bw * 0.6} height={bh} rx="1" fill={v >= 0 ? up : down} opacity="0.85" />;
      })}
    </svg>
  );
}

Object.assign(window, { Spark, AreaSpark, Candles, Heatmap, RRG, Gauge, BarMini, FlowBars });
