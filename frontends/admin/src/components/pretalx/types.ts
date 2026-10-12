export interface PretalxUrl {
  id: number
  name: string
  url: string
  polling_enabled: boolean
  polling_interval: number
  last_success: string | null
  last_failure: string | null
  is_valid: boolean | null
  next_fetch: string | null
  has_cache: boolean
}

export interface PretalxSettings {
  time_format?: string
  end_of_day?: string
  no_session_text?: string
  coming_up_text?: string
  invalid_data_text?: string
  sim_datetime?: string
}
