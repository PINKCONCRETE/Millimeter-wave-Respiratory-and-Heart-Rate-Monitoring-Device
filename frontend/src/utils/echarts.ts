export function calculateEchartsFontSize(elt: HTMLElement | null, scaleFactor: number = 1) {
  if (elt === null) {
    return 14 * scaleFactor; // 如果元素为空，返回默认值
  }
  const computedStyle = window.getComputedStyle(elt);
  let fontSize = parseFloat(computedStyle.fontSize) || 14; // 默认14px
  return fontSize * scaleFactor
}

export function calculateEchartsLineWidth(elt: HTMLElement | null, scaleFactor: number = 1) {
  if (elt === null) {
    return 2 * scaleFactor; // 如果元素为空，返回默认值
  }
  const computedStyle = window.getComputedStyle(elt);
  let lineWidth = parseFloat(computedStyle.fontSize) * 0.13 || 2; // 默认1px
  return lineWidth * scaleFactor
}
