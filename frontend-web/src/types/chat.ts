// ---- Chat & Streaming ----

export interface Citation {
  index: number
  source: string
  page: number | null
  chunk_id: string
  excerpt: string
  score: number
}

export interface ToolResult {
  name: string
  success: boolean
  content: string
  latency_ms: number
}

export interface TravelRequest {
  query: string
  client_id: string
  conversation_id: string | null
}

export interface TravelResponse {
  conversation_id: string
  answer: string
  citations: Citation[]
  tools: ToolResult[]
  scenario_type: 'simple' | 'complex' | 'multi_destination'
  retrieved_chunks: number
  trip_summary: TripSummary
}

export interface TripSummary {
  destination: string | null
  origin: string | null
  travel_date: string | null
  travel_days: number | null
  travelers: number | null
  budget: number | null
  preferences: string[]
}

// ---- Stream Events ----
export type StreamEventType = 'status' | 'progress' | 'delta' | 'complete' | 'error'

export interface StreamStatusEvent {
  type: 'status'
  message: string
}

export interface StreamProgressEvent {
  type: 'progress'
  stage: 'understanding' | 'research' | 'realtime' | 'writing'
  message: string
}

export interface StreamDeltaEvent {
  type: 'delta'
  content: string
}

export interface StreamCompleteEvent {
  type: 'complete'
  response: TravelResponse
}

export interface StreamErrorEvent {
  type: 'error'
  message: string
}

export type StreamEvent =
  | StreamStatusEvent
  | StreamProgressEvent
  | StreamDeltaEvent
  | StreamCompleteEvent
  | StreamErrorEvent
