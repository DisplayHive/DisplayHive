<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import { useAdminNavigation } from '../composables/useAdminNavigation'
import { useCommandPalette, useCommandPaletteHotkey } from '../composables/useCommandPalette'
import { useTheme } from '../composables/useTheme'
import { useContentStore } from '../stores/content'
import { useMediaStore } from '../stores/media'
import { useRightsStore } from '../stores/rights'
import { useScreengroupsStore } from '../stores/screengroups'
import { useScreensStore } from '../stores/screens'
import { searchEntries, type PaletteEntry } from '../utils/commandSearch'
import { links } from '../utils/links'

// Ctrl+K: jump to a page, an item or an action by typing a few letters. The lists come from the
// stores (loaded when the palette opens, and only for the pages the person may see).
const router = useRouter()
const rights = useRightsStore()
const { isOpen, close } = useCommandPalette()
useCommandPaletteHotkey()
const { pages } = useAdminNavigation()
const { isDark, setTheme } = useTheme()
const contentStore = useContentStore()
const screensStore = useScreensStore()
const screengroupsStore = useScreengroupsStore()
const mediaStore = useMediaStore()

const query = ref('')
const active = ref(0)
const input = ref<{ $el: HTMLInputElement } | null>(null)

const go = (to: Parameters<typeof router.push>[0]) => () => { router.push(to) }

const entries = computed<PaletteEntry[]>(() => {
  const list: PaletteEntry[] = []
  if (rights.can('content.create')) list.push({ id: 'a-content', group: 'Actions', label: 'New content', icon: 'pi pi-plus', keywords: 'create add', run: go('/content/new') })
  if (rights.can('media.upload')) list.push({ id: 'a-upload', group: 'Actions', label: 'Upload media', icon: 'pi pi-upload', keywords: 'add file image', run: go('/media') })
  if (rights.can('screens.create')) list.push({ id: 'a-screen', group: 'Actions', label: 'Add screen', icon: 'pi pi-window-maximize', keywords: 'create new', run: go('/screens') })
  list.push({
    id: 'a-theme', group: 'Actions', label: isDark.value ? 'Switch to light theme' : 'Switch to dark theme',
    icon: isDark.value ? 'pi pi-sun' : 'pi pi-moon', keywords: 'dark light mode', run: () => { void setTheme(isDark.value ? 'light' : 'dark') },
  })
  for (const p of pages.value) list.push({ id: `p-${p.path}`, group: 'Pages', label: p.label, icon: p.icon, run: go(p.path) })
  if (rights.can('content.page')) {
    for (const c of contentStore.content) list.push({ id: `c-${c.id}`, group: 'Content', label: c.title, hint: c.contenttype_name, icon: 'pi pi-box', run: go(links.content(c.id)) })
  }
  if (rights.can('screens.page')) {
    for (const s of screensStore.screens) list.push({ id: `s-${s.id}`, group: 'Screens', label: s.name, hint: s.resolution, icon: 'pi pi-window-maximize', run: go(links.screen(s.id)) })
  }
  if (rights.can('screengroups.page')) {
    for (const g of screengroupsStore.screengroups.filter((x) => !x.is_one_screen)) {
      list.push({ id: `g-${g.id}`, group: 'Screen groups', label: g.name, icon: 'pi pi-clone', run: go(links.screengroup(g.id)) })
    }
  }
  if (rights.can('media.page')) {
    for (const m of mediaStore.mediaItems) {
      list.push({ id: `m-${m.id}`, group: 'Media', label: m.title || m.filename, hint: m.filename, icon: 'pi pi-images', keywords: (m.tags ?? []).join(' '), run: go({ path: '/media', query: { search: m.filename } }) })
    }
  }
  return list
})

const results = computed(() => searchEntries(entries.value, query.value))
// Headings are drawn where the group changes.
const rows = computed(() => results.value.map((entry, i) => ({ entry, i, heading: i === 0 || results.value[i - 1]?.group !== entry.group ? entry.group : '' })))

watch(isOpen, async (open) => {
  if (!open) return
  query.value = ''
  active.value = 0
  if (rights.can('content.page')) contentStore.fetch()
  if (rights.can('screens.page')) screensStore.fetch()
  if (rights.can('screengroups.page')) screengroupsStore.fetch()
  if (rights.can('media.page')) mediaStore.fetch()
  await nextTick()
  input.value?.$el?.focus()
})
watch(query, () => { active.value = 0 })

const choose = (entry: PaletteEntry | undefined) => {
  if (!entry) return
  close()
  entry.run()
}
const move = (step: number) => {
  const n = results.value.length
  if (!n) return
  active.value = (active.value + step + n) % n
  nextTick(() => document.querySelector('.palette-item.active')?.scrollIntoView({ block: 'nearest' }))
}
</script>

<template>
  <Dialog
    v-model:visible="isOpen"
    modal
    dismissable-mask
    :show-header="false"
    position="top"
    :style="{ width: '560px', maxWidth: '95vw', marginTop: '10vh' }"
    :pt="{ content: { style: 'padding: 0.75rem' } }"
  >
    <div class="palette" data-testid="command-palette">
      <InputText
        ref="input"
        v-model="query"
        class="palette-input"
        placeholder="Search pages, content, screens, media …"
        aria-label="Search"
        autocomplete="off"
        @keydown.down.prevent="move(1)"
        @keydown.up.prevent="move(-1)"
        @keydown.enter.prevent="choose(results[active])"
      />
      <ul v-if="rows.length" class="palette-list" role="listbox">
        <template v-for="row in rows" :key="row.entry.id">
          <li v-if="row.heading" class="palette-heading" role="presentation">{{ row.heading }}</li>
          <li
            class="palette-item"
            :class="{ active: row.i === active }"
            role="option"
            :aria-selected="row.i === active"
            :data-testid="`palette-${row.entry.id}`"
            @mousemove="active = row.i"
            @click="choose(row.entry)"
          >
            <i :class="row.entry.icon" />
            <span class="palette-label">{{ row.entry.label }}</span>
            <span v-if="row.entry.hint" class="palette-hint">{{ row.entry.hint }}</span>
          </li>
        </template>
      </ul>
      <p v-else class="palette-empty">Nothing found.</p>
    </div>
  </Dialog>
</template>

<style scoped>
.palette {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.palette-input {
  width: 100%;
}

.palette-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 55vh;
  overflow-y: auto;
}

.palette-heading {
  padding: 0.5rem 0.5rem 0.2rem;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--p-text-muted-color);
}

.palette-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.45rem 0.5rem;
  border-radius: var(--p-border-radius-md, 6px);
  cursor: pointer;
}

/* PrimeVue's own hover/selected tokens, so light and dark theme both follow. */
.palette-item.active {
  background: var(--p-highlight-background);
  color: var(--p-highlight-color);
}

.palette-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.palette-hint {
  color: var(--p-text-muted-color);
  font-size: 0.8rem;
  white-space: nowrap;
}

.palette-empty {
  margin: 0;
  padding: 0.75rem 0.5rem;
  color: var(--p-text-muted-color);
}
</style>
