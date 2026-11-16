import { createContext, useContext } from 'react'

export type ToastTone = 'success' | 'info' | 'error'

export interface ToastItem {
  id: number
  tone: ToastTone
  message: string
}

type Action = { type: 'add'; toast: ToastItem } | { type: 'dismiss'; id: number }

const MAX_VISIBLE = 4

/** Newest last; the oldest is dropped past `MAX_VISIBLE`. */
export function toastReducer(state: ToastItem[], action: Action): ToastItem[] {
  if (action.type === 'add') return [...state, action.toast].slice(-MAX_VISIBLE)
  return state.filter((t) => t.id !== action.id)
}

export interface ToastApi {
  show: (message: string, tone?: ToastTone) => void
  success: (message: string) => void
  error: (message: string) => void
}

export const ToastContext = createContext<ToastApi | null>(null)

/** Toasts for quick confirmations. Anything the author must act on stays an inline `Notice`. */
export function useToast(): ToastApi {
  const api = useContext(ToastContext)
  if (!api) throw new Error('useToast must be used inside ToastProvider')
  return api
}
