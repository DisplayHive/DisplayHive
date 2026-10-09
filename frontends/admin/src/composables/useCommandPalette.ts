import { onBeforeUnmount, onMounted, ref } from 'vue'

const isOpen = ref(false)

/** Open state of the command palette (components/CommandPalette.vue), shared app-wide. */
export function useCommandPalette() {
  return {
    isOpen,
    open: () => { isOpen.value = true },
    close: () => { isOpen.value = false },
    toggle: () => { isOpen.value = !isOpen.value },
  }
}

/** Ctrl+K / Cmd+K opens (or closes) the palette. Install once, where the palette lives. */
export function useCommandPaletteHotkey() {
  const { toggle } = useCommandPalette()
  const onKey = (event: KeyboardEvent) => {
    if ((event.ctrlKey || event.metaKey) && !event.altKey && !event.shiftKey && event.key.toLowerCase() === 'k') {
      event.preventDefault()
      toggle()
    }
  }
  onMounted(() => window.addEventListener('keydown', onKey))
  onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
}
