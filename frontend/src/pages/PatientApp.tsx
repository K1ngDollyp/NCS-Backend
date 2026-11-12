import clsx from 'clsx'
import { AlertTriangle, BellRing, ChevronRight, Eye, KeyRound, LogOut, Phone, QrCode, ShieldCheck, ShieldOff, Stethoscope, X } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CareConnect } from '../components/CareConnect'
import { FacilityChip, LabFlagValue } from '../components/clinical'
import { Logo } from '../components/Layout'
import { SkeletonList, useToast } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { fmtDate, fmtDateTime, shortFacility, timeAgo } from '../lib/format'
import { useResource } from '../lib/hooks'
import type { Facility, PatientProfile, Referral, UnifiedRecord } from '../lib/types'

interface PendingRequest { request_id: string; facility_name: string; requested_by: string; purpose: string; code: string | null; expires_at: string }
interface AccessLog {
  consents: { id: string; facility_name: string; purpose: string; created_at: string; expires_at: string; revoked_at: string | null; active: boolean }[]
  events: { id: string; action: string; timestamp: string; actor: string | null; actor_role: string | null; facility_name: string | null }[]
}

const ACTION_TEXT: Record<string, string> = {
  NETWORK_RECORD_VIEWED: 'viewed your record',
  NETWORK_ACCESS_GRANTED: 'was given access with your code',
  NETWORK_ACCESS_REQUESTED: 'asked to see your record',
  ENCOUNTER_OPENED: 'started a visit for you',
  VITALS_RECORDED: 'recorded your vital signs',
  CLINICAL_NOTE_SIGNED: 'signed a clinical note',
  INTELLIGENCE_ASSESSMENT_GENERATED: 'used VITALIS AI on your record',
  CONSENT_REVOKED: 'lost access (you revoked it)',
}

/** Merge consecutive identical events (same person, same action) so the log stays readable. */
function collapse(events: AccessLog['events']) {
  const out: (AccessLog['events'][number] & { count: number })[] = []
  for (const ev of events) {
    const last = out[out.length - 1]
    if (last && last.actor === ev.actor && last.action === ev.action) last.count += 1
    else out.push({ ...ev, count: 1 })
  }
  return out
}

export default function PatientApp() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()
  const me = useResource<PatientProfile>('/patients/me')
  const rec = useResource<UnifiedRecord>(me.data ? `/records/patients/${me.data.id}` : null, { poll: 8000 })
  const pending = useResource<PendingRequest[]>('/records/me/access-requests', { poll: 2000 })
  const log = useResource<AccessLog>('/records/me/access-log', { poll: 5000 })
  const [tab, setTab] = useState<'visits' | 'results' | 'access'>('visits')
  const [qr, setQr] = useState<string | null>(null)
  const referrals = useResource<Referral[]>('/referrals/me', { poll: 4000 })
  const facilities = useResource<Facility[]>('/facilities')
  const [care, setCare] = useState<null | 'new' | Referral>(null)

  async function showQr() {
    if (!me.data) return
    const g = await api<{ qr_code_base64: string }>('/connect/qr-grants', { method: 'POST', json: { patient_id: me.data.id, duration_minutes: 10 } })
    setQr(g.qr_code_base64)
  }

  async function revoke(id: string) {
    await api(`/connect/consents/${id}`, { method: 'DELETE' })
    toast({ tone: 'success', title: 'Access removed', description: 'That hospital can no longer see your records from other hospitals.' })
    log.reload(true)
  }

  const req = pending.data?.[0]
  const active = log.data?.consents.filter((c) => c.active) ?? []
  const openReferral = referrals.data?.find((r) => r.status === 'pending' || r.status === 'accepted' || r.status === 'more_information')
  const facilityName = (id: string) => shortFacility(facilities.data?.find((f) => f.id === id)?.name)

  return (
    <div className="min-h-full bg-slate-100 sm:py-8">
      <div className="mx-auto min-h-screen max-w-[420px] overflow-hidden bg-slate-50 sm:min-h-[860px] sm:rounded-[40px] sm:border-[10px] sm:border-slate-900 sm:shadow-2xl">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-4">
          <Logo />
          <button onClick={() => { logout(); navigate('/login') }} aria-label="Sign out" className="grid size-10 place-items-center rounded-md text-slate-500 hover:bg-slate-100"><LogOut className="size-5" /></button>
        </header>

        {care && me.data ? (
          <CareConnect patient={me.data} initialReferral={care === 'new' ? null : care} onExit={() => { setCare(null); referrals.reload(true); log.reload(true) }} />
        ) : (
        <div className="space-y-4 px-4 py-5">
          <div>
            <div className="text-sm text-slate-500">Welcome back</div>
            <div className="text-2xl font-semibold text-slate-900">{user?.full_name}</div>
          </div>

          {/* CareConnect: an open referral takes priority over starting a new check */}
          {openReferral ? (
            <button onClick={() => setCare(openReferral)} className={clsx('block w-full rounded-lg border border-l-4 bg-white p-4 text-left animate-slide-up', openReferral.status === 'accepted' ? 'border-brand-200 border-l-brand-600' : 'border-sky-200 border-l-sky-600')}>
              <div className="text-sm text-slate-500">Your referral to {facilityName(openReferral.destination_facility_id)}</div>
              <div className="mt-0.5 flex items-center justify-between gap-2 text-base font-semibold text-slate-900">
                {openReferral.status === 'accepted' ? 'Confirmed: go to reception today' : openReferral.status === 'pending' ? 'Waiting for the hospital to confirm' : 'The hospital needs more information'}
                <ChevronRight className="size-5 shrink-0 text-slate-400" />
              </div>
            </button>
          ) : me.data && (
            <section className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="text-base font-semibold text-slate-900">Feeling unwell?</div>
              <p className="mt-1 text-sm text-slate-600">Check your symptoms, then find a hospital that can actually treat you, before you travel.</p>
              <button onClick={() => setCare('new')} className="mt-3 flex h-12 w-full items-center justify-center gap-2 rounded-md bg-brand-700 text-base font-semibold text-white hover:bg-brand-800">
                <Stethoscope className="size-5" />Check my symptoms
              </button>
              <a href="tel:112" className="mt-2 flex h-11 w-full items-center justify-center gap-2 rounded-md border border-rose-200 text-sm font-semibold text-rose-700 hover:bg-rose-50">
                <Phone className="size-4" />Emergency? Call 112
              </a>
            </section>
          )}

          {/* Live access request */}
          {req && (
            <section className="rounded-lg border border-amber-300 border-l-4 border-l-amber-500 bg-white p-4 animate-slide-up" aria-live="assertive">
              <div className="flex items-center gap-2 text-base font-semibold text-amber-800"><BellRing className="size-5" />A hospital is asking for your records</div>
              <p className="mt-2 text-base text-slate-700">
                <b>{shortFacility(req.facility_name)}</b> ({req.requested_by?.replace(/\s*\(.*\)$/, '')}) wants to see your records from other hospitals.
              </p>
              <div className="mt-4 rounded-md bg-slate-900 py-4 text-center text-white">
                <div className="text-sm text-slate-300">Your one-time code</div>
                <div className="mt-1 font-mono text-4xl font-semibold tracking-[0.25em]">{req.code}</div>
              </div>
              <p className="mt-3 text-sm text-slate-600">If you agree, read this code to the staff member. Only do this if you are at {shortFacility(req.facility_name)}. It expires at {fmtDateTime(req.expires_at).split(' · ')[1]}.</p>
            </section>
          )}

          {/* Health ID card */}
          {me.loading && !me.data ? <SkeletonList rows={1} /> : me.data && (
            <section className="rounded-lg bg-brand-800 p-5 text-white">
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-sm text-brand-100">VITALIS health ID</div>
                  <div className="mt-0.5 font-mono text-2xl font-semibold tracking-wide">{me.data.patient_number}</div>
                </div>
                <button onClick={showQr} className="flex h-10 items-center gap-1.5 rounded-md bg-white/10 px-3 text-sm font-medium ring-1 ring-white/20 hover:bg-white/20"><QrCode className="size-4" />Show QR</button>
              </div>
              <div className="mt-4 text-lg font-semibold">{me.data.first_name} {me.data.last_name}</div>
              <dl className="mt-2 grid grid-cols-3 gap-2 text-sm">
                <div><dt className="text-brand-100">Blood</dt><dd className="font-semibold">{me.data.blood_group ?? '—'}</dd></div>
                <div><dt className="text-brand-100">Genotype</dt><dd className="font-semibold">{me.data.genotype ?? '—'}</dd></div>
                <div><dt className="text-brand-100">Born</dt><dd className="font-semibold">{fmtDate(me.data.dob)}</dd></div>
              </dl>
              {me.data.allergies.length > 0 && (
                <div className="mt-4 flex items-start gap-2 rounded-md bg-white px-3 py-2 text-sm font-semibold text-rose-700">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0" />Allergy: {me.data.allergies.join(', ')}
                </div>
              )}
            </section>
          )}

          {qr && (
            <section className="rounded-lg border border-slate-200 bg-white p-4 text-center animate-slide-up">
              <div className="flex items-center justify-between"><span className="text-base font-semibold text-slate-900">Check-in QR code</span><button onClick={() => setQr(null)} aria-label="Close QR" className="grid size-9 place-items-center rounded-md text-slate-500 hover:bg-slate-100"><X className="size-4" /></button></div>
              <img src={qr} alt="Your VITALIS check-in QR code" className="mx-auto mt-2 size-48" />
              <p className="text-sm text-slate-500">Works once, for 10 minutes. It holds no medical information.</p>
            </section>
          )}

          {rec.data && (
            <div className="grid grid-cols-3 divide-x divide-slate-200 rounded-lg border border-slate-200 bg-white text-center">
              <div className="py-3"><div className="text-2xl font-semibold tabular">{rec.data.facilities.length}</div><div className="text-sm text-slate-500">Hospitals</div></div>
              <div className="py-3"><div className="text-2xl font-semibold tabular">{rec.data.encounters.length}</div><div className="text-sm text-slate-500">Visits</div></div>
              <div className="py-3"><div className="text-2xl font-semibold tabular">{rec.data.lab_series.length}</div><div className="text-sm text-slate-500">Results</div></div>
            </div>
          )}

          <div className="grid grid-cols-3 rounded-lg border border-slate-200 bg-white p-1" role="tablist">
            {(['visits', 'results', 'access'] as const).map((t) => (
              <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)} className={clsx('h-10 rounded-md text-sm font-semibold transition-colors duration-150', tab === t ? 'bg-brand-700 text-white' : 'text-slate-600 hover:bg-slate-50')}>
                {{ visits: 'Visits', results: 'Results', access: 'Who looked' }[t]}
              </button>
            ))}
          </div>

          {tab === 'visits' && (
            <div className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
              {rec.data?.encounters.map((e) => (
                <div key={e.id} className="p-4">
                  <div className="flex items-center justify-between gap-2"><FacilityChip name={e.facility_name} /><span className="text-sm text-slate-500">{fmtDate(e.opened_at)}</span></div>
                  <div className="mt-2 text-base font-medium text-slate-900">{e.presenting_complaint}</div>
                  {e.clinical_notes.at(-1)?.assessment && <div className="mt-1 line-clamp-2 text-sm text-slate-500">{e.clinical_notes.at(-1)!.assessment}</div>}
                  {e.status !== 'completed' && <div className="mt-2 text-sm font-medium text-sky-700">Visit in progress</div>}
                </div>
              ))}
            </div>
          )}

          {tab === 'results' && (
            <div className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
              {[...(rec.data?.lab_series ?? [])].reverse().map((l, i) => (
                <div key={i} className="flex items-center justify-between gap-3 px-4 py-3">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-slate-900">{l.parameter}</div>
                    <div className="text-xs text-slate-500">{shortFacility(l.facility_name)} · {fmtDate(l.date)}</div>
                  </div>
                  <LabFlagValue v={{ value: l.value, unit: l.unit ?? undefined, flag: l.flag ?? undefined }} />
                </div>
              ))}
            </div>
          )}

          {tab === 'access' && log.data && (
            <div className="space-y-4">
              <section>
                <h3 className="mb-2 flex items-center gap-1.5 text-base font-semibold text-slate-900"><KeyRound className="size-4 text-slate-400" />Hospitals that can see your records</h3>
                {active.length === 0 && <p className="text-sm text-slate-500">None right now. Each hospital only sees its own records about you.</p>}
                {active.map((c) => (
                  <div key={c.id} className="mb-2 rounded-lg border border-slate-200 bg-white p-4">
                    <div className="flex items-center gap-2 text-base font-semibold text-slate-900"><ShieldCheck className="size-5 text-brand-700" />{shortFacility(c.facility_name)}</div>
                    <div className="mt-1 text-sm text-slate-500">You approved this {timeAgo(c.created_at)}. Ends {fmtDateTime(c.expires_at)}.</div>
                    <button onClick={() => revoke(c.id)} className="mt-3 inline-flex h-10 items-center gap-1.5 rounded-md border border-rose-200 px-3 text-sm font-semibold text-rose-700 hover:bg-rose-50"><ShieldOff className="size-4" />Remove access now</button>
                  </div>
                ))}
              </section>
              <section>
                <h3 className="mb-2 flex items-center gap-1.5 text-base font-semibold text-slate-900"><Eye className="size-4 text-slate-400" />Everyone who opened your record</h3>
                <div className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
                  {log.data.events.length === 0 && <p className="p-4 text-sm text-slate-500">No one yet.</p>}
                  {collapse(log.data.events).map((ev) => (
                    <div key={ev.id} className="px-4 py-3 text-sm">
                      <div className="text-slate-800"><b>{ev.actor?.replace(/\s*\(.*\)$/, '') ?? 'System'}</b>{ev.facility_name && <> at {shortFacility(ev.facility_name)}</>} {ACTION_TEXT[ev.action] ?? ev.action.toLowerCase()}</div>
                      <div className="mt-0.5 text-xs text-slate-500">{fmtDateTime(ev.timestamp)}{ev.count > 1 && ` · ${ev.count} times`}</div>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          )}
        </div>
        )}
      </div>
    </div>
  )
}
