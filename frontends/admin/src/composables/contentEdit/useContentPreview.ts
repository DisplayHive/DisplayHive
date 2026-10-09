import { computed, onMounted, onUnmounted, ref, watch, type Ref } from 'vue'
import { useSocket } from '../useSocket'
import { useAspectRatios, BASE_ASPECT_RATIO } from '../useAspectRatios'
import { buildDesignPreviewSrcdoc, type DesignPreviewPayload, type PreviewContainer } from '../../utils/designPreview'
import type { DefaultColor } from '../../types/models'

interface PreviewData { design: DesignPreviewPayload; containers: Record<string, PreviewContainer>; aspect_ratio?: string }

/**
 * Live preview: renders the in-progress (possibly unsaved) form fields through the Contenttype's
 * actual Layout + the active Design, debounced so it doesn't fire a server round trip on every
 * keystroke. srcdoc assembly itself lives in utils/designPreview.ts, shared with
 * ContentTable.vue's row-expansion preview for already-saved content.
 */
export function useContentPreview(form: Ref<{ contenttype_id: number | null; fields: Record<string, unknown> }>) {
  const { on, off, emit } = useSocket()

  // Which aspect ratio the preview shows (resolved server-side to the Layout's best matching
  // variation, like a screen of that ratio).
  const { ratios: previewRatios } = useAspectRatios()
  const previewRatio = ref(BASE_ASPECT_RATIO)
  const previewData = ref<PreviewData | null>(null)
  let previewTimer: ReturnType<typeof setTimeout> | null = null

  const handleContentPreview = (data: PreviewData) => {
    previewData.value = data
  }

  // Active Design's color palette, from the preview payload — offered as quick-pick swatches by
  // the icon handler's color picker.
  const designPalette = computed<DefaultColor[]>(() => previewData.value?.design?.default_colors ?? [])

  const requestPreview = () => {
    if (!form.value.contenttype_id) {
      previewData.value = null
      return
    }
    emit('displayhive:admin:cts:preview_content_element', {
      contenttype_id: form.value.contenttype_id,
      aspect_ratio: previewRatio.value,
      ...form.value.fields,
    })
  }

  watch(previewRatio, requestPreview)

  watch(
    () => [form.value.contenttype_id, form.value.fields],
    () => {
      if (previewTimer) clearTimeout(previewTimer)
      previewTimer = setTimeout(requestPreview, 500)
    },
    { deep: true },
  )

  const previewSrcdoc = ref('')
  watch(
    previewData,
    async (data) => {
      const srcdoc = await buildDesignPreviewSrcdoc(data?.design, data?.containers)
      // Guard against an older (slower) resolution overwriting a newer one.
      if (previewData.value === data) previewSrcdoc.value = srcdoc
    },
    { immediate: true },
  )

  onMounted(() => on('displayhive:admin:stc:content_element_preview', handleContentPreview))
  onUnmounted(() => {
    off('displayhive:admin:stc:content_element_preview', handleContentPreview)
    if (previewTimer) clearTimeout(previewTimer)
  })

  const reset = () => {
    previewData.value = null
    if (previewTimer) clearTimeout(previewTimer)
  }

  return { previewRatios, previewRatio, previewSrcdoc, designPalette, reset }
}
