import clsx from 'clsx'
import { Building2, Check, KeyRound, Lock, MessageSquareText, RefreshCw, ShieldCheck, Smartphone } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { shortFacility } from '../lib/format'
import { Button, ErrorNote, Modal } from './ui'

interface Target {
  patient_id: string
  full_name: string
  masked_phone: string | null
  external_facilities: string[]
  network_encounters?: number
  external_encounters?: number
}

interface RequestResult {
  request_id: string
  expires_at: string
  delivery: { channel: string; masked_phone: string | null }
  demo_code: string | null
}

export function ConsentFlow({ open, target, onClose, onApproved }: { open: boolean; target: Target | null; onClose: () => void; onApproved: () => void }) {
  const { user } = useAuth()
  const [step, setStep] = useState<'intro' | 'code' | 'done'>('intro')
  const [req, setReq] = useState<RequestResult | null>(null)
  const [digits, setDigits] = useState<string[]>(Array(6).fill(''))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [left, setLeft] = useState(0)
  const [showSms, setShowSms] = useState(false)
  const inputs = useRef<(HTMLInputElement | null)[]>([])

  useEffect(() => {
    if (open) {
      setStep('intro'); setReq(null); setDigits(Array(6).fill('')); setError(null); setShowSms(false)
    }
  }, [open, target?.patient_id])

  useEffect(() => {
    if (!req) return
    const tick = () => setLeft(Math.max(0, Math.round((new Date(req.expires_at).getTime() - Date.now()) / 1000)))
    tick()
    const id = window.setInterval(tick, 1000)
    return () => window.clearInterval(id)
  }, [req])

  // Simulated SMS arrives a moment after sending
  useEffect(() => {
    if (step !== 'code' || !req?.demo_code) return
    const id = window.setTimeout(() => setShowSms(true), 1400)
    return () => window.clearTimeout(id)
  }, [step, req])

  if (!target) return null

  async function send() {
    setBusy(true); setError(null)
    try {
      const r = await api<RequestResult>('/records/access-requests', { method: 'POST', json: { patient_id: target!.patient_id } })
      setReq(r); setDigits(Array(6).fill('')); setShowSms(false); setStep('code')
      window.setTimeout(() => inputs.current[0]?.focus(), 50)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function verify(code = digits.join('')) {
    if (!req || code.length !== 6) return
    setBusy(true); setError(null)
    try {
      await api(`/records/access-requests/${req.request_id}/verify`, { method: 'POST', json: { code } })
      setStep('done')
      window.setTimeout(() => { onApproved() }, 1600)
    } catch (e) {
      setError((e as Error).message)
      setDigits(Array(6).fill(''))
      inputs.current[0]?.focus()
    } finally {
      setBusy(false)
    }
  }

  function setDigit(i: number, v: string) {
    const clean = v.replace(/\D/g, '')
    if (clean.length > 1) {
      const all = clean.slice(0, 6).split('')
      const next = Array(6).fill('').map((_, k) => all[k] ?? '')
      setDigits(next)
      inputs.current[Math.min(5, all.length)]?.focus()
      if (all.length === 6) verify(all.join(''))
      return
    }
    const next = [...digits]
    next[i] = clean
    setDigits(next)
    if (clean && i < 5) inputs.current[i + 1]?.focus()
    if (next.every(Boolean)) verify(next.join(''))
  }

  const facilities = target.external_facilities.map(shortFacility)
  const visits = target.external_encounters ?? target.network_encounters
  const here = shortFacility(user?.facility_name)

  return (
    <Modal open={open} onClose={onClose} width="max-w-xl">
      {step === 'intro' && (
        <div className="p-7">
          <div className="mb-4 grid size-11 place-items-center rounded-md bg-amber-50 text-amber-700">
            <Lock className="size-6" />
          </div>
          <h2 className="text-xl font-semibold text-slate-900">Her records at other hospitals are locked</h2>
          <p className="mt-2 text-base leading-relaxed text-slate-600">
            <b className="text-slate-800">{target.full_name}</b> has{' '}
            {visits ? <b>{visits} previous visit{visits > 1 ? 's' : ''}</b> : 'records'} at{' '}
            {facilities.length} other facilit{facilities.length === 1 ? 'y' : 'ies'}. VITALIS only releases them when the patient approves.
          </p>
          <div className="mt-5 space-y-2">
            {facilities.map((f) => (
              <div key={f} className="flex items-center gap-3 rounded-md border border-slate-200 px-3.5 py-2.5 text-sm">
                <Building2 className="size-4 text-slate-400" />
                <span className="flex-1 font-medium text-slate-700">{f}</span>
                <Lock className="size-3.5 text-slate-400" />
              </div>
            ))}
          </div>
          <div className="mt-5 rounded-md bg-slate-50 p-4 text-sm text-slate-600">
            <div className="flex items-center gap-2 font-semibold text-slate-800"><KeyRound className="size-4 text-brand-600" /> How it works</div>
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">
              <li>A one-time code is sent to the patient’s phone <b>{target.masked_phone}</b></li>
              <li>The patient reads the code to you, which confirms they agree</li>
              <li>{here} gets read access for 24 hours. The patient can revoke it at any time</li>
            </ol>
          </div>
          <ErrorNote message={error} />
          <div className="mt-6 flex justify-end gap-2">
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button onClick={send} loading={busy} icon={<Smartphone className="size-4" />}>Send one-time code</Button>
          </div>
        </div>
      )}

      {step === 'code' && req && (
        <div className="p-7">
          <div className="mb-4 grid size-11 place-items-center rounded-md bg-brand-50 text-brand-700">
            <Smartphone className="size-6" />
          </div>
          <h2 className="text-xl font-semibold text-slate-900">Enter the code from the patient’s phone</h2>
          <p className="mt-2 text-sm text-slate-600">
            Code sent by {req.delivery.channel} to <b className="text-slate-800">{req.delivery.masked_phone}</b>. Ask the patient to read it out.
          </p>
          <div className="mt-6 flex justify-center gap-2">
            {digits.map((d, i) => (
              <input
                key={i}
                ref={(el) => { inputs.current[i] = el }}
                value={d}
                inputMode="numeric"
                maxLength={6}
                onChange={(e) => setDigit(i, e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Backspace' && !digits[i] && i > 0) inputs.current[i - 1]?.focus() }}
                className={clsx(
                  'h-14 w-11 rounded-md border-2 text-center font-mono text-2xl font-semibold text-slate-900 outline-none transition-colors sm:w-12',
                  d ? 'border-brand-500 bg-brand-50/40' : 'border-slate-200 focus:border-brand-500',
                  error && 'border-rose-300',
                )}
              />
            ))}
          </div>
          <div className="mt-3 flex items-center justify-center gap-3 text-xs text-slate-500">
            <span>Expires in <b className="font-mono text-slate-700">{Math.floor(left / 60)}:{String(left % 60).padStart(2, '0')}</b></span>
            <span className="text-slate-300">•</span>
            <button onClick={send} className="inline-flex items-center gap-1 font-semibold text-brand-700 hover:underline"><RefreshCw className="size-3" /> Resend</button>
          </div>
          <div className="mt-4"><ErrorNote message={error} /></div>

          {req.demo_code && (
            <div className={clsx('mt-6 transition-all duration-500', showSms ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2 pointer-events-none')}>
              <div className="mb-2 text-xs font-semibold text-slate-500">Demo: the SMS the patient receives</div>
              <div className="flex gap-3 rounded-lg bg-slate-900 p-4 text-white">
                <div className="grid size-9 shrink-0 place-items-center rounded-md bg-brand-600"><MessageSquareText className="size-5" /></div>
                <div className="text-sm leading-relaxed">
                  <div className="text-xs font-semibold text-brand-200">VITALIS · now</div>
                  {here} is requesting access to your health record. Your code is{' '}
                  <button onClick={() => setDigit(0, req.demo_code!)} className="rounded bg-white/15 px-1.5 font-mono font-bold tracking-widest hover:bg-white/25" title="Click to fill">
                    {req.demo_code}
                  </button>
                  . Expires in 10 min. Only share it if you are at the facility.
                </div>
              </div>
            </div>
          )}

          <div className="mt-6 flex justify-end gap-2">
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button onClick={() => verify()} loading={busy} disabled={digits.join('').length !== 6} icon={<ShieldCheck className="size-4" />}>Verify & unlock</Button>
          </div>
        </div>
      )}

      {step === 'done' && (
        <div className="p-10 text-center">
          <div className="mx-auto mb-4 grid size-14 place-items-center rounded-full bg-brand-700 text-white">
            <Check className="size-8" strokeWidth={3} />
          </div>
          <h2 className="text-xl font-semibold text-slate-900">The patient approved access</h2>
          <p className="mt-2 text-sm text-slate-600">
            Records from {facilities.join(' and ')} are now available to {here} for 24 hours.
            This access has been logged and the patient can see it.
          </p>
        </div>
      )}
    </Modal>
  )
}
