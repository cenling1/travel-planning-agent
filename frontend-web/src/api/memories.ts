// ============================================================
// Layer 3: API — Memories module
// ============================================================

import { http } from '@/utils/http'
import type { Memory, MemoryCreate } from '@/types/memory'

export const memoriesApi = {
  list(): Promise<Memory[]> {
    return http.get<Memory[]>('/api/memories')
  },

  create(payload: MemoryCreate): Promise<Memory> {
    return http.post<Memory>('/api/memories', { body: payload })
  },

  delete(id: string): Promise<void> {
    return http.delete(`/api/memories/${id}`)
  },
}
