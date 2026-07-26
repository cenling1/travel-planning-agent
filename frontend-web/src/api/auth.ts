// ============================================================
// Layer 3: API — Auth module
// ============================================================

import { http } from '@/utils/http'
import type {
  LoginRequest,
  TokenPair,
  RegisterRequest,
  User,
  ChangePasswordRequest,
} from '@/types/auth'

export const authApi = {
  login(payload: LoginRequest): Promise<TokenPair> {
    return http.post<TokenPair>('/api/auth/login', { body: payload, authenticated: false })
  },

  register(payload: RegisterRequest): Promise<TokenPair> {
    return http.post<TokenPair>('/api/auth/register', { body: payload, authenticated: false })
  },

  refresh(): Promise<TokenPair> {
    return http.post<TokenPair>('/api/auth/refresh', {
      authenticated: false,
    })
  },

  logout(): Promise<void> {
    return http.post<void>('/api/auth/logout', {
      authenticated: false,
    })
  },

  logoutAll(): Promise<void> {
    return http.post<void>('/api/auth/logout-all')
  },

  getMe(): Promise<User> {
    return http.get<User>('/api/auth/me')
  },

  changePassword(payload: ChangePasswordRequest): Promise<void> {
    return http.post<void>('/api/auth/change-password', { body: payload })
  },
}
