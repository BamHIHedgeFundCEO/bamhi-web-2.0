import { toPng } from 'html-to-image'

/**
 * 表格匯出共用工具（市場觀察 / 拐點篩選共用）。
 * dlImg 會在截圖瞬間為目標元素加上 .exporting class —
 * 各 view 需搭配 CSS 解除 max-height / overflow，讓截圖涵蓋完整內容
 * （否則只截到視窗內可見的捲動範圍，且電腦/平板結果不一致）。
 */

function csvCell(v) {
  if (v === null || v === undefined) return ''
  if (typeof v === 'boolean') return v ? 'true' : ''
  const s = String(v)
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

export function dlCsv(rows, cols, filename) {
  if (!rows?.length) return
  const header = cols.map((c) => c.label)
  const lines = rows.map((row) => cols.map((c) => csvCell(row[c.key])).join(','))
  const csv = '﻿' + [header.join(','), ...lines].join('\n') // BOM，Excel 中文不亂碼
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export async function dlImg(el, filename, bg = '#0a0e1a') {
  if (!el) return
  el.classList.add('exporting')
  try {
    // 等一個 frame 讓瀏覽器重排（解除 max-height 後高度才正確）
    await new Promise((r) => requestAnimationFrame(r))
    const dataUrl = await toPng(el, {
      backgroundColor: bg,
      pixelRatio: 2,
      width: el.scrollWidth,
      height: el.scrollHeight,
    })
    const a = document.createElement('a')
    a.href = dataUrl
    a.download = filename
    a.click()
  } catch (e) {
    console.error('[export] 圖片匯出失敗', e)
  } finally {
    el.classList.remove('exporting')
  }
}

export const today = () => new Date().toISOString().slice(0, 10)
