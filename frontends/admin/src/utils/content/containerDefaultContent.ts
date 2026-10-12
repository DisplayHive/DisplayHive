import { blankPretalxTableValue } from './pretalxTable'

/** Field handler options for a container's default content ("None" first: it is optional). */
export const DEFAULT_FIELD_HANDLER_OPTIONS = [
  { label: 'None', value: '' },
  { label: 'Arrow', value: 'arrows' },
  { label: 'Countdown', value: 'countdown' },
  { label: 'Date / Time Format', value: 'datetime_format' },
  { label: 'HTML (raw)', value: 'rawhtml' },
  { label: 'Icon', value: 'icon' },
  { label: 'iFrame', value: 'iframe' },
  { label: 'Lauftext (Marquee)', value: 'marquee' },
  { label: 'Image', value: 'image' },
  { label: 'Link/URL', value: 'link' },
  { label: 'Long Text', value: 'textbig' },
  { label: 'Number', value: 'numbers' },
  { label: 'Pretalx Table', value: 'pretalx_table' },
  { label: 'Short Text', value: 'textklein' },
  { label: 'Table', value: 'table' },
  { label: 'WYSIWYG', value: 'wysiwyg' },
]

/**
 * The starting value of `default_content` after switching a container's handler: handlers that
 * keep structured data (packed as JSON into default_content) get an empty one of their shape,
 * plain-text handlers an empty string.
 */
export const defaultContentFor = (handler: string): string => {
  switch (handler) {
    case 'arrows': return JSON.stringify({ char: '', size: 5 })
    case 'image': return JSON.stringify({ url: '', size: null })
    case 'icon': return JSON.stringify({ icon: '', size: 5, color: '' })
    case 'table': return JSON.stringify({ columns: ['Column 1', 'Column 2'], rows: [['', '']] })
    case 'pretalx_table': return JSON.stringify(blankPretalxTableValue())
    case 'datetime_format': return 'HH:mm:ss'
    case 'marquee': return JSON.stringify({ text: '', speed: 20 })
    case 'countdown': return JSON.stringify({ target: '', format: 'DD:HH:mm:ss', finished_text: '' })
    default: return ''
  }
}
