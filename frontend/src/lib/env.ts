function requireEnv(key: string): string {
  const value = import.meta.env[key]
  if (!value) {
    throw new Error(`Missing ${key} — copy .env.example to .env and fill in the service URLs`)
  }
  return value
}

export const serviceUrls = {
  auth: requireEnv('VITE_AUTH_SERVICE_URL'),
  group: requireEnv('VITE_GROUP_SERVICE_URL'),
  travel: requireEnv('VITE_TRAVEL_SERVICE_URL'),
} as const
