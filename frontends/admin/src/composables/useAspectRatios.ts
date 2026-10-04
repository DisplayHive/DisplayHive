import { ref, onMounted, onUnmounted } from 'vue'
import { useSocket } from './useSocket'

/** The base ratio every Layout/Screen has; positions/membership at this
 * ratio live on the container/layout themselves, not in variations. */
export const BASE_ASPECT_RATIO = '16:9'

/** CSS `aspect-ratio` value for a "W:H" string ("4:3" -> "4 / 3"). */
export const cssAspectRatio = (ratio: string | null | undefined): string =>
  (ratio || BASE_ASPECT_RATIO).replace(':', ' / ')

const ratioNumber = (ratio: string): number => {
  const [w = 1, h = 1] = ratio.split(':').map(Number)
  return w / h
}

/** The ratio from *available* closest to *target* (log distance; the base on
 * ties, then the first listed) — mirrors application/aspect_ratio.py's
 * best_ratio, so a preview shows what a screen of that ratio would get. */
export const bestAspectRatio = (target: string | null | undefined, available: string[]): string => {
  if (!available.length) return BASE_ASPECT_RATIO
  if (!target) return available.includes(BASE_ASPECT_RATIO) ? BASE_ASPECT_RATIO : available[0]!
  const t = Math.log(ratioNumber(target))
  let best = available[0]!
  let bestKey: [number, number] = [Infinity, 1]
  for (const r of available) {
    const key: [number, number] = [Math.round(Math.abs(Math.log(ratioNumber(r)) - t) * 1e9), r === BASE_ASPECT_RATIO ? 0 : 1]
    if (key[0] < bestKey[0] || (key[0] === bestKey[0] && key[1] < bestKey[1])) {
      best = r
      bestKey = key
    }
  }
  return best
}

/**
 * The aspect ratios offered by the active Design (16:9 first, then its extra
 * ones), kept live. Used wherever a ratio is picked: Screens, Layout
 * variations, Content previews.
 */
export function useAspectRatios() {
  const { on, off, emit } = useSocket()
  const ratios = ref<string[]>([BASE_ASPECT_RATIO])

  const handle = (data: { ratios?: string[] }) => {
    ratios.value = data?.ratios?.length ? data.ratios : [BASE_ASPECT_RATIO]
  }

  onMounted(() => {
    on('displayhive:admin:stc:aspect_ratios', handle)
    emit('displayhive:admin:cts:get_aspect_ratios')
  })
  onUnmounted(() => off('displayhive:admin:stc:aspect_ratios', handle))

  return { ratios }
}
