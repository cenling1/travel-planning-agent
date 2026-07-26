// ============================================================
// Layer 4: Store — Chat
// Manages streaming generation state per conversation
// ============================================================

import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { TravelResponse, StreamEvent } from '@/types/chat'
import { chatApi } from '@/api/chat'
import { useConversationStore } from './conversation'

export interface ChatSessionState {
  isGenerating: boolean
  progress: string
  streamingContent: string
  response: TravelResponse | null
  error: string | null
  abortController: AbortController | null
  pendingUserQuery: string
  lastQuery: string
  stopped: boolean
  matchingUserCountAtStart: number
}

export const useChatStore = defineStore('chat', () => {
  // ---- State ----
  // Map of conversationId → ChatSessionState, supporting multiple tabs/sessions
  const sessions = ref<Record<string, ChatSessionState>>({})
  const defaultSession: ChatSessionState = {
    isGenerating: false,
    progress: '',
    streamingContent: '',
    response: null,
    error: null,
    abortController: null,
    pendingUserQuery: '',
    lastQuery: '',
    stopped: false,
    matchingUserCountAtStart: 0,
  }

  // ---- Getters ----
  function sessionFor(conversationId: string | null): ChatSessionState {
    const id = conversationId || '__new__'
    if (!sessions.value[id]) {
      sessions.value[id] = { ...defaultSession }
    }
    return sessions.value[id]
  }

  // ---- Actions ----
  function initSession(conversationId: string | null) {
    const id = conversationId || '__new__'
    sessions.value[id] = { ...defaultSession }
  }

  function cleanupSession(conversationId: string | null) {
    const id = conversationId || '__new__'
    const session = sessions.value[id]
    if (session?.abortController) {
      session.abortController.abort()
    }
    delete sessions.value[id]
  }

  async function sendMessage(query: string, conversationId: string | null): Promise<void> {
    const convStore = useConversationStore()
    const session = sessionFor(conversationId)

    // Prevent duplicate submission
    if (session.isGenerating) return

    // Synchronize the previous completed turn before replacing its local overlay.
    if (session.response && conversationId) {
      await convStore.fetchDetail(conversationId)
    }

    session.isGenerating = true
    session.progress = '正在理解旅行需求…'
    session.streamingContent = ''
    session.response = null
    session.error = null
    session.pendingUserQuery = query
    session.lastQuery = query
    session.stopped = false
    session.matchingUserCountAtStart = convStore.currentDetail?.messages.filter(
      (message) => message.role === 'user' && message.content === query,
    ).length || 0
    session.abortController = new AbortController()

    try {
      await chatApi.chatStream(
        {
          query,
          client_id: 'web',
          conversation_id: conversationId,
        },
        {
          signal: session.abortController.signal,
          onEvent: (event: StreamEvent) => handleStreamEvent(event, session, convStore),
          onError: (err: Error) => {
            session.error = err.message || '流式传输错误'
            session.isGenerating = false
          },
          onDone: () => {
            session.isGenerating = false
            session.progress = ''
          },
        },
      )
    } catch (err) {
      session.error = err instanceof Error ? err.message : '发送消息失败'
      session.isGenerating = false
    }
  }

  function handleStreamEvent(
    event: StreamEvent,
    session: ChatSessionState,
    convStore: ReturnType<typeof useConversationStore>,
  ) {
    switch (event.type) {
      case 'status':
      case 'progress':
        session.progress = event.message
        break
      case 'delta':
        session.streamingContent += event.content
        break
      case 'complete':
        session.response = event.response
        session.progress = ''
        convStore.fetchList()
        break
      case 'error':
        session.error = event.message
        break
    }
  }

  function stopGeneration(conversationId: string | null) {
    const session = sessionFor(conversationId)
    if (session.abortController && session.isGenerating) {
      session.abortController.abort()
      session.isGenerating = false
      session.progress = '已停止生成'
      session.stopped = true
    }
  }

  function retryMessage(conversationId: string | null, query?: string) {
    const session = sessionFor(conversationId)
    return sendMessage(query || session.lastQuery, conversationId)
  }

  return {
    sessions,
    sessionFor,
    initSession,
    cleanupSession,
    sendMessage,
    stopGeneration,
    retryMessage,
  }
})
