import { describe, it, expect } from 'vitest'
import { dayKey, formatToday } from './timezone'

// 03:30Z on Jun 16: still Jun 15 evening in New York, already afternoon in Tokyo.
const instant = '2026-06-16T03:30:00Z'

describe('dayKey', () => {
  it('depends on the zone, not the machine', () => {
    expect(dayKey(instant, 'America/New_York')).toBe('2026-06-15')
    expect(dayKey(instant, 'Asia/Tokyo')).toBe('2026-06-16')
  })
})

describe('formatToday', () => {
  it('formats in the given zone', () => {
    const now = new Date(instant)
    expect(formatToday('America/New_York', now)).toBe('Monday, June 15, 2026')
    expect(formatToday('Asia/Tokyo', now)).toBe('Tuesday, June 16, 2026')
  })
})
