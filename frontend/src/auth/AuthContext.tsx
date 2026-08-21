import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import * as authApi from '../api/auth'
import { setOnRefreshFailed } from '../lib/apiClient'
import { clearTokens, getStoredTokens, storeTokens } from '../lib/tokenStorage'
import type { LoginRequest, RegisterRequest } from '../api/types'

interface AuthContextValue {
  userId: string | null
  isAuthenticated: boolean
  login: (req: LoginRequest) => Promise<void>
  register: (req: RegisterRequest) => Promise<{ user_id: string }>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [userId, setUserId] = useState<string | null>(() => getStoredTokens()?.userId ?? null)

  useEffect(() => {
    setOnRefreshFailed(() => setUserId(null))
  }, [])

  const login = useCallback(async (req: LoginRequest) => {
    const res = await authApi.login(req)
    storeTokens({ accessToken: res.accessToken, refreshToken: res.refreshToken, userId: res.userId })
    setUserId(res.userId)
  }, [])

  const register = useCallback((req: RegisterRequest) => authApi.register(req), [])

  const logout = useCallback(async () => {
    const stored = getStoredTokens()
    if (stored) {
      try {
        await authApi.logout(stored.refreshToken)
      } catch {
        // logout is best-effort client-side regardless of server response
      }
    }
    clearTokens()
    setUserId(null)
  }, [])

  return (
    <AuthContext.Provider value={{ userId, isAuthenticated: userId !== null, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
