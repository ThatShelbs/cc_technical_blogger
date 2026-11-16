import { CheckCircle2, Info, X, XCircle } from 'lucide-react'
import { useCallback, useEffect, useMemo, useReducer, useRef, type ReactNode } from 'react'

import { cx } from '../lib/cx'
import { ToastContext, toastReducer, type ToastApi, type ToastItem, type ToastTone } from './useToast'

const ICONS = { success: CheckCircle2, info: Info, error: XCircle }
const TONES: Record<ToastTone, string> = {
  success: 'border-success/40',
  info: 'border-line',
  error: 'border-danger/50',
}

function ToastView({ toast, onDismiss }: { toast: ToastItem; onDismiss: (id: number) => void }) {
  useEffect(() => {
    // Errors stay longer: they are harder to read at a glance.
    const timer = window.setTimeout(() => onDismiss(toast.id), toast.tone === 'error' ? 8000 : 4000)
    return () => window.clearTimeout(timer)
  }, [toast, onDismiss])
  const Icon = ICONS[toast.tone]
  return (
    <div
      role={toast.tone === 'error' ? 'alert' : 'status'}
      className={cx('pointer-events-auto flex items-start gap-3 rounded-xl border bg-surface px-4 py-3 text-sm shadow-xl', TONES[toast.tone])}
    >
      <Icon
        className={cx('mt-0.5 size-4 shrink-0', toast.tone === 'success' ? 'text-success' : toast.tone === 'error' ? 'text-danger' : 'text-muted')}
        aria-hidden
      />
      <p className="min-w-0 flex-1">{toast.message}</p>
      <button type="button" onClick={() => onDismiss(toast.id)} className="rounded p-0.5 text-muted hover:text-fg" aria-label="Dismiss notification">
        <X className="size-4" aria-hidden />
      </button>
    </div>
  )
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, dispatch] = useReducer(toastReducer, [])
  const next = useRef(1)
  const dismiss = useCallback((id: number) => dispatch({ type: 'dismiss', id }), [])
  const api = useMemo<ToastApi>(() => {
    const show = (message: string, tone: ToastTone = 'info') => dispatch({ type: 'add', toast: { id: next.current++, tone, message } })
    return { show, success: (m) => show(m, 'success'), error: (m) => show(m, 'error') }
  }, [])
  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="pointer-events-none fixed right-4 bottom-4 z-50 flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2">
        {toasts.map((toast) => (
          <ToastView key={toast.id} toast={toast} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  )
}
