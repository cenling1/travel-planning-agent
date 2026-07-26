// ============================================================
// Layer 3: API — Admin module
// ============================================================

import { http } from '@/utils/http'
import type { User } from '@/types/auth'
import type { AdminUserCreate, AdminUserUpdate, AdminPasswordReset } from '@/types/admin'

export const adminApi = {
  listUsers(): Promise<User[]> {
    return http.get<User[]>('/api/admin/users')
  },

  createUser(payload: AdminUserCreate): Promise<User> {
    return http.post<User>('/api/admin/users', { body: payload })
  },

  updateUser(userId: string, payload: AdminUserUpdate): Promise<User> {
    return http.patch<User>(`/api/admin/users/${userId}`, { body: payload })
  },

  resetPassword(userId: string, payload: AdminPasswordReset): Promise<User> {
    return http.post<User>(`/api/admin/users/${userId}/reset-password`, { body: payload })
  },
}
