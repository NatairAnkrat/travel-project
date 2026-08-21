import { serviceUrls } from './env'
import { clearTokens, getStoredTokens, storeTokens } from './tokenStorage'

export class ApiError extends Error {
  status: number
  body: unknown

  constructor(status: number, body: unknown) {
    super(`API error ${status}`)
    this.status = status
    this.body = body
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
  /**
   * Attach the stored access token and, on a 401, refresh once and retry.
   * auth-service's own endpoints (login/register/refresh/logout) don't take
   * this — there's nothing to attach yet and a 401 there means "bad
   * credentials", not "expired token".
   */
  authenticated?: boolean
}

// Set by AuthContext so the client can force a logout when a refresh
// attempt itself fails (refresh token expired/revoked) — kept as a plain
// module-level hook rather than threading React state through here since
// this file has no React dependency otherwise.
let onRefreshFailed: (() => void) | null = null
export function setOnRefreshFailed(handler: () => void): void {
  onRefreshFailed = handler
}

let refreshPromise: Promise<string> | null = null

async function refreshAccessToken(): Promise<string> {
  if (refreshPromise) return refreshPromise

  refreshPromise = (async () => {
    const stored = getStoredTokens()
    if (!stored) throw new Error('no refresh token available')

    const res = await fetch(`${serviceUrls.auth}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: stored.refreshToken }),
    })
    if (!res.ok) {
      clearTokens()
      onRefreshFailed?.()
      throw new Error('refresh failed')
    }
    const data = await res.json()
    storeTokens({ accessToken: data.accessToken, refreshToken: data.refreshToken, userId: data.userId })
    return data.accessToken as string
  })()

  try {
    return await refreshPromise
  } finally {
    refreshPromise = null
  }
}

async function doFetch(url: string, init: RequestInit): Promise<Response> {
  return fetch(url, init)
}

export async function apiRequest<T>(
  baseUrl: string,
  path: string,
  { method = 'GET', body, authenticated = true }: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }

  if (authenticated) {
    const stored = getStoredTokens()
    if (stored) headers.Authorization = `Bearer ${stored.accessToken}`
  }

  const init: RequestInit = { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined }
  let res = await doFetch(`${baseUrl}${path}`, init)

  if (authenticated && res.status === 401) {
    try {
      const newAccessToken = await refreshAccessToken()
      headers.Authorization = `Bearer ${newAccessToken}`
      res = await doFetch(`${baseUrl}${path}`, { ...init, headers })
    } catch {
      throw new ApiError(401, null)
    }
  }

  if (!res.ok) {
    const contentType = res.headers.get('content-type') ?? ''
    const errorBody = contentType.includes('application/json') ? await res.json().catch(() => null) : await res.text()
    throw new ApiError(res.status, errorBody)
  }

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const authApi = <T>(path: string, opts?: RequestOptions) =>
  apiRequest<T>(serviceUrls.auth, path, { ...opts, authenticated: false })
export const groupApi = <T>(path: string, opts?: RequestOptions) => apiRequest<T>(serviceUrls.group, path, opts)
export const travelApi = <T>(path: string, opts?: RequestOptions) => apiRequest<T>(serviceUrls.travel, path, opts)
