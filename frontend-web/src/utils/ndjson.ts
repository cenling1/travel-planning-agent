// ============================================================
// Layer 2: Utility — NDJSON stream parser
// Handles chunked encoding: partial lines, multiple objects per chunk
// ============================================================

import type { StreamEvent } from '@/types/chat'

export type StreamEventCallback = (event: StreamEvent) => void
export type StreamErrorCallback = (error: Error) => void
export type StreamDoneCallback = () => void

export interface StreamOptions {
  onEvent: StreamEventCallback
  onError?: StreamErrorCallback
  onDone?: StreamDoneCallback
  signal?: AbortSignal
}

/**
 * Consume a ReadableStream<Uint8Array> from fetch,
 * parse as NDJSON, and invoke callbacks for each event.
 */
export async function consumeStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  options: StreamOptions,
): Promise<void> {
  const { onEvent, onError, onDone, signal } = options
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      if (signal?.aborted) {
        break
      }

      let result: ReadableStreamReadResult<Uint8Array>
      try {
        result = await reader.read()
      } catch (err) {
        if (!signal?.aborted) {
          onError?.(err instanceof Error ? err : new Error('网络连接中断'))
        }
        break
      }

      if (result.done) break

      buffer += decoder.decode(result.value, { stream: true })

      // Process complete lines
      const lines = buffer.split('\n')
      // Last element might be incomplete — keep in buffer
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed) continue

        try {
          const event: StreamEvent = JSON.parse(trimmed)
          if (isValidStreamEvent(event)) {
            onEvent(event)
          }
        } catch {
          // Malformed JSON — emit as error but continue
          onError?.(new Error('后端返回了无法解析的流式数据'))
          return
        }

        if (signal?.aborted) {
          return
        }
      }
    }

    // Process remaining buffer content
    if (buffer.trim()) {
      try {
        const event: StreamEvent = JSON.parse(buffer.trim())
        if (isValidStreamEvent(event)) {
          onEvent(event)
        }
      } catch {
        onError?.(new Error('流式响应在完整数据到达前中断'))
      }
    }
  } catch (err) {
    onError?.(err instanceof Error ? err : new Error(String(err)))
  } finally {
    try { reader.releaseLock() } catch { /* already released */ }
    onDone?.()
  }
}

function isValidStreamEvent(event: unknown): event is StreamEvent {
  if (!event || typeof event !== 'object') return false
  const e = event as Record<string, unknown>
  if (e.type === 'status') return typeof e.message === 'string'
  if (e.type === 'progress') return typeof e.message === 'string' && typeof e.stage === 'string'
  if (e.type === 'delta') return typeof e.content === 'string'
  if (e.type === 'complete') return typeof e.response === 'object'
  if (e.type === 'error') return typeof e.message === 'string'
  return false
}
