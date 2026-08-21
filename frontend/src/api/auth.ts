import { authApi } from '../lib/apiClient'
import type { AuthResponse, LoginRequest, RegisterRequest } from './types'

export function register(req: RegisterRequest): Promise<{ user_id: string }> {
  return authApi('/api/v1/auth/register', { method: 'POST', body: req })
}

export function login(req: LoginRequest): Promise<AuthResponse> {
  return authApi('/api/v1/auth/login', { method: 'POST', body: req })
}

export function refresh(refreshToken: string): Promise<AuthResponse> {
  return authApi('/api/v1/auth/refresh', { method: 'POST', body: { refresh_token: refreshToken } })
}

export function logout(refreshToken: string): Promise<void> {
  return authApi('/api/v1/auth/logout', { method: 'POST', body: { refresh_token: refreshToken } })
}
