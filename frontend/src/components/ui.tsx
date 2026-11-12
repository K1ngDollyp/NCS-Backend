import clsx from 'clsx'
import { CheckCircle2, Info, Loader2, X, XCircle } from 'lucide-react'
import { createContext, useCallback, useContext, useEffect, useState, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import { STATUS_LABEL } from '../lib/format'

/* ------------------------------------------------------------------ Button
   primary   → the one main action on a screen (brand green)
   secondary → supporting actions
   ghost     → low-emphasis / tertiary
   danger    → destructive
   ai        → runs or acts on machine-generated content (indigo)          */
type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'ai' | 'outline'
const VARIANTS: Record<Variant, string> = {
  primary: 'bg-brand-700 text-white hover:bg-brand-800',
  secondary: 'bg-white text-slate-800 border border-slate-300 hover:bg-slate-50',
  outline: 'bg-white text-brand-800 border border-brand-300 hover:bg-brand-50',
  ghost: 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
  danger: 'bg-rose-700 text-white hover:bg-rose-800',
  ai: 'bg-ai-600 text-white hover:bg-ai-700',
}

export function Button({
  variant = 'primary', size = 'md', loading, icon, children, className, disabled, ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: 'sm' | 'md' | 'lg'; loading?: boolean; icon?: ReactNode }) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={clsx(
        'inline-flex items-center justify-center gap-2 rounded-md font-semibold transition-colors duration-150 disabled:pointer-events-none disabled:opacity-50 whitespace-nowrap',
        size === 'sm' && 'h-8 px-3 text-sm',
        size === 'md' && 'h-10 px-4 text-sm',
        size === 'lg' && 'h-12 px-5 text-base',
        VARIANTS[variant],
        className,
      )}
    >
      {loading ? <Loader2 className="size-4 animate-spin" /> : icon}
      {children}
    </button>
  )
}

/* ------------------------------------------------------------------ Surfaces */
export function Card({ children, className, ...rest }: { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div {...rest} className={clsx('rounded-lg border border-slate-200 bg-white', className)}>
      {children}
    </div>
  )
}

export function CardHeader({ title, subtitle, icon, action, className }: { title: ReactNode; subtitle?: ReactNode; icon?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={clsx('flex flex-wrap items-start justify-between gap-x-4 gap-y-2 px-5 pt-4 pb-3', className)}>
      <div className="flex min-w-0 items-start gap-2.5">
        {icon && <span className="mt-0.5 shrink-0 text-slate-400 [&>svg]:size-[18px]">{icon}</span>}
        <div className="min-w-0">
          <h3 className="text-base font-semibold text-slate-900">{title}</h3>
          {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
        </div>
      </div>
      {action}
    </div>
  )
}

/* ------------------------------------------------------------------ Badges */
type Tone = 'slate' | 'brand' | 'amber' | 'rose' | 'sky' | 'ai' | 'emerald'
const TONES: Record<Tone, string> = {
  slate: 'bg-slate-100 text-slate-700 ring-slate-200',
  brand: 'bg-brand-50 text-brand-800 ring-brand-200',
  emerald: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  amber: 'bg-amber-50 text-amber-800 ring-amber-200',
  rose: 'bg-rose-50 text-rose-700 ring-rose-200',
  sky: 'bg-sky-50 text-sky-700 ring-sky-200',
  ai: 'bg-ai-50 text-ai-700 ring-ai-200',
}
export function Badge({ tone = 'slate', children, className, icon }: { tone?: Tone; children: ReactNode; className?: string; icon?: ReactNode }) {
  return (
    <span className={clsx('inline-flex h-6 items-center gap-1 rounded-md px-2 text-xs font-semibold ring-1 ring-inset whitespace-nowrap [&>svg]:size-3.5', TONES[tone], className)}>
      {icon}
      {children}
    </span>
  )
}

export function PriorityBadge({ priority }: { priority: string }) {
  if (priority === 'emergency') return <Badge tone="rose">Emergency</Badge>
  if (priority === 'urgent') return <Badge tone="amber">Urgent</Badge>
  return <span className="text-xs font-medium text-slate-400">Routine</span>
}

export function StatusBadge({ status }: { status: string }) {
  const tone: Tone =
    status === 'completed' || status === 'verified' ? 'emerald'
      : status === 'results_ready' ? 'brand'
        : status === 'result_entered' ? 'amber'
          : status === 'rejected' || status === 'cancelled' ? 'rose'
            : 'sky'
  return <Badge tone={tone}>{STATUS_LABEL[status] ?? status}</Badge>
}

/* ------------------------------------------------------------------ Form */
export function Field({ label, hint, children, className }: { label: string; hint?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <label className={clsx('block', className)}>
      <span className="mb-1.5 block text-sm font-medium text-slate-700">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
    </label>
  )
}

const inputCls = 'w-full rounded-md border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900 placeholder:text-slate-400 outline-none transition-colors duration-150 focus:border-brand-600 focus:ring-3 focus:ring-brand-600/15'

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...rest} className={clsx(inputCls, 'h-11', className)} />
}
export function Textarea({ className, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...rest} className={clsx(inputCls, 'min-h-[88px] resize-y', className)} />
}
export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...rest} className={clsx(inputCls, 'h-11 pr-8', className)}>{children}</select>
}

/* ------------------------------------------------------------------ Feedback */
export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={clsx('animate-spin text-brand-600', className ?? 'size-5')} />
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('skeleton', className ?? 'h-4 w-full')} />
}

/** Placeholder rows shaped like a list while data loads (no layout jump). */
export function SkeletonList({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3 p-4" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="space-y-2 rounded-md border border-slate-100 p-3">
          <Skeleton className="h-4 w-2/5" />
          <Skeleton className="h-3.5 w-4/5" />
        </div>
      ))}
    </div>
  )
}

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-sm text-slate-500" role="status">
      <Spinner /> {label}
    </div>
  )
}

export function EmptyState({ icon, title, description, action }: { icon: ReactNode; title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-10 text-center">
      <div className="mb-3 text-slate-300 [&>svg]:size-8">{icon}</div>
      <p className="font-semibold text-slate-800">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-slate-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <div role="alert" className="flex items-start gap-2 rounded-md border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-800">
      <XCircle className="mt-0.5 size-4 shrink-0" />
      {message}
    </div>
  )
}

export function Avatar({ name, className }: { name: string; className?: string }) {
  const letters = name.replace(/^(Dr\.|Nurse|Mrs?\.?)\s+/i, '').split(/\s+/).slice(0, 2).map((p) => p[0]).join('').toUpperCase()
  return (
    <div className={clsx('grid shrink-0 place-items-center rounded-full bg-slate-100 font-semibold text-slate-700', className ?? 'size-10 text-sm')}>
      {letters}
    </div>
  )
}

export function Modal({ open, onClose, children, width = 'max-w-lg', label }: { open: boolean; onClose: () => void; children: ReactNode; width?: string; label?: string }) {
  useEffect(() => {
    if (!open) return
    const h = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={label}>
      <div className="absolute inset-0 bg-slate-900/45 animate-fade-in" onClick={onClose} />
      <div className={clsx('relative max-h-[92vh] w-full overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-2xl animate-slide-up', width)}>
        <button onClick={onClose} aria-label="Close" className="absolute right-3 top-3 z-10 grid size-9 place-items-center rounded-md text-slate-400 hover:bg-slate-100 hover:text-slate-700">
          <X className="size-5" />
        </button>
        {children}
      </div>
    </div>
  )
}

export function PageHeader({ title, subtitle, action, eyebrow }: { title: ReactNode; subtitle?: ReactNode; action?: ReactNode; eyebrow?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && <div className="mb-1 text-sm font-medium text-brand-700">{eyebrow}</div>}
        <h1 className="text-2xl font-semibold text-slate-900 sm:text-3xl">{title}</h1>
        {subtitle && <p className="mt-1.5 max-w-2xl text-base text-slate-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

/** Compact KPI: number first, label second. No decorative icon tiles. */
export function Stat({ label, value, tone }: { label: string; value: ReactNode; tone?: 'rose' | 'amber' }) {
  return (
    <div className="px-4 py-3">
      <div className={clsx('text-2xl font-semibold tabular', tone === 'rose' ? 'text-rose-700' : tone === 'amber' ? 'text-amber-700' : 'text-slate-900')}>{value}</div>
      <div className="text-sm text-slate-500">{label}</div>
    </div>
  )
}

/* ------------------------------------------------------------------ Toasts */
interface Toast { id: number; title: string; description?: string; tone: 'success' | 'error' | 'info' }
const ToastCtx = createContext<(t: Omit<Toast, 'id'>) => void>(() => {})

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const push = useCallback((t: Omit<Toast, 'id'>) => {
    const id = Date.now() + Math.random()
    setToasts((all) => [...all, { ...t, id }])
    window.setTimeout(() => setToasts((all) => all.filter((x) => x.id !== id)), 4200)
  }, [])
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed inset-x-4 bottom-4 z-[60] flex flex-col items-end gap-2 sm:left-auto sm:w-96" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className="pointer-events-auto flex w-full gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-xl animate-slide-up">
            {t.tone === 'success' && <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-emerald-600" />}
            {t.tone === 'error' && <XCircle className="mt-0.5 size-5 shrink-0 text-rose-600" />}
            {t.tone === 'info' && <Info className="mt-0.5 size-5 shrink-0 text-sky-600" />}
            <div>
              <div className="text-sm font-semibold text-slate-900">{t.title}</div>
              {t.description && <div className="mt-0.5 text-sm text-slate-500">{t.description}</div>}
            </div>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useToast() {
  return useContext(ToastCtx)
}
