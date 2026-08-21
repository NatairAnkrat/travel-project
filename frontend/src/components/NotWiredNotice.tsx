import type { ReactNode } from 'react'

/** Marks UI that has no backing endpoint yet. Keep this visible, not a code comment — see docs/openapi/README.md. */
export function NotWiredNotice({ children }: { children: ReactNode }) {
  return (
    <div className="not-wired-notice">
      <strong>Not wired up:</strong> {children}
    </div>
  )
}
