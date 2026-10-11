export type Task = 'summarize' | 'extract_fields' | 'classify_document'

export interface EntityMetadata {
  entity_type: string
  placeholder: string
  start: number
  end: number
}

export interface PIIResult {
  entity_count: number
  entity_types: string[]
  entities: EntityMetadata[]
}

export interface ProcessResult {
  task: Task
  sanitized_preview: string
  pii: PIIResult
  llm_output: string
  audit_event_id: string
  latency_ms: number
}

export interface BlockedResult {
  message: string
  reasons: string[]
  risk_level: string
  audit_event_id: string
}

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
const API_KEY = import.meta.env.VITE_API_KEY ?? ''

/**
 * Shortcut: the API key is compiled into the bundle, so it is visible to anyone
 * who loads the page. Fine for a local demo; a real deployment must keep the key
 * server-side (reverse proxy or session auth), upgrade before exposing publicly.
 */
function authHeaders(): Record<string, string> {
  return API_KEY ? { 'X-API-Key': API_KEY } : {}
}

/** Thrown when the backend guard blocks a request (HTTP 400). */
export class BlockedError extends Error {
  constructor(public readonly data: BlockedResult) {
    super(data.message)
    this.name = 'BlockedError'
  }
}

/** Thrown when the API key is missing or invalid (HTTP 401). */
export class UnauthorizedError extends Error {
  constructor(message = 'Unauthorized — check VITE_API_KEY') {
    super(message)
    this.name = 'UnauthorizedError'
  }
}

/** Thrown for any other non-success response. */
export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message)
    this.name = 'ApiError'
  }
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/health`)
    return res.ok
  } catch {
    return false
  }
}

export async function processDocument(text: string, task: Task): Promise<ProcessResult> {
  const res = await fetch(`${BASE_URL}/api/process-document`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ text, task }),
  })

  const data = await res.json().catch(() => null)

  if (res.status === 401) {
    throw new UnauthorizedError(typeof data?.detail === 'string' ? data.detail : undefined)
  }
  if (res.status === 400 && data) {
    throw new BlockedError(data as BlockedResult)
  }
  if (!res.ok) {
    const message = (data && (data.message || data.detail)) || `Request failed (${res.status})`
    throw new ApiError(typeof message === 'string' ? message : `Request failed (${res.status})`, res.status)
  }
  return data as ProcessResult
}
