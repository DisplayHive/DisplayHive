import type { WeeklyWindow } from './recurrence'

// Dates and weekly windows as the content forms (the edit page, the delivery settings of a list row) handle them.

/** A copy of the windows from the server (or none), so editing the form never touches the loaded data. */
export const cloneWindows = (v: unknown): WeeklyWindow[] =>
  Array.isArray(v) ? v.map((w) => ({ days: [...(w.days ?? [])], from: String(w.from ?? ''), to: String(w.to ?? '') })) : []

export const parseIsoDate = (v: string | null | undefined): Date | null => {
  if (!v) return null
  const d = new Date(v)
  return isNaN(d.getTime()) ? null : d
}

export const formatDateDisplay = (d: Date | null): string => {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d!.getDate())}.${pad(d!.getMonth() + 1)}.${d!.getFullYear()} ${pad(d!.getHours())}:${pad(d!.getMinutes())}`
}

export const fmtDt = (d: Date | null | undefined): string | null => {
  if (!d) return null
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}
