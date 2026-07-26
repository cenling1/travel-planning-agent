// ============================================================
// Layer 2: Utility — HTTP client wrapper
// Handles auth headers, 401 interception, refresh lock, timeout
// ============================================================

import { ApiError } from '@/types/system'

// These will be set by the auth store after initialization
let getAccessToken: () => string | null = () => null
let onUnauthorized: (() => Promise<boolean>) | null = null
let clearAuth: (() => void) | null = null
let onAuthExpired: (() => void) | null = null

export function configureHttpClient(deps: {
  getAccessToken: () => string | null
  onUnauthorized: () => Promise<boolean> // returns true if refresh succeeded
  clearAuth: () => void
  onAuthExpired?: () => void
}) {
  getAccessToken = deps.getAccessToken
  onUnauthorized = deps.onUnauthorized
  clearAuth = deps.clearAuth
  onAuthExpired = deps.onAuthExpired || null
}

let refreshLock: Promise<boolean> | null = null

async function tryRefresh(): Promise<boolean> {
  if (!onUnauthorized) return false
  if (refreshLock) return refreshLock
  refreshLock = onUnauthorized().finally(() => {
    refreshLock = null
  })
  return refreshLock
}

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  params?: Record<string, string>
  body?: unknown
  authenticated?: boolean
  timeout?: number
}

function buildUrl(path: string, params?: Record<string, string>): string {
  const url = new URL(path, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, value)
      }
    })
  }
  return url.pathname + url.search
}

async function parseError(response: Response): Promise<ApiError> {
  let detail = `请求失败 (${response.status})`
  try {
    const body = await response.json()
    if (body && typeof body.detail === 'string') {
      detail = body.detail
    }
  } catch {
    // non-JSON response — fall back to statusText
    if (response.statusText) {
      detail = response.statusText
    }
  }
  const messages: Record<number, string> = {
    400: '请求参数有误',
    401: '请先登录',
    403: '权限不足',
    404: '资源不存在',
    429: '请求过于频繁，请稍后再试',
    500: '服务器内部错误',
  }
  const message = messages[response.status] || `请求失败 (${response.status})`
  return new ApiError(message, response.status, detail)
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const {
    params,
    body,
    authenticated = true,
    timeout = 30000,
    signal: externalSignal,
    ...rest
  } = options

  const url = buildUrl(path, params)
  const headers: Record<string, string> = {
    'Accept': 'application/json',
    ...(rest.headers as Record<string, string>),
  }

  if (authenticated) {
    const token = getAccessToken()
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
  }

  const fetchInit: RequestInit = { ...rest, headers, credentials: 'same-origin' }

  if (body instanceof FormData || body instanceof Blob || body instanceof URLSearchParams) {
    fetchInit.body = body
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    fetchInit.body = JSON.stringify(body)
  }

  async function execute(init: RequestInit): Promise<Response> {
    const controller = new AbortController()
    const abort = () => controller.abort()
    externalSignal?.addEventListener('abort', abort, { once: true })
    const timer = setTimeout(abort, timeout)
    try {
      return await fetch(url, { ...init, signal: controller.signal })
    } finally {
      clearTimeout(timer)
      externalSignal?.removeEventListener('abort', abort)
    }
  }

  try {
    let response = await execute(fetchInit)

    // Automatic 401 refresh with single lock
    if (response.status === 401 && authenticated && onUnauthorized) {
      const refreshed = await tryRefresh()
      if (refreshed) {
        // Retry with new token
        const newToken = getAccessToken()
        if (newToken) {
          headers['Authorization'] = `Bearer ${newToken}`
        }
        response = await execute({ ...fetchInit, headers })
      } else {
        // Refresh failed — clear auth and redirect
        clearAuth?.()
        onAuthExpired?.()
        throw new ApiError('登录已过期，请重新登录', 401, 'Refresh token expired')
      }
    }

    if (!response.ok) {
      throw await parseError(response)
    }

    // 204 No Content
    if (response.status === 204) {
      return undefined as T
    }

    return response.json()
  } catch (err) {
    if (err instanceof ApiError) throw err
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiError('请求超时', 408, '请求超时')
    }
    if (err instanceof TypeError && err.message === 'Failed to fetch') {
      throw new ApiError('网络连接失败', 0, 'Failed to fetch')
    }
    throw err
  }
}

export const http = {
  get<T>(path: string, options?: RequestOptions): Promise<T> {
    return request<T>(path, { ...options, method: 'GET' })
  },
  post<T>(path: string, options?: RequestOptions): Promise<T> {
    return request<T>(path, { ...options, method: 'POST' })
  },
  patch<T>(path: string, options?: RequestOptions): Promise<T> {
    return request<T>(path, { ...options, method: 'PATCH' })
  },
  delete(path: string, options?: RequestOptions): Promise<void> {
    return request<void>(path, { ...options, method: 'DELETE' })
  },
  upload<T>(path: string, formData: FormData, options?: RequestOptions): Promise<T> {
    const { authenticated = true, timeout = 120000, ...init } = options || {}
    const headers: Record<string, string> = {
      'Accept': 'application/json',
      ...(init.headers as Record<string, string>),
    }
    if (authenticated) {
      const token = getAccessToken()
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }
    }
    return request<T>(path, {
      ...init,
      authenticated,
      timeout,
      body: formData,
      headers,
      method: 'POST',
    })
  },
}
