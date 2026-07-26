// ============================================================
// Layer 1: TypeScript Type Definitions
// All types mirror backend Pydantic schemas (backend/schemas.py)
// ============================================================

// ---- Auth ----
export interface User {
  id: string
  username: string
  email: string | null
  role: 'user' | 'admin'
  is_active: boolean
  last_login_at: string | null
  created_at: string
  updated_at: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  email?: string | null
  password: string
}

export interface TokenPair {
  access_token: string
  token_type: string
  expires_in: number
  user: User
}

export interface ChangePasswordRequest {
  current_password: string
  new_password: string
}
