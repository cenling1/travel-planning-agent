import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { User } from '@/types/auth'

const authMocks = vi.hoisted(() => ({
  login: vi.fn(),
  register: vi.fn(),
  refresh: vi.fn(),
  logout: vi.fn(),
  logoutAll: vi.fn(),
  getMe: vi.fn(),
  changePassword: vi.fn(),
}))

vi.mock('@/api/auth', () => ({ authApi: authMocks }))

import { useAuthStore } from './auth'

const adminUser: User = {
  id: 'admin-1',
  username: 'admin',
  email: null,
  role: 'admin',
  is_active: true,
  last_login_at: null,
  created_at: '2026-07-25T10:00:00Z',
  updated_at: '2026-07-25T10:00:00Z',
}

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('restores a cookie-backed session and derives admin access', async () => {
    authMocks.refresh.mockResolvedValue({
      access_token: 'access-token',
      token_type: 'bearer',
      expires_in: 900,
      user: adminUser,
    })
    authMocks.getMe.mockResolvedValue(adminUser)
    const store = useAuthStore()

    await expect(store.restoreSession()).resolves.toBe(true)

    expect(store.accessToken).toBe('access-token')
    expect(store.user).toEqual(adminUser)
    expect(store.isAuthenticated).toBe(true)
    expect(store.isAdmin).toBe(true)
    expect(store.restoreAttempted).toBe(true)
    expect(store.isRestoring).toBe(false)
  })

  it('shares one refresh request across concurrent callers', async () => {
    let resolveRefresh!: (value: unknown) => void
    authMocks.refresh.mockReturnValue(new Promise((resolve) => {
      resolveRefresh = resolve
    }))
    authMocks.getMe.mockResolvedValue(adminUser)
    const store = useAuthStore()

    const first = store.refreshSession()
    const second = store.refreshSession()
    expect(authMocks.refresh).toHaveBeenCalledTimes(1)

    resolveRefresh({
      access_token: 'rotated-token',
      token_type: 'bearer',
      expires_in: 900,
      user: adminUser,
    })

    await expect(Promise.all([first, second])).resolves.toEqual([true, true])
    expect(authMocks.refresh).toHaveBeenCalledTimes(1)
    expect(authMocks.getMe).toHaveBeenCalledTimes(1)
  })

  it('clears in-memory authentication when refresh fails', async () => {
    authMocks.refresh.mockRejectedValue(new Error('expired'))
    const store = useAuthStore()

    await expect(store.refreshSession()).resolves.toBe(false)

    expect(store.accessToken).toBeNull()
    expect(store.user).toBeNull()
    expect(store.isAuthenticated).toBe(false)
  })
})
