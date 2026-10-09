import type { DefaultColor } from './models'

/** The Design being edited in the Designs page's dialog (and shared by its panels). */
export interface DesignForm {
  id: number | null
  name: string
  description: string
  html: string
  css: string
  background_color: string
  background_image_url: string
  background_repeat: string
  background_size: string
  background_opacity: number
  background_effect: string
  background_effect_settings: Record<string, number | string | string[]>
  default_colors: DefaultColor[]
  /** Extra aspect ratios ("W:H") offered for Screens and Layout variations; 16:9 is the implicit base. */
  aspect_ratios: string[]
  /** Progress indicator along the bottom of the screen (fills over a scene's duration). */
  indicator_enabled: boolean
  indicator_color: string
  indicator_height: number
  indicator_direction: 'ltr' | 'rtl'
  gradient_ids: number[]
}

export const blankDesignForm = (): DesignForm => ({
  id: null,
  name: '',
  description: '',
  html: '',
  css: '',
  background_color: '',
  background_image_url: '',
  background_repeat: '',
  background_size: '',
  background_opacity: 100,
  background_effect: '',
  background_effect_settings: {},
  default_colors: [],
  aspect_ratios: [],
  indicator_enabled: false,
  indicator_color: '',
  indicator_height: 0.8,
  indicator_direction: 'ltr',
  gradient_ids: [],
})
