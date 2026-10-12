// Date/time format tokens of the Pretalx screens, and a preview formatter that
// follows the same token rules, so the Pretalx page can show what a format gives.

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

/** Formats `d` in `timezone` using `fmt` (tokens as listed in FORMAT_TOKENS). */
export function formatDateStr(d: Date, fmt: string, timezone: string): string {
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
  } catch { return fmt }
}
