// ---- Memories ----

export interface Memory {
  id: string
  owner_id: string
  memory_key: string
  memory_type: string
  content: string
  importance: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface MemoryCreate {
  memory_key: string
  content: string
  memory_type: string
  importance: number
}
