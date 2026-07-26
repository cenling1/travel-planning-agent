// ============================================================
// Layer 4: Store — System
// Manages health status, tool availability, global notifications
// ============================================================

import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { HealthResponse } from '@/types/system'
import { healthApi } from '@/api/health'

export const useSystemStore = defineStore('system', () => {
  // ---- State ----
  const health = ref<HealthResponse | null>(null)
  const toolHealth = ref<Record<string, boolean> | null>(null)
  const isCheckingHealth = ref(false)
  const healthError = ref<string | null>(null)

  // ---- Actions ----
  async function checkHealth(): Promise<void> {
    isCheckingHealth.value = true
    healthError.value = null
    try {
      health.value = await healthApi.check()
    } catch {
      health.value = null
      healthError.value = '无法连接到服务器'
    } finally {
      isCheckingHealth.value = false
    }
  }

  async function checkTools(): Promise<void> {
    try {
      const result = await healthApi.checkTools()
      toolHealth.value = result.configured
    } catch {
      toolHealth.value = null
    }
  }

  // Start periodic health check
  let healthTimer: ReturnType<typeof setInterval> | null = null

  function startHealthPolling(intervalMs = 30000) {
    checkHealth()
    if (healthTimer) clearInterval(healthTimer)
    healthTimer = setInterval(checkHealth, intervalMs)
  }

  function stopHealthPolling() {
    if (healthTimer) {
      clearInterval(healthTimer)
      healthTimer = null
    }
  }

  return {
    health,
    toolHealth,
    isCheckingHealth,
    healthError,
    checkHealth,
    checkTools,
    startHealthPolling,
    stopHealthPolling,
  }
})
