export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

type Body = FormData | object | undefined

async function request<T>(method: string, path: string, body?: Body): Promise<T> {
  const isForm = body instanceof FormData
  const response = await fetch(path, {
    method,
    headers: body !== undefined && !isForm ? { 'Content-Type': 'application/json' } : undefined,
    body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
  })
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response))
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const data = await response.json()
    if (typeof data.detail === 'string') return data.detail
    if (Array.isArray(data.detail)) {
      return data.detail.map((d: { msg?: string }) => d.msg ?? 'Invalid value').join('; ')
    }
  } catch {
    // Non-JSON error body; fall through to the status text.
  }
  return response.statusText || `Request failed (${response.status})`
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: Body) => request<T>('POST', path, body ?? {}),
  put: <T>(path: string, body?: Body) => request<T>('PUT', path, body ?? {}),
  patch: <T>(path: string, body?: Body) => request<T>('PATCH', path, body ?? {}),
  del: <T>(path: string) => request<T>('DELETE', path),
}

export function errorText(error: unknown): string {
  if (error instanceof Error) return error.message
  return String(error)
}
