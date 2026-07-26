// ============================================================
// Layer 3: API — Chat module (regular + streaming)
// ============================================================

import { http } from '@/utils/http'
import { consumeStream, type StreamOptions } from '@/utils/ndjson'
import type { TravelRequest, TravelResponse } from '@/types/chat'

export const chatApi = {
  async chat(request: TravelRequest): Promise<TravelResponse> {
    return http.post<TravelResponse>('/api/chat', { body: request })
  },

  async chatStream(
    request: TravelRequest,
    options: Omit<StreamOptions, 'onEvent' | 'onError' | 'onDone'> & {
      onEvent: StreamOptions['onEvent']
      onError?: StreamOptions['onError']
      onDone?: StreamOptions['onDone']
    },
  ): Promise<void> {
    const controller = new AbortController()
    if (options.signal) {
      options.signal.addEventListener('abort', () => controller.abort())
    }

    const execute = () => {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        Accept: 'application/x-ndjson',
      }
      const token = streamAuth.getAccessToken()
      if (token) headers.Authorization = `Bearer ${token}`
      return fetch('/api/chat/stream', {
        method: 'POST',
        headers,
        credentials: 'same-origin',
        body: JSON.stringify(request),
        signal: controller.signal,
      })
    }

    let response: Response
    try {
      response = await execute()
      if (response.status === 401 && await streamAuth.refresh()) {
        response = await execute()
      }
    } catch (err) {
      if (controller.signal.aborted) {
        options.onDone?.()
        return
      }
      options.onError?.(err instanceof Error ? err : new Error(String(err)))
      options.onDone?.()
      return
    }

    if (!response.ok) {
      if (response.status === 401) streamAuth.expired()
      let detail = '流式请求失败'
      try {
        const body = await response.json()
        detail = body.detail || detail
      } catch { /* ignore */ }
      options.onError?.(new Error(detail))
      options.onDone?.()
      return
    }

    if (!response.body) {
      options.onError?.(new Error('浏览器不支持 ReadableStream'))
      options.onDone?.()
      return
    }

    const reader = response.body.getReader()
    await consumeStream(reader, options)
  },
}

// Inline access — avoids circular dependency between http.ts ↔ stores
const streamAuth: {
  getAccessToken: () => string | null
  refresh: () => Promise<boolean>
  expired: () => void
} = {
  getAccessToken: () => null as string | null,
  refresh: async () => false,
  expired: () => undefined,
}

export function configureStreamAuth(config: {
  getAccessToken: () => string | null
  refresh: () => Promise<boolean>
  expired: () => void
}) {
  streamAuth.getAccessToken = config.getAccessToken
  streamAuth.refresh = config.refresh
  streamAuth.expired = config.expired
}
