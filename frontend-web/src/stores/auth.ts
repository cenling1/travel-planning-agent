// ============================================================
// Layer 4: Store — Auth
// Access Token in memory only, Refresh Token via secure Cookie
// Single refresh lock to prevent concurrent refresh requests
// ============================================================

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User, LoginRequest, RegisterRequest, ChangePasswordRequest } from '@/types/auth'
import { authApi } from '@/api/auth'
import { configureHttpClient } from '@/utils/http'
import { configureStreamAuth } from '@/api/chat'
import { extractErrorMessage } from '@/utils/error'

export const useAuthStore = defineStore('auth', () => {
  // ---- State ----
  const user = ref<User | null>(null)
  const accessToken = ref<string | null>(null)
  const isRestoring = ref(false)
  const restoreAttempted = ref(false)
  const loginError = ref<string | null>(null)
  const isLoginLoading = ref(false)

  // Refresh lock: ensures only one refresh runs at a time
  let refreshLock: Promise<boolean> | null = null

  // ---- Getters ----
  const isAuthenticated = computed(() => !!accessToken.value && !!user.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  // ---- Actions ----
  function setSession(access: string | null, currentUser: User | null) {
    accessToken.value = access
    user.value = currentUser
  }

  async function login(payload: LoginRequest): Promise<boolean> {
    isLoginLoading.value = true
    loginError.value = null
    try {
      const result = await authApi.login(payload)
      setSession(result.access_token, result.user)
      return true
    } catch (err) {
      loginError.value = extractErrorMessage(err, '登录失败')
      return false
    } finally {
      isLoginLoading.value = false
    }
  }

  async function register(payload: RegisterRequest): Promise<boolean> {
    isLoginLoading.value = true
    loginError.value = null
    try {
      const result = await authApi.register(payload)
      setSession(result.access_token, result.user)
      return true
    } catch (err) {
      loginError.value = extractErrorMessage(err, '注册失败')
      return false
    } finally {
      isLoginLoading.value = false
    }
  }

  /**
   * Refresh the current session using the refresh token.
   * Protected by a single lock — concurrent callers wait for the same result.
   */
  async function refreshSession(): Promise<boolean> {
    // If there's already a refresh in progress, wait for it
    if (refreshLock) return refreshLock

    refreshLock = (async () => {
      try {
        const result = await authApi.refresh()
        accessToken.value = result.access_token
        user.value = await authApi.getMe()
        return true
      } catch {
        clearAuth()
        return false
      } finally {
        refreshLock = null
      }
    })()

    return refreshLock
  }

  /**
   * Try to restore session from existing tokens (e.g., on page load).
   */
  async function restoreSession(): Promise<boolean> {
    isRestoring.value = true
    restoreAttempted.value = true
    try {
      return await refreshSession()
    } catch {
      clearAuth()
      return false
    } finally {
      isRestoring.value = false
    }
  }

  async function logout(): Promise<void> {
    try {
      await authApi.logout()
    } finally {
      clearAuth()
    }
  }

  async function logoutAll(): Promise<void> {
    try {
      await authApi.logoutAll()
    } finally {
      clearAuth()
    }
  }

  async function changePassword(payload: ChangePasswordRequest): Promise<boolean> {
    try {
      await authApi.changePassword(payload)
      clearAuth()
      return true
    } catch {
      return false
    }
  }

  function clearAuth() {
    user.value = null
    accessToken.value = null
    loginError.value = null
  }

  // ---- Init ----
  // Wire up the HTTP client so it can auto-refresh and get tokens
  configureHttpClient({
    getAccessToken: () => accessToken.value,
    onUnauthorized: () => refreshSession(),
    clearAuth: () => clearAuth(),
    onAuthExpired: () => window.dispatchEvent(new CustomEvent('auth:expired')),
  })
  configureStreamAuth({
    getAccessToken: () => accessToken.value,
    refresh: () => refreshSession(),
    expired: () => {
      clearAuth()
      window.dispatchEvent(new CustomEvent('auth:expired'))
    },
  })

  return {
    // State
    user,
    accessToken,
    isRestoring,
    restoreAttempted,
    loginError,
    isLoginLoading,
    // Getters
    isAuthenticated,
    isAdmin,
    // Actions
    login,
    register,
    refreshSession,
    restoreSession,
    logout,
    logoutAll,
    changePassword,
    clearAuth,
  }
})
