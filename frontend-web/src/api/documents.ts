// ============================================================
// Layer 3: API — Documents module
// ============================================================

import { http } from '@/utils/http'
import type {
  Document,
  DocumentUploadResponse,
  SearchRequest,
  SearchResponse,
} from '@/types/document'

export const documentsApi = {
  list(): Promise<Document[]> {
    return http.get<Document[]>('/api/documents')
  },

  upload(files: File[]): Promise<DocumentUploadResponse> {
    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))
    return http.upload<DocumentUploadResponse>('/api/documents', formData)
  },

  search(query: string, topK = 5): Promise<SearchResponse> {
    return http.post<SearchResponse>('/api/documents/search', {
      body: { query, top_k: topK } satisfies SearchRequest,
    })
  },

  reindex(documentId: string): Promise<Document> {
    return http.post<Document>(`/api/documents/${documentId}/reindex`)
  },

  delete(documentId: string): Promise<void> {
    return http.delete(`/api/documents/${documentId}`)
  },
}
