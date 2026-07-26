import { describe, expect, it, vi } from 'vitest'
import { formatDate } from './format'

describe('formatDate', () => {
  it('treats timezone-less API timestamps as UTC', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-07-25T10:20:00Z'))
    expect(formatDate('2026-07-25T10:18:00', 'relative')).toBe('2 分钟前')
    vi.useRealTimers()
  })
})
