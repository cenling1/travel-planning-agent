import { describe, expect, it, vi } from 'vitest'
import { consumeStream } from './ndjson'

function readerFrom(chunks: string[]) {
  const encoder = new TextEncoder()
  return new ReadableStream<Uint8Array>({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)))
      controller.close()
    },
  }).getReader()
}

describe('consumeStream', () => {
  it('parses objects split across arbitrary chunks', async () => {
    const onEvent = vi.fn()
    const onDone = vi.fn()
    await consumeStream(readerFrom([
      '{"type":"progress","stage":"under',
      'standing","message":"理解需求"}\n{"type":"del',
      'ta","content":"北京"}\n',
    ]), { onEvent, onDone })

    expect(onEvent).toHaveBeenCalledTimes(2)
    expect(onEvent.mock.calls[1][0]).toEqual({ type: 'delta', content: '北京' })
    expect(onDone).toHaveBeenCalledTimes(1)
  })

  it('reports a truncated final object', async () => {
    const onError = vi.fn()
    await consumeStream(readerFrom(['{"type":"delta"']), { onEvent: vi.fn(), onError })
    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ message: '流式响应在完整数据到达前中断' }))
  })

  it('reports reader failures', async () => {
    const failure = new Error('connection reset')
    const reader = { read: vi.fn().mockRejectedValue(failure), releaseLock: vi.fn() } as unknown as ReadableStreamDefaultReader<Uint8Array>
    const onError = vi.fn()
    await consumeStream(reader, { onEvent: vi.fn(), onError })
    expect(onError).toHaveBeenCalledWith(failure)
  })
})
