// ---- Documents ----

export interface Document {
  id: string
  filename: string
  file_type: string
  status: 'processing' | 'ready' | 'error'
  visibility: string
  chunk_count: number
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface DocumentUploadResponse {
  documents: Document[]
}

export interface SearchRequest {
  query: string
  top_k: number
}

export interface SearchResponse {
  query: string
  citations: import('./chat').Citation[]
  embedding_provider: string
}
