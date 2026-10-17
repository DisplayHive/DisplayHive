<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { fieldHandlerDef } from '../../plugins/registry'
import type { TagConfig } from '../../composables/contentEdit/useContentEditor'
import type { ContainerTextStyle, PreviewContainer } from '../../utils/design/designPreview'
import type { DefaultColor } from '../../types/models'
import FieldValueEditor from '../fields/FieldValueEditor.vue'
import Popover from 'primevue/popover'

// Editing "in the preview": laid over a preview frame (a sandboxed document, so the hot spots go
// over it, not into it). Each container of the preview that a field of the content type fills is a
// hot spot. A simple value (one line or a text area — the handler's `inlineEdit`) is edited right
// there; any other opens the field's own editor, the one the form uses, in a popover. Only what
// the form offers can be edited: a field without a handler, one whose controls are all hidden and a
// locked simple value are not hot spots; with `editable` off (the person lacks the right to change
// the content) there are none at all. Place it inside a `position: relative` box that has the frame.
const props = defineProps<{
  /** The preview's containers with their areas (percent of the frame), keyed by container id. */
  containers: Record<string, PreviewContainer>
  tags: TagConfig[]
  /** The values being edited (a field's key bag); changed in place. */
  fields: Record<string, unknown>
  palette?: DefaultColor[]
  editable: boolean
  /** Per field name: does its editor show any control (false: all hidden). Unknown counts as yes. */
  controlVisible?: Record<string, boolean>
  /** How each container's text looks in the preview (reported by the frame): the in-place editor uses it. */
  textStyles?: Record<string, ContainerTextStyle>
  /**
   * Where a complex field's editor goes: in a popover at the spot (default), or — docked — nowhere here:
   * the layer only says which field was picked (`pick`) and the page shows the editor in a place of its own.
   */
  docked?: boolean
  /** Docked: the field whose editor is open; its spot stays highlighted. */
  activeName?: string | null
}>()

const emit = defineEmits<{ pick: [tag: TagConfig] }>()

interface Spot { tag: TagConfig; containerId: string; style: Record<string, string>; inline: 'input' | 'textarea' | null }

const isLocked = (tag: TagConfig) => !!tag.optionFlags?.[tag.name]?.locked
const isHidden = (tag: TagConfig) => !!tag.optionFlags?.[tag.name]?.hidden

const spots = computed<Spot[]>(() => {
  if (!props.editable) return []
  const out: Spot[] = []
  for (const [id, box] of Object.entries(props.containers)) {
    const tag = props.tags.find((t) => t.containerId === Number(id))
    if (!tag || tag.fieldHandler === '' || isHidden(tag) || props.controlVisible?.[tag.name] === false) continue
    const inline = fieldHandlerDef(tag.fieldHandler)?.inlineEdit ?? null
    if (inline && isLocked(tag)) continue
    out.push({
      tag,
      containerId: id,
      inline,
      style: { top: `${box.top}%`, left: `${box.left}%`, width: `${box.width}%`, height: `${box.height}%` },
    })
  }
  return out
})

// The in-place editor looks like the text will on the display: same font, size and colour (the box
// behind it is dark or light, whichever the text colour is readable on).
const inlineStyle = (spot: Spot): Record<string, string> => {
  const t = props.textStyles?.[spot.containerId]
  if (!t) return {}
  const rgb = /rgba?\((\d+),\s*(\d+),\s*(\d+)/.exec(t.color)
  const light = rgb ? (0.299 * +rgb[1] + 0.587 * +rgb[2] + 0.114 * +rgb[3]) / 255 > 0.5 : false
  return {
    fontFamily: t.fontFamily, fontSize: t.fontSize, fontWeight: t.fontWeight, fontStyle: t.fontStyle,
    color: t.color, lineHeight: t.lineHeight, textAlign: t.textAlign, letterSpacing: t.letterSpacing,
    textTransform: t.textTransform,
    background: light ? 'rgba(0, 0, 0, 0.72)' : 'rgba(255, 255, 255, 0.85)',
  }
}

const inlineName = ref<string | null>(null)
const popoverTag = ref<TagConfig | null>(null)
const popover = ref<InstanceType<typeof Popover> | null>(null)

const openSpot = async (spot: Spot, event: MouseEvent) => {
  if (spot.inline) {
    popover.value?.hide()
    inlineName.value = spot.tag.name
    await nextTick()
    document.querySelector<HTMLElement>('[data-testid="preview-inline-input"]')?.focus()
    return
  }
  inlineName.value = null
  if (props.docked) {
    emit('pick', spot.tag)
    return
  }
  const target = event.currentTarget as HTMLElement
  if (popoverTag.value?.name === spot.tag.name) {
    popover.value?.toggle(event, target)
    return
  }
  popoverTag.value = spot.tag
  await nextTick()
  popover.value?.show(event, target)
}

const closeInline = () => { inlineName.value = null }
</script>

<template>
  <div class="preview-spots">
    <template v-for="spot in spots" :key="spot.tag.name">
      <div v-if="inlineName === spot.tag.name" class="preview-spot preview-spot--editing" :style="spot.style">
        <textarea
          v-if="spot.inline === 'textarea'"
          v-model="fields[spot.tag.name] as string"
          data-testid="preview-inline-input"
          class="preview-inline"
          :style="inlineStyle(spot)"
          :aria-label="spot.tag.title || spot.tag.name"
          @blur="closeInline"
          @keydown.esc="closeInline"
        ></textarea>
        <input
          v-else
          v-model="fields[spot.tag.name] as string"
          data-testid="preview-inline-input"
          class="preview-inline"
          :style="inlineStyle(spot)"
          :aria-label="spot.tag.title || spot.tag.name"
          @blur="closeInline"
          @keydown.enter="closeInline"
          @keydown.esc="closeInline"
        />
      </div>
      <button
        v-else
        type="button"
        :class="['preview-spot', { 'preview-spot--active': activeName === spot.tag.name }]"
        :style="spot.style"
        :title="`Edit: ${spot.tag.title || spot.tag.name}`"
        :aria-label="`Edit ${spot.tag.title || spot.tag.name}`"
        :data-testid="`preview-spot-${spot.tag.name}`"
        @click="openSpot(spot, $event)"
      ></button>
    </template>
    <Popover v-if="!docked" ref="popover">
      <div v-if="popoverTag" class="preview-popover" data-testid="preview-popover">
        <strong class="preview-popover-title">{{ popoverTag.title || popoverTag.name }}</strong>
        <FieldValueEditor
          :tag="popoverTag"
          :fields="fields"
          mode="edit"
          :palette="palette ?? []"
          :option-flags="popoverTag.optionFlags"
        />
      </div>
    </Popover>
  </div>
</template>

<style scoped>
.preview-spots {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.preview-spot {
  position: absolute;
  padding: 0;
  background: transparent;
  border: 1px dashed transparent;
  border-radius: 3px;
  cursor: pointer;
  pointer-events: auto;
}

.preview-spot:hover,
.preview-spot:focus-visible {
  border-color: var(--p-primary-color, #f5c400);
  background: color-mix(in srgb, var(--p-primary-color, #f5c400) 12%, transparent);
  outline: none;
}

.preview-spot--active {
  border-color: var(--p-primary-color, #f5c400);
  background: color-mix(in srgb, var(--p-primary-color, #f5c400) 18%, transparent);
}

.preview-spot--editing {
  pointer-events: auto;
  z-index: 2;
}

.preview-inline {
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  resize: none;
  padding: 0.25rem 0.4rem;
  font: inherit;
  font-size: 0.9rem;
  color: var(--p-text-color, #111);
  background: var(--p-content-background, #fff);
  /* (font, size and colour of the display replace these once the frame has reported them) */
  border: 2px solid var(--p-primary-color, #f5c400);
  border-radius: 3px;
}

.preview-popover {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  width: min(26rem, 80vw);
}
</style>
