// ============================================================
// Layer 3: API — Health module
// ============================================================

import { http } from '@/utils/http'
import type { HealthResponse, ToolHealth } from '@/types/system'

export const healthApi = {
  check(): Promise<HealthResponse> {
    return http.get<HealthResponse>('/health', { authenticated: false })
  },

  checkTools(): Promise<ToolHealth> {
    return http.get<ToolHealth>('/health/tools')
  },
}
