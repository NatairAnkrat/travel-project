// group-service has no "list my groups" or "get group" endpoint (only
// create/invite/accept/decline/members/leave — see docs/openapi/README.md).
// Until that exists, the only way the frontend can show "your groups" at
// all is to remember group ids locally as the user creates or joins them.
// This is purely a client-side convenience cache, not a source of truth —
// it won't show groups created on another device/browser.

const STORAGE_KEY = 'travel.knownGroups'

export interface KnownGroup {
  id: string
  name: string
}

export function getKnownGroups(): KnownGroup[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]')
  } catch {
    return []
  }
}

export function rememberGroup(group: KnownGroup): void {
  const groups = getKnownGroups().filter((g) => g.id !== group.id)
  groups.push(group)
  localStorage.setItem(STORAGE_KEY, JSON.stringify(groups))
}
