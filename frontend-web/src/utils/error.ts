// ============================================================
// Layer 2: Utility — Error extraction & handling
// ============================================================

import { ApiError } from '@/types/system'

/**
 * Extract a human-readable message from any error type.
 */
export function extractErrorMessage(err: unknown, fallback = '发生了未知错误'): string {
  if (err instanceof ApiError) {
    return err.detail || err.message
  }
  if (err instanceof Error) {
    return err.message
  }
  if (typeof err === 'string') {
    return err
  }
  if (err && typeof err === 'object' && 'detail' in err) {
    return String((err as { detail: unknown }).detail)
  }
  return fallback
}

/**
 * Check if an error is a network/disconnection error.
 */
export function isNetworkError(err: unknown): boolean {
  if (err instanceof ApiError && err.status === 0) return true
  if (err instanceof TypeError && err.message === 'Failed to fetch') return true
  return false
}

/**
 * Check if an error is a timeout.
 */
export function isTimeoutError(err: unknown): boolean {
  if (err instanceof ApiError && err.status === 408) return true
  if (err instanceof DOMException && err.name === 'AbortError') return true
  return false
}

/**
 * Get a recovery suggestion based on error type.
 */
export function errorRecoveryHint(err: unknown): string | null {
  if (isNetworkError(err)) return '请检查网络连接后重试'
  if (isTimeoutError(err)) return '请求超时，请重试或减少输入内容'
  if (err instanceof ApiError) {
    if (err.status === 401) return '请重新登录'
    if (err.status === 403) return '您没有权限执行此操作'
    if (err.status === 429) return '请稍后再试'
    if (err.status >= 500) return '服务器暂时不可用，请稍后重试'
  }
  return null
}
