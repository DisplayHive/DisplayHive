// Geometry of the Layout canvas: positions are percentages of the canvas, snapping pulls an
// edge or the centre of a moving/resizing container onto the canvas bounds, onto other
// containers and onto the user's snaplines.

export type Pos = { top: number; left: number; width: number; height: number }

/** 'h' = horizontal line (constrains top/bottom), 'v' = vertical line (constrains left/right). */
export interface Snapline { axis: 'h' | 'v'; position: number }

export type Corner = 'tl' | 'tr' | 'bl' | 'br'

export const SNAP_THRESHOLD = 1.5 // percent
export const MIN_SIZE = 4 // percent

export const clamp = (v: number, min: number, max: number) => Math.min(Math.max(v, min), max)
export const round1 = (v: number) => Math.round(v * 10) / 10

/** Same shape (4:3 == 8:6)? */
export const sameShape = (a: string, b: string) => {
  const [aw = 1, ah = 1] = a.split(':').map(Number)
  const [bw = 1, bh = 1] = b.split(':').map(Number)
  return aw * bh === bw * ah
}

export const closestWithinThreshold = (value: number, targets: number[]): number | null => {
  let best: number | null = null
  let bestDiff = SNAP_THRESHOLD
  for (const t of targets) {
    const diff = Math.abs(value - t)
    if (diff < bestDiff) {
      bestDiff = diff
      best = t
    }
  }
  return best
}

/** Where an edge may snap to: canvas bounds and centre, the other containers, the snaplines. */
export const edgeTargets = (others: Pos[], snaplines: Snapline[]) => {
  const hTargets = [0, 50, 100]
  const vTargets = [0, 50, 100]
  for (const p of others) {
    hTargets.push(p.left, p.left + p.width, p.left + p.width / 2)
    vTargets.push(p.top, p.top + p.height, p.top + p.height / 2)
  }
  for (const line of snaplines) {
    if (line.axis === 'v') hTargets.push(line.position)
    else vTargets.push(line.position)
  }
  return { hTargets, vTargets }
}

// Picks whichever of {left edge, right edge, center} lands closest to a
// target, so a move can snap on center just as readily as on a side.
export const snapAxis = (start: number, size: number, targets: number[]): number => {
  const startSnap = closestWithinThreshold(start, targets)
  const endSnap = closestWithinThreshold(start + size, targets)
  const centerSnap = closestWithinThreshold(start + size / 2, targets)
  const candidates: Array<{ value: number; diff: number }> = []
  if (startSnap !== null) candidates.push({ value: startSnap, diff: Math.abs(start - startSnap) })
  if (endSnap !== null) candidates.push({ value: endSnap - size, diff: Math.abs(start + size - endSnap) })
  if (centerSnap !== null) candidates.push({ value: centerSnap - size / 2, diff: Math.abs(start + size / 2 - centerSnap) })
  if (!candidates.length) return start
  candidates.sort((a, b) => a.diff - b.diff)
  return candidates[0]!.value
}

export const snapMove = (
  left: number, top: number, width: number, height: number,
  targets: { hTargets: number[]; vTargets: number[] },
) => ({
  left: snapAxis(left, width, targets.hTargets),
  top: snapAxis(top, height, targets.vTargets),
})

// Resizes from *corner*, keeping the OPPOSITE corner fixed as the anchor —
// the dragged corner's own edges snap to the same target set moves use.
export const resizeFromCorner = (
  corner: Corner, start: Pos, dxPct: number, dyPct: number,
  targets: { hTargets: number[]; vTargets: number[] },
): Pos => {
  const { hTargets, vTargets } = targets
  const { left: startLeft, top: startTop, width: startWidth, height: startHeight } = start
  const movesLeftEdge = corner === 'tl' || corner === 'bl'
  const movesTopEdge = corner === 'tl' || corner === 'tr'

  const anchorX = movesLeftEdge ? startLeft + startWidth : startLeft
  const anchorY = movesTopEdge ? startTop + startHeight : startTop

  let movingX = movesLeftEdge ? startLeft + dxPct : startLeft + startWidth + dxPct
  let movingY = movesTopEdge ? startTop + dyPct : startTop + startHeight + dyPct

  movingX = movesLeftEdge ? clamp(movingX, 0, anchorX - MIN_SIZE) : clamp(movingX, anchorX + MIN_SIZE, 100)
  movingY = movesTopEdge ? clamp(movingY, 0, anchorY - MIN_SIZE) : clamp(movingY, anchorY + MIN_SIZE, 100)

  const snappedXTarget = closestWithinThreshold(movingX, hTargets)
  const snappedYTarget = closestWithinThreshold(movingY, vTargets)
  if (snappedXTarget !== null) {
    movingX = movesLeftEdge ? clamp(snappedXTarget, 0, anchorX - MIN_SIZE) : clamp(snappedXTarget, anchorX + MIN_SIZE, 100)
  }
  if (snappedYTarget !== null) {
    movingY = movesTopEdge ? clamp(snappedYTarget, 0, anchorY - MIN_SIZE) : clamp(snappedYTarget, anchorY + MIN_SIZE, 100)
  }

  return {
    left: movesLeftEdge ? movingX : anchorX,
    top: movesTopEdge ? movingY : anchorY,
    width: movesLeftEdge ? anchorX - movingX : movingX - anchorX,
    height: movesTopEdge ? anchorY - movingY : movingY - anchorY,
  }
}
