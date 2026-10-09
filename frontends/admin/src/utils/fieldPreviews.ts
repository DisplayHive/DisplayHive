// Previews shown in the editors of the date/time format and countdown fields: the format as it
// would render right now, and the token reference tables.

export const FORMAT_TOKENS = [
  { token: 'YYYY',  desc: 'Year (4 digits)',        example: '2024'   },
  { token: 'YY',    desc: 'Year (2 digits)',         example: '24'     },
  { token: 'MM',    desc: 'Month (01–12)',           example: '06'     },
  { token: 'M',     desc: 'Month (1–12)',            example: '6'      },
  { token: 'DD',    desc: 'Day (01–31)',             example: '07'     },
  { token: 'D',     desc: 'Day (1–31)',              example: '7'      },
  { token: 'HH',    desc: 'Hour 24h (00–23)',        example: '14'     },
  { token: 'H',     desc: 'Hour 24h (0–23)',         example: '14'     },
  { token: 'hh',    desc: 'Hour 12h (01–12)',        example: '02'     },
  { token: 'h',     desc: 'Hour 12h (1–12)',         example: '2'      },
  { token: 'mm',    desc: 'Minute (00–59)',          example: '05'     },
  { token: 'ss',    desc: 'Second (00–59)',          example: '09'     },
  { token: 'A',     desc: 'AM / PM',                example: 'PM'     },
  { token: 'dddd',  desc: 'Weekday (full)',          example: 'Monday' },
  { token: 'ddd',   desc: 'Weekday (short)',         example: 'Mon'    },
]

export const COUNTDOWN_TOKENS = [
  { token: 'DD', desc: 'Days remaining (padded)',    example: '03' },
  { token: 'D',  desc: 'Days remaining',              example: '3'  },
  { token: 'HH', desc: 'Hours remaining (padded)',    example: '05' },
  { token: 'H',  desc: 'Hours remaining',             example: '5'  },
  { token: 'mm', desc: 'Minutes remaining (padded)',  example: '09' },
  { token: 'm',  desc: 'Minutes remaining',           example: '9'  },
  { token: 'ss', desc: 'Seconds remaining (padded)',  example: '02' },
  { token: 's',  desc: 'Seconds remaining',           example: '2'  },
]

/** *d* formatted with a moment-style *fmt* in the given IANA timezone (the format itself if the zone is invalid). */
export function formatDateString(d: Date, fmt: string, timezone: string): string {
  try {
    const tz = timezone || 'UTC'
    const p = new Intl.DateTimeFormat('en-US', {
      timeZone: tz,
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
      hour12: false, weekday: 'long',
    }).formatToParts(d)
    const p12 = new Intl.DateTimeFormat('en-US', {
      timeZone: tz, hour: 'numeric', hour12: true,
    }).formatToParts(d)
    const wdShort = new Intl.DateTimeFormat('en-US', {
      timeZone: tz, weekday: 'short',
    }).format(d)

    const get   = (type: string) => p.find(x => x.type === type)?.value ?? ''
    const get12 = (type: string) => p12.find(x => x.type === type)?.value ?? ''

    const year   = get('year')
    const month  = get('month')
    const day    = get('day')
    const h24    = parseInt(get('hour'), 10) % 24
    const minute = get('minute')
    const second = get('second')
    const wdFull = get('weekday')
    const h12r   = parseInt(get12('hour'), 10)
    const h12    = h12r === 0 ? 12 : h12r
    const period = (get12('dayPeriod') || (h24 < 12 ? 'AM' : 'PM')).toUpperCase()

    return fmt.replace(/YYYY|YY|dddd|ddd|MM|M|DD|D|HH|H|hh|h|mm|m|ss|s|A|a/g, t => {
      switch (t) {
        case 'YYYY': return year
        case 'YY':   return year.slice(-2)
        case 'dddd': return wdFull
        case 'ddd':  return wdShort
        case 'MM':   return month
        case 'M':    return String(parseInt(month, 10))
        case 'DD':   return day
        case 'D':    return String(parseInt(day, 10))
        case 'HH':   return String(h24).padStart(2, '0')
        case 'H':    return String(h24)
        case 'hh':   return String(h12).padStart(2, '0')
        case 'h':    return String(h12)
        case 'mm':   return minute
        case 'm':    return String(parseInt(minute, 10))
        case 'ss':   return second
        case 's':    return String(parseInt(second, 10))
        case 'A':    return period
        case 'a':    return period.toLowerCase()
        default:     return t
      }
    })
  } catch {
    return fmt
  }
}

/** The time remaining as a countdown format (DD/D days, HH/H hours, mm/m minutes, ss/s seconds). */
export function formatCountdownString(remainingMs: number, fmt: string): string {
  const totalSeconds = Math.max(0, Math.floor(remainingMs / 1000))
  const days = Math.floor(totalSeconds / 86400)
  const hours = Math.floor((totalSeconds % 86400) / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  return fmt.replace(/DD|D|HH|H|mm|m|ss|s/g, t => {
    switch (t) {
      case 'DD': return String(days).padStart(2, '0')
      case 'D':  return String(days)
      case 'HH': return String(hours).padStart(2, '0')
      case 'H':  return String(hours)
      case 'mm': return String(minutes).padStart(2, '0')
      case 'm':  return String(minutes)
      case 'ss': return String(seconds).padStart(2, '0')
      case 's':  return String(seconds)
      default:   return t
    }
  })
}

/** What the countdown field shows as its preview: the remaining time, or the "finished" text. */
export const formatCountdownPreview = (target: string, format: string, finishedText: string, now: Date): string => {
  if (!target) return '—'
  const t = new Date(target).getTime()
  if (isNaN(t)) return 'Invalid date'
  const remainingMs = t - now.getTime()
  return remainingMs <= 0 && finishedText ? finishedText : formatCountdownString(remainingMs, format || 'DD:HH:mm:ss')
}

/** A naive "YYYY-MM-DDTHH:mm" string (no timezone), as the countdown target is stored. */
export const formatCountdownTarget = (d: Date | null): string => {
  if (!d) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export const parseCountdownTarget = (raw: string): Date | null => {
  if (!raw) return null
  const d = new Date(raw)
  return isNaN(d.getTime()) ? null : d
}
