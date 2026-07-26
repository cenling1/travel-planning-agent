import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const chatStreamMock = vi.hoisted(() => vi.fn())

vi.mock('@/api/chat', () => ({
  chatApi: {
    chat: vi.fn(),
    chatStream: chatStreamMock,
  },
}))

import { useChatStore } from './chat'

describe('chat store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('blocks duplicate submissions while a stream is active', async () => {
    let finishStream!: () => void
    chatStreamMock.mockReturnValue(new Promise<void>((resolve) => {
      finishStream = resolve
    }))
    const store = useChatStore()

    const first = store.sendMessage('plan a trip', 'conversation-1')
    await Promise.resolve()
    await store.sendMessage('plan a trip', 'conversation-1')

    expect(chatStreamMock).toHaveBeenCalledTimes(1)
    expect(store.sessionFor('conversation-1').isGenerating).toBe(true)

    finishStream()
    await first
  })

  it('aborts the active request and keeps the stopped state visible', async () => {
    chatStreamMock.mockImplementation((_request, options) => new Promise<void>((resolve) => {
      options.signal?.addEventListener('abort', () => resolve(), { once: true })
    }))
    const store = useChatStore()

    const sending = store.sendMessage('plan a trip', 'conversation-2')
    await Promise.resolve()
    const session = store.sessionFor('conversation-2')
    const controller = session.abortController

    store.stopGeneration('conversation-2')
    await sending

    expect(controller?.signal.aborted).toBe(true)
    expect(session.isGenerating).toBe(false)
    expect(session.stopped).toBe(true)
    expect(session.progress).not.toBe('')
  })
})
