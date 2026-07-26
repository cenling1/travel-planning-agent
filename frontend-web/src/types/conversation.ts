// ---- Conversations ----

export interface Conversation {
  id: string
  client_id: string
  title: string
  summary: string
  created_at: string
  updated_at: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface ConversationDetail extends Conversation {
  messages: Message[]
}

export interface ConversationCreate {
  client_id: string
  title: string
}
