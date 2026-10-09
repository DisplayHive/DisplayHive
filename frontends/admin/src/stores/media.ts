import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { useSocket } from '../composables/useSocket'
import { unwrapEntity } from '../utils/entity'
import type { MediaItem, MediaUsage } from '../types/models'

type RawMediaItemJsonApi = {
  id: string | number
  attributes: {
    title?: string
    filename?: string
    mime_type?: string
    mimetype?: string
    url?: string
    preview_url?: string
    tags?: string[]
    folder?: string
    used_by?: MediaUsage[]
  }
}

type RawMediaItemFlat = {
  id?: string | number
  title?: string
  name?: string
  filename?: string
  mimetype?: string
  mime_type?: string
  url?: string
  preview_url?: string
  preview?: string
  tags?: string[]
  folder?: string
  used_by?: MediaUsage[]
}

type RawMediaItem = RawMediaItemJsonApi | RawMediaItemFlat | string

function normalizeMediaItem(item: RawMediaItem, idx = 0, currentFolder = ''): MediaItem {
  try {
    if (typeof item === 'string') {
      return { id: idx, title: '', filename: '', mimetype: '', folder: currentFolder, preview_url: '', url: '', tags: [] }
    }
    const r = unwrapEntity(item as RawMediaItemFlat)
    return {
      id: Number(r.id || idx),
      title: r.title || r.name || '',
      filename: r.filename || '',
      mimetype: r.mime_type || r.mimetype || '',
      folder: r.folder || currentFolder,
      preview_url: r.preview_url || r.preview || r.url || '',
      url: r.url || '',
      tags: r.tags || [],
      used_by: r.used_by || [],
    }
  } catch {
    return { id: idx, title: '', filename: '', mimetype: '', folder: currentFolder, preview_url: '', url: '', tags: [] }
  }
}

export const useMediaStore = defineStore('media', () => {
  const { on, emit } = useSocket()

  const mediaItems = ref<MediaItem[]>([])
  const loading = ref(false)

  const handleMediaList = (data: {
    media?: RawMediaItem[]
    media_items?: RawMediaItem[]
    data?: RawMediaItem[]
    current_folder?: string
    currentFolder?: string
  }) => {
    const currentFolder = data?.current_folder || data?.currentFolder || ''
    const arr = data?.media || data?.media_items || data?.data || []
    mediaItems.value = arr.map((it, i) => normalizeMediaItem(it, i, currentFolder))
    loading.value = false
  }

  on('displayhive:media:stc:media_list', handleMediaList)

  const fetch = () => {
    loading.value = true
    emit('displayhive:media:cts:get_media')
  }

  const allTags = computed(() => {
    const map = new Map<string, number>()
    mediaItems.value.forEach((m) => {
      ;(m.tags || []).forEach((t) => {
        const key = (t || '').trim()
        if (!key) return
        map.set(key, (map.get(key) || 0) + 1)
      })
    })
    return Array.from(map.entries())
      .map(([tag, count]) => ({ tag, count }))
      .sort((a, b) => b.count - a.count || a.tag.localeCompare(b.tag))
  })

  return { mediaItems, loading, fetch, allTags }
})
