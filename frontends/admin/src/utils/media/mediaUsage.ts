import type { RouteLocationRaw } from 'vue-router'
import type { MediaItem, MediaUsage } from '../types/models'
import { links } from './links'

const KIND_LABEL: Record<MediaUsage['kind'], string> = {
  content: 'Content',
  contenttype: 'Content type',
  layout: 'Layout',
  container: 'Container',
  design: 'Design',
  setting: 'Setting',
}

/** "Content: Welcome" — what a usage is, for lists and confirmation texts. */
export const usageLabel = (u: MediaUsage): string => `${KIND_LABEL[u.kind]}: ${u.name}`

/** The admin page that shows where the file sits; null for a container outside any layout. */
export function usageLink(u: MediaUsage): RouteLocationRaw | null {
  switch (u.kind) {
    case 'content': return links.content(u.id)
    case 'contenttype': return links.contentType(u.id)
    case 'layout': return links.layout(u.id)
    case 'design': return links.design(u.id)
    case 'setting': return links.settings()
    default: return null
  }
}

export const isUnused = (m: MediaItem): boolean => !(m.used_by && m.used_by.length)

/** The warning added to the delete confirmation of a file that is still in use. */
export function deleteWarning(m: MediaItem): string {
  const users = m.used_by ?? []
  if (!users.length) return ''
  const shown = users.slice(0, 5).map(usageLabel).join(', ')
  const more = users.length > 5 ? ` and ${users.length - 5} more` : ''
  return ` It is still used by ${shown}${more} — those will show a broken file.`
}
