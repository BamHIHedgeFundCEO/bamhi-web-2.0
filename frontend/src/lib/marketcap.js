/**
 * 市值分級共用（市場觀察 / 拐點篩選同一套分級與顏色）。
 * Mega ≥ $100B / Large $10–100B / Mid $2–10B / Small $0.3–2B / Micro < $0.3B
 */
export const TIERS = ['Mega', 'Large', 'Mid', 'Small', 'Micro']

export function capTier(mc) {
  if (mc == null) return null
  if (mc >= 100e9) return 'Mega'
  if (mc >= 10e9) return 'Large'
  if (mc >= 2e9) return 'Mid'
  if (mc >= 0.3e9) return 'Small'
  return 'Micro'
}

export function fmtCap(v) {
  if (v == null) return '—'
  const s = v >= 1e12 ? `$${(v / 1e12).toFixed(2)}T` : v >= 1e9 ? `$${(v / 1e9).toFixed(1)}B` : `$${(v / 1e6).toFixed(0)}M`
  return `${s} ${capTier(v)}`
}

export const TIER_COLORS = {
  Mega: '#a78bfa',
  Large: 'var(--color-accent-cyan)',
  Mid: 'var(--color-bull)',
  Small: '#fcd34d',
  Micro: 'var(--color-bear)',
}

export function capColor(v) {
  return TIER_COLORS[capTier(v)] ?? ''
}
