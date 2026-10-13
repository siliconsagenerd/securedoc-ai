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
  filename?: string
  sanitized_preview: string
  pii: PIIResult
  llm_output: string
  audit_event_id: string
  latency_ms: number
}

export interface BlockedResult {
  message: string
  reasons: string[]
  categories?: string[]
  score?: number
  risk_level: string
  audit_event_id: string
}

/**
 * All requests go to the same origin (relative paths). A server-side proxy
 * (nginx in Docker, Vite's dev proxy locally) forwards them to the backend and
 * injects the X-API-Key header. The key is never part of the frontend bundle.
 */
const API_BASE = ''

/** Thrown when the backend guard blocks a request (HTTP 400). */
export class BlockedError extends Error {
  constructor(public readonly data: BlockedResult) {
    super(data.message)
    this.name = 'BlockedError'
  }
}

/** Thrown when authentication fails (HTTP 401, e.g. proxy key misconfigured). */
export class UnauthorizedError extends Error {
  constructor(message = 'Unauthorized — the API proxy is not configured') {
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

async function parseResult(res: Response): Promise<ProcessResult> {
  const data = await res.json().catch(() => null)

  if (res.status === 401) {
    throw new UnauthorizedError(typeof data?.detail === 'string' ? data.detail : undefined)
  }
  if (res.status === 429) {
    const retry = res.headers.get('Retry-After')
    throw new ApiError(
      `Rate limit reached${retry ? ` — retry in ${retry}s` : ''}`,
      res.status,
    )
  }
  if (res.status === 400 && data) {
    if (Array.isArray(data.reasons)) throw new BlockedError(data as BlockedResult)
    throw new ApiError(typeof data.message === 'string' ? data.message : 'File rejected', res.status)
  }
  if (!res.ok) {
    const message = (data && (data.message || data.detail)) || `Request failed (${res.status})`
    throw new ApiError(typeof message === 'string' ? message : `Request failed (${res.status})`, res.status)
  }
  return data as ProcessResult
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/version`)
    return res.ok
  } catch {
    return false
  }
}

export async function processDocument(text: string, task: Task): Promise<ProcessResult> {
  const res = await fetch(`${API_BASE}/api/process-document`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, task }),
  })
  return parseResult(res)
}

export async function uploadDocument(file: File, task: Task): Promise<ProcessResult> {
  const form = new FormData()
  form.append('file', file)
  form.append('task', task)

  const res = await fetch(`${API_BASE}/api/upload-document`, {
    method: 'POST',
    body: form,
  })
  return parseResult(res)
}
