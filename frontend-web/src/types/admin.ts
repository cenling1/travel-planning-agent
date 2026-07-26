// ---- Admin ----

export interface AdminUserUpdate {
  role?: 'user' | 'admin' | null
  is_active?: boolean | null
}

export interface AdminUserCreate {
  username: string
  email?: string | null
  password: string
  role: 'user' | 'admin'
}

export interface AdminPasswordReset {
  new_password: string
}
