// ============================================================
// Layer 2: Utility barrel export
// ============================================================

export { http, configureHttpClient, type RequestOptions } from './http'
export { consumeStream, type StreamOptions, type StreamEventCallback, type StreamErrorCallback, type StreamDoneCallback } from './ndjson'
export { renderMarkdown, stripMarkdown } from './markdown'
export {
  formatDate,
  formatFileSize,
  documentStatusLabel,
  documentStatusType,
  memoryTypeLabel,
  importancePercent,
  truncate,
} from './format'
export { extractErrorMessage, isNetworkError, isTimeoutError, errorRecoveryHint } from './error'
