// auth-service issues a JWT access token + a rotating refresh token
// (docs/openapi/auth-service.yaml). Refresh rotates on every use, so
// whatever this module holds must always be overwritten with the newest
// pair returned by /auth/refresh or /auth/login.

const ACCESS_TOKEN_KEY = 'travel.accessToken'
const REFRESH_TOKEN_KEY = 'travel.refreshToken'
const USER_ID_KEY = 'travel.userId'

export interface TokenPair {
  accessToken: string
  refreshToken: string
  userId: string
}

export function getStoredTokens(): TokenPair | null {
  const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY)
  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY)
  const userId = localStorage.getItem(USER_ID_KEY)
  if (!accessToken || !refreshToken || !userId) return null
  return { accessToken, refreshToken, userId }
}

export function storeTokens(tokens: TokenPair): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.accessToken)
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken)
  localStorage.setItem(USER_ID_KEY, tokens.userId)
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
  localStorage.removeItem(USER_ID_KEY)
}
