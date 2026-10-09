import { onUnmounted, ref } from 'vue'

/** A `now` that ticks every second (for the live previews), stopped when the editor goes away. */
export function usePreviewClock() {
  const now = ref(new Date())
  const timer = setInterval(() => { now.value = new Date() }, 1000)
  onUnmounted(() => clearInterval(timer))
  return now
}
