// ============================================================
// Layer 3: API — Conversations module
// ============================================================

import { http } from '@/utils/http'
import type { Conversation, ConversationDetail } from '@/types/conversation'

export const conversationsApi = {
  list(): Promise<Conversation[]> {
    return http.get<Conversation[]>('/api/conversations')
  },

  get(id: string): Promise<ConversationDetail> {
    return http.get<ConversationDetail>(`/api/conversations/${id}`)
  },

  create(title?: string): Promise<Conversation> {
    return http.post<Conversation>('/api/conversations', {
      body: { client_id: 'web', title: title || '新旅行规划' },
    })
  },

  delete(id: string): Promise<void> {
    return http.delete(`/api/conversations/${id}`)
  },
}
