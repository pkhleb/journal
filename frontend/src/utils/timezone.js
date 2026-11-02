// Server default for users who never set a zone; must match DEFAULT_TIMEZONE
// in backend/app/timeutil.py so a stale cached user agrees with the server.
export const DEFAULT_TIMEZONE = 'America/New_York'

export function browserTimeZone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || DEFAULT_TIMEZONE
  } catch {
    return DEFAULT_TIMEZONE
  }
}

export function supportedTimeZones() {
  try {
    return Intl.supportedValuesOf('timeZone')
  } catch {
    return [DEFAULT_TIMEZONE]
  }
}

// Calendar day ("YYYY-MM-DD") of an instant in the given IANA zone. en-CA
// formats as ISO year-month-day, which is also directly comparable.
export function dayKey(value, timeZone) {
  return new Date(value).toLocaleDateString('en-CA', { timeZone })
}

export function formatToday(timeZone, now = new Date()) {
  return now.toLocaleDateString('en-US', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric', timeZone,
  })
}
