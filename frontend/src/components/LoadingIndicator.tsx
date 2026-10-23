import type { ReactNode } from 'react'

export function LoadingIndicator({ label, children }: { label: string; children: ReactNode }) {
  return <div role="status" aria-label={label}>{children}<span className="sr-only">{label}…</span></div>
}
