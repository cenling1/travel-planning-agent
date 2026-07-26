// ============================================================
// Layer 2: Utility — Formatters & display helpers
// ============================================================

/**
 * Format ISO timestamp to human-readable string in zh-CN locale.
 */
export function formatDate(iso: string, format: 'full' | 'date' | 'relative' = 'full'): string {
  // SQLite stores UTC timestamps without an offset; browsers otherwise interpret them as local time.
  const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(iso) ? iso : `${iso}Z`
  const date = new Date(normalized)
  if (isNaN(date.getTime())) return '—'

  switch (format) {
    case 'date':
      return date.toLocaleDateString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
      })
    case 'relative':
      return formatRelative(date)
    case 'full':
    default:
      return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
  }
}

function formatRelative(date: Date): string {
  const now = Date.now()
  const diff = now - date.getTime()
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  if (hours < 24) return `${hours} 小时前`
  if (days < 7) return `${days} 天前`
  return date.toLocaleDateString('zh-CN')
}

/**
 * Format file size in human-readable form.
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  const size = bytes / Math.pow(1024, i)
  return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

/**
 * Document status display mapping.
 */
export function documentStatusLabel(status: string): string {
  const map: Record<string, string> = {
    processing: '处理中',
    ready: '就绪',
    error: '失败',
  }
  return map[status] || status
}

export function documentStatusType(status: string): 'info' | 'success' | 'danger' {
  const map: Record<string, 'info' | 'success' | 'danger'> = {
    processing: 'info',
    ready: 'success',
    error: 'danger',
  }
  return map[status] || 'info'
}

/**
 * Memory type display mapping.
 */
export function memoryTypeLabel(type: string): string {
  const map: Record<string, string> = {
    preference: '偏好',
    fact: '事实',
    constraint: '约束',
  }
  return map[type] || type
}

/**
 * Importance as percentage for progress bars.
 */
export function importancePercent(value: number): number {
  return Math.round(value * 100)
}

/**
 * Truncate string to given length.
 */
export function truncate(text: string, length: number): string {
  if (text.length <= length) return text
  return text.substring(0, length) + '…'
}
