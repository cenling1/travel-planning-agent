// ---- System / Health ----

export interface HealthResponse {
  status: string
  database: string
  embedding_provider: string
  auth_enabled: boolean
  registration_enabled: boolean
  max_upload_bytes: number
}

export interface ToolHealth {
  configured: Record<string, boolean>
}

// ---- Generic API ----

export interface ApiErrorResponse {
  detail: string
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public detail: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}
