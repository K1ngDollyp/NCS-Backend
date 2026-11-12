import clsx from 'clsx'
import { AlertTriangle, Ambulance, ArrowLeft, Check, CheckCircle2, ChevronDown, Clock, Hospital, LocateFixed, MapPin, Phone, Send, ShieldCheck, Siren, XCircle } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { shortFacility, timeAgo } from '../lib/format'
import { useResource } from '../lib/hooks'
import type { EmergencyRequest, Facility, HospitalSearchResult, PatientProfile, Referral, TriageResult } from '../lib/types'
import { Button, ErrorNote, Skeleton } from './ui'

/* VITALIS CareConnect: symptom check → capability-matched hospital → share record + referral → hospital confirms.
   Emergencies go through VITALIS emergency coordination: hospitals are asked one at a time and must confirm.
   Every step calls the real backend: /triage/sessions, /hospitals/search, /connect/qr-grants, /referrals,
   /emergency/requests. */

const WARNING_SIGNS = ['Chest pain', 'Difficulty breathing', 'Slurred speech', 'Sudden weakness on one side', 'Severe bleeding', 'Loss of consciousness']
const OTHER_SYMPTOMS = ['Headache', 'Blurred vision', 'Excessive thirst', 'Frequent urination', 'Tiredness', 'High fever', 'Cough', 'Body aches', 'Severe abdominal pain', 'Vomiting and diarrhea']
const DURATIONS = [{ v: 1, l: 'Today' }, { v: 3, l: '2–3 days' }, { v: 7, l: 'About a week' }, { v: 30, l: 'Longer' }]

/** What the patient needs, mapped to the capability-search parameters each hospital's reported capabilities are checked against. */
const CARE_NEEDS: { key: string; label: string; params: Record<string, string> }[] = [
  { key: 'general', label: 'General doctor', params: {} },
  { key: 'heart', label: 'Heart and blood pressure', params: { condition: 'heart' } },
  { key: 'pregnancy', label: 'Pregnancy and childbirth', params: { condition: 'obstetric' } },
  { key: 'children', label: 'Children', params: { condition: 'pediatric' } },
  { key: 'emergency', label: 'Emergency care', params: { service: 'Emergency Resuscitation' } },
]

/** Demo location used when the browser location is not shared. Labelled as such in the UI. */
const DEMO_LOCATION = { lat: 7.153, lon: 3.348, label: 'Sapon, Abeokuta (demo location)' }

const SHARE_SCOPE = ['vitals', 'allergies', 'medications', 'lab_results', 'notes']
const SCOPE_TEXT = ['Past visits and doctors’ notes', 'Vital signs', 'Lab results', 'Allergies and medicines']

const URGENCY = {
  EMERGENCY_RED: { title: 'Get emergency care now', tone: 'rose', referral: 'emergency' },
  URGENT_YELLOW: { title: 'See a doctor today', tone: 'amber', referral: 'urgent' },
  ROUTINE_GREEN: { title: 'No emergency warning signs found', tone: 'brand', referral: 'routine' },
} as const

const PATIENT_GUIDANCE: Record<string, string> = {
  EMERGENCY_RED: 'One of your answers is an emergency warning sign. Call 112 or go to the nearest emergency unit now. Do not wait for an appointment.',
  URGENT_YELLOW: 'Some of your answers mean a doctor should see you today.',
  ROUTINE_GREEN: 'None of your answers are emergency warning signs. A doctor should still see you, especially if it gets worse or does not go away.',
}

function needFromTriage(t: TriageResult) {
  if (t.urgency_level === 'EMERGENCY_RED') return 'emergency'
  const s = (t.recommended_service ?? '').toLowerCase()
  if (s.includes('cardio')) return 'heart'
  if (s.includes('obstetric')) return 'pregnancy'
  return 'general'
}

/** The warning signs the patient reported, extracted from the rule output (never the clinical label). */
function triggersOf(flags: string[]) {
  return [...new Set(flags.map((f) => f.match(/triggered by '([^']+)'/)?.[1]).filter((t): t is string => !!t))]
}

type Step = 'symptoms' | 'result' | 'hospitals' | 'send' | 'status' | 'emergency'

export function CareConnect({ patient, onExit, initialReferral, initialEmergency }: { patient: PatientProfile; onExit: () => void; initialReferral?: Referral | null; initialEmergency?: EmergencyRequest | null }) {
  const [step, setStep] = useState<Step>(initialEmergency ? 'emergency' : initialReferral ? 'status' : 'symptoms')
  const [picked, setPicked] = useState<string[]>([])
  const [days, setDays] = useState(7)
  const [details, setDetails] = useState('')
  const [triage, setTriage] = useState<TriageResult | null>(null)
  const [need, setNeed] = useState('general')
  const [chosen, setChosen] = useState<HospitalSearchResult | null>(null)
  const [referral, setReferral] = useState<Referral | null>(initialReferral ?? null)
  const [emergency, setEmergency] = useState<EmergencyRequest | null>(initialEmergency ?? null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function runCheck() {
    setBusy(true); setError(null)
    try {
      const symptoms = picked.map((s) => ({ symptom: s.toLowerCase(), duration_days: days }))
      if (details.trim()) symptoms.push({ symptom: details.trim().toLowerCase(), duration_days: days })
      const t = await api<TriageResult>('/triage/sessions', { method: 'POST', json: { patient_id: patient.id, symptoms } })
      setTriage(t)
      setNeed(needFromTriage(t))
      setStep('result')
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  async function startEmergency() {
    if (!triage) return
    setBusy(true); setError(null)
    try {
      const signs = triggersOf(triage.matched_red_flags)
      const symptoms = triage.symptoms_structured.map((s) => s.symptom).join(', ')
      const em = await api<EmergencyRequest>('/emergency/requests', {
        method: 'POST',
        json: {
          patient_id: patient.id, initiated_by_role: 'patient',
          emergency_type: signs[0] ? signs[0][0].toUpperCase() + signs[0].slice(1) : 'Medical emergency',
          presenting_complaint: symptoms, patient_latitude: DEMO_LOCATION.lat, patient_longitude: DEMO_LOCATION.lon,
          patient_address: DEMO_LOCATION.label,
        },
      })
      setEmergency(em)
      setStep('emergency')
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  // Each step is a new screen: start it at the top.
  useEffect(() => { window.scrollTo({ top: 0 }) }, [step])

  const back = () => {
    setError(null)
    if (step === 'symptoms' || step === 'status' || step === 'emergency') onExit()
    else setStep(({ result: 'symptoms', hospitals: 'result', send: 'hospitals' } as const)[step])
  }

  return (
    <div className="animate-fade-in">
      <div className="flex items-center gap-2 border-b border-slate-200 bg-white px-3 py-2">
        <button onClick={back} aria-label="Back" className="grid size-10 place-items-center rounded-md text-slate-600 hover:bg-slate-100"><ArrowLeft className="size-5" /></button>
        <div className="min-w-0">
          <div className={clsx('text-xs font-medium', step === 'emergency' ? 'text-rose-700' : 'text-brand-700')}>VITALIS CareConnect</div>
          <div className="truncate text-base font-semibold text-slate-900">
            {{ symptoms: 'Check my symptoms', result: 'Your result', hospitals: 'Find a hospital', send: 'Send your details', status: 'Your referral', emergency: 'Emergency help' }[step]}
          </div>
        </div>
      </div>

      <div className="space-y-4 px-4 py-5">
        {step === 'symptoms' && (
          <>
            <ChipGroup title="Any of these right now?" tone="rose" options={WARNING_SIGNS} picked={picked} setPicked={setPicked} />
            <ChipGroup title="What else are you feeling?" options={OTHER_SYMPTOMS} picked={picked} setPicked={setPicked} />
            <section>
              <h3 className="mb-2 text-sm font-semibold text-slate-900">How long?</h3>
              <div className="grid grid-cols-2 gap-2">
                {DURATIONS.map((d) => (
                  <button key={d.v} onClick={() => setDays(d.v)} className={clsx('h-11 rounded-md border text-sm font-medium', days === d.v ? 'border-brand-700 bg-brand-50 text-brand-800' : 'border-slate-300 bg-white text-slate-700')}>{d.l}</button>
                ))}
              </div>
            </section>
            <label className="block">
              <span className="mb-1.5 block text-sm font-semibold text-slate-900">Anything else? <span className="font-normal text-slate-500">(optional)</span></span>
              <textarea value={details} onChange={(e) => setDetails(e.target.value)} rows={2} placeholder="In your own words" className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-base text-slate-900 placeholder:text-slate-400 focus:border-brand-600 focus:outline-none" />
            </label>
            <ErrorNote message={error} />
            <Button size="lg" className="w-full" disabled={picked.length === 0 && !details.trim()} loading={busy} onClick={runCheck}>Check my symptoms</Button>
            <p className="text-center text-xs text-slate-500">This is a rule-based check, not a diagnosis. It never replaces a doctor or emergency care.</p>
          </>
        )}

        {step === 'result' && triage && (
          <>
            <TriageCard triage={triage} busy={busy} onFind={() => setStep('hospitals')} onEmergency={startEmergency} />
            <ErrorNote message={error} />
          </>
        )}

        {step === 'hospitals' && triage && (
          <HospitalSearch need={need} setNeed={setNeed} onChoose={(m) => { setChosen(m); setStep('send') }} />
        )}

        {step === 'send' && triage && chosen && (
          <SendReferral patient={patient} triage={triage} match={chosen} need={need}
            onSent={(r) => { setReferral(r); setStep('status') }} />
        )}

        {step === 'status' && referral && (
          <ReferralStatusView referral={referral} patient={patient} onChooseAnother={() => { setReferral(null); setStep(triage ? 'hospitals' : 'symptoms') }} onDone={onExit} />
        )}

        {step === 'emergency' && emergency && <EmergencyStatusView request={emergency} patient={patient} onDone={onExit} />}
      </div>
    </div>
  )
}

function ChipGroup({ title, options, picked, setPicked, tone }: { title: string; options: string[]; picked: string[]; setPicked: (v: string[]) => void; tone?: 'rose' }) {
  const toggle = (s: string) => setPicked(picked.includes(s) ? picked.filter((p) => p !== s) : [...picked, s])
  return (
    <section>
      <h3 className={clsx('mb-2 text-sm font-semibold', tone === 'rose' ? 'text-rose-800' : 'text-slate-900')}>{title}</h3>
      <div className="flex flex-wrap gap-2">
        {options.map((s) => {
          const on = picked.includes(s)
          return (
            <button key={s} onClick={() => toggle(s)} aria-pressed={on}
              className={clsx('inline-flex min-h-10 items-center gap-1.5 rounded-md border px-3 text-sm font-medium transition-colors duration-150',
                on ? (tone === 'rose' ? 'border-rose-600 bg-rose-50 text-rose-800' : 'border-brand-700 bg-brand-50 text-brand-800') : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50')}>
              {on && <Check className="size-4" />}{s}
            </button>
          )
        })}
      </div>
    </section>
  )
}

function TriageCard({ triage, busy, onFind, onEmergency }: { triage: TriageResult; busy: boolean; onFind: () => void; onEmergency: () => void }) {
  const u = URGENCY[triage.urgency_level as keyof typeof URGENCY] ?? URGENCY.ROUTINE_GREEN
  const emergency = triage.urgency_level === 'EMERGENCY_RED'
  // Patients see the warning sign they reported, never the rule's clinical label (no diagnosis on the patient side).
  const triggers = triggersOf(triage.matched_red_flags)
  return (
    <>
      <section className={clsx('rounded-lg border border-l-4 bg-white p-4 animate-slide-up',
        u.tone === 'rose' ? 'border-rose-200 border-l-rose-600' : u.tone === 'amber' ? 'border-amber-200 border-l-amber-500' : 'border-slate-200 border-l-brand-600')}>
        <div className={clsx('flex items-center gap-2 text-lg font-semibold', u.tone === 'rose' ? 'text-rose-800' : u.tone === 'amber' ? 'text-amber-800' : 'text-slate-900')}>
          {emergency ? <Siren className="size-5" /> : u.tone === 'amber' ? <AlertTriangle className="size-5" /> : <CheckCircle2 className="size-5 text-brand-700" />}
          {u.title}
        </div>
        <p className="mt-2 text-base text-slate-700">{PATIENT_GUIDANCE[triage.urgency_level] ?? PATIENT_GUIDANCE.ROUTINE_GREEN}</p>
        {triggers.length > 0 && (
          <ul className="mt-3 space-y-1 text-sm text-slate-700">
            {triggers.map((t) => <li key={t} className="flex gap-2"><AlertTriangle className={clsx('mt-0.5 size-4 shrink-0', emergency ? 'text-rose-600' : 'text-amber-600')} />You said: {t}</li>)}
          </ul>
        )}
        <div className="mt-3 text-xs text-slate-500">Rule-based check · protocol {triage.protocol_version} · not a diagnosis</div>
      </section>

      {emergency ? (
        <>
          <a href="tel:112" className="flex h-14 items-center justify-center gap-2 rounded-md bg-rose-700 text-lg font-semibold text-white hover:bg-rose-800">
            <Phone className="size-5" />Call 112 now
          </a>
          <Button size="lg" variant="secondary" className="w-full" loading={busy} icon={<Siren className="size-5" />} onClick={onEmergency}>
            Find a hospital that will take me now
          </Button>
          <p className="text-center text-sm text-slate-600">VITALIS asks the best-equipped hospital to confirm it can receive you, and moves to the next one if it can’t.</p>
        </>
      ) : (
        <Button size="lg" className="w-full" icon={<Hospital className="size-5" />} onClick={onFind}>Find a hospital that can see me</Button>
      )}
    </>
  )
}

/** Great-circle distance in km (same formula as the backend matcher), used only to explain exclusions. */
function km(a: { lat: number; lon: number }, f: Facility) {
  const r = (d: number) => (d * Math.PI) / 180
  const dLat = r(f.latitude - a.lat), dLon = r(f.longitude - a.lon)
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(r(a.lat)) * Math.cos(r(f.latitude)) * Math.sin(dLon / 2) ** 2
  return 6371 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h))
}

const ACCEPTANCE: Record<string, { text: string; tone: 'brand' | 'amber' | 'slate' }> = {
  accepting: { text: 'Accepting patients', tone: 'brand' },
  limited: { text: 'Limited capacity', tone: 'amber' },
  not_accepting: { text: 'Not accepting', tone: 'slate' },
  unknown: { text: 'Availability unknown', tone: 'slate' },
}

function HospitalSearch({ need, setNeed, onChoose }: { need: string; setNeed: (n: string) => void; onChoose: (m: HospitalSearchResult) => void }) {
  const [loc, setLoc] = useState(DEMO_LOCATION)
  const [locating, setLocating] = useState(false)
  const n = CARE_NEEDS.find((c) => c.key === need) ?? CARE_NEEDS[0]
  const qs = new URLSearchParams({ latitude: String(loc.lat), longitude: String(loc.lon), ...n.params })
  const matches = useResource<HospitalSearchResult[]>(`/hospitals/search?${qs}`)
  const all = useResource<Facility[]>('/facilities')

  const excluded = useMemo(() => {
    if (!matches.data || !all.data) return []
    const ok = new Set(matches.data.map((m) => m.facility.id))
    return all.data.filter((f) => !ok.has(f.id))
  }, [matches.data, all.data])
  const nearest = matches.data?.length ? Math.min(...matches.data.map((m) => m.distance_km)) : null

  function useMyLocation() {
    if (!navigator.geolocation) return
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      (p) => { setLoc({ lat: +p.coords.latitude.toFixed(4), lon: +p.coords.longitude.toFixed(4), label: 'Your current location' }); setLocating(false) },
      () => setLocating(false),
      { timeout: 8000 },
    )
  }

  return (
    <>
      <section>
        <h3 className="mb-2 text-sm font-semibold text-slate-900">What care do you need?</h3>
        <div className="flex flex-wrap gap-2">
          {CARE_NEEDS.map((c) => (
            <button key={c.key} onClick={() => setNeed(c.key)} aria-pressed={need === c.key}
              className={clsx('min-h-10 rounded-md border px-3 text-sm font-medium', need === c.key ? 'border-brand-700 bg-brand-50 text-brand-800' : 'border-slate-300 bg-white text-slate-700')}>{c.label}</button>
          ))}
        </div>
      </section>
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className="inline-flex items-center gap-1.5 text-slate-600"><MapPin className="size-4 text-slate-400" />{loc.label}</span>
        {loc === DEMO_LOCATION && <button onClick={useMyLocation} className="inline-flex items-center gap-1 font-medium text-brand-700"><LocateFixed className="size-4" />{locating ? 'Locating…' : 'Use my location'}</button>}
      </div>

      <ErrorNote message={matches.error} />
      {matches.loading && !matches.data && <div className="space-y-3"><Skeleton className="h-36" /><Skeleton className="h-36" /></div>}

      {matches.data && (
        <p className="text-sm text-slate-600">
          {matches.data.length === 0 ? <>No hospital on VITALIS can confirm <b>{n.label.toLowerCase()}</b> right now.</> :
            <><b>{matches.data.length}</b> of {all.data?.length ?? '…'} hospitals can provide <b>{n.label.toLowerCase()}</b>. Best fit first, not nearest first.</>}
        </p>
      )}

      {matches.data?.map((m, i) => <MatchCard key={m.facility.id} m={m} best={i === 0} onChoose={() => onChoose(m)} />)}

      {excluded.length > 0 && (
        <section className="rounded-lg border border-dashed border-slate-300 p-4">
          <h3 className="text-sm font-semibold text-slate-700">Not shown</h3>
          <ul className="mt-2 space-y-2">
            {excluded.map((f) => (
              <li key={f.id} className="flex items-start gap-2 text-sm text-slate-600">
                <XCircle className="mt-0.5 size-4 shrink-0 text-slate-400" />
                <span><b className="font-medium text-slate-800">{shortFacility(f.name)}</b>: has not confirmed it can provide {n.label.toLowerCase()} right now
                  {nearest !== null && km(loc, f) < nearest ? `, so it was left out even though it is closer (${km(loc, f).toFixed(1)} km).` : '.'}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  )
}

function MatchCard({ m, best, onChoose }: { m: HospitalSearchResult; best: boolean; onChoose: () => void }) {
  const [open, setOpen] = useState(false)
  const a = ACCEPTANCE[m.acceptance_status] ?? ACCEPTANCE.unknown
  const stale = m.freshness_label === 'stale' || m.freshness_label === 'unknown'
  const b = m.score_breakdown
  const rows = [
    ['Can provide the care you need', b.service_compatibility_C, '40%'],
    ['Reported availability', b.availability_A, '25%'],
    ['Distance', b.distance_suitability_D, '20%'],
    ['Verified and up to date', b.verification_freshness_V, '15%'],
  ] as const
  return (
    <article className={clsx('rounded-lg border bg-white animate-slide-up', best ? 'border-brand-300' : 'border-slate-200')}>
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            {best && <div className="mb-1 text-xs font-semibold text-brand-700">Best fit</div>}
            <h3 className="text-base font-semibold text-slate-900">{shortFacility(m.facility.name)}</h3>
            <div className="text-sm text-slate-500">{m.facility.facility_type} · {m.distance_km.toFixed(1)} km away</div>
          </div>
          <div className="shrink-0 text-right">
            <div className="text-2xl font-semibold text-slate-900 tabular">{Math.round(m.suitability_score)}</div>
            <div className="text-xs text-slate-500">fit / 100</div>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm">
          <span className={clsx('inline-flex items-center gap-1.5 font-medium', a.tone === 'brand' ? 'text-brand-800' : a.tone === 'amber' ? 'text-amber-800' : 'text-slate-600')}>
            <span className={clsx('size-2 rounded-full', a.tone === 'brand' ? 'bg-brand-600' : a.tone === 'amber' ? 'bg-amber-500' : 'bg-slate-400')} />
            {a.text}{m.expected_wait_minutes != null && ` · about ${m.expected_wait_minutes} min wait`}
          </span>
        </div>
        <div className={clsx('mt-1 inline-flex items-start gap-1 text-sm', stale ? 'text-amber-800' : 'text-slate-500')}>
          <Clock className="mt-0.5 size-3.5 shrink-0" />
          <span>{stale ? 'Out of date: ' : ''}Confirmed by {m.reported_by}{m.last_confirmed_at && `, ${timeAgo(m.last_confirmed_at)}`}</span>
        </div>
        {m.matched_capabilities.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {m.matched_capabilities.map((c) => <span key={c} className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700"><Check className="size-3 text-brand-700" />{c}</span>)}
          </div>
        )}
        <button onClick={() => setOpen(!open)} aria-expanded={open} className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-slate-600 hover:text-slate-900">
          Why this hospital <ChevronDown className={clsx('size-4 transition-transform duration-150', open && 'rotate-180')} />
        </button>
        {open && (
          <dl className="mt-2 space-y-1.5 rounded-md bg-slate-50 p-3 text-sm animate-fade-in">
            {rows.map(([label, v, w]) => (
              <div key={label} className="flex items-center justify-between gap-3">
                <dt className="text-slate-600">{label} <span className="text-slate-400">({w})</span></dt>
                <dd className="font-semibold text-slate-900 tabular">{Math.round(v ?? 0)}</dd>
              </div>
            ))}
            <p className="pt-1 text-xs text-slate-500">A transparent prototype score, not a clinical ranking. The hospital still has to confirm it can see you.</p>
          </dl>
        )}
      </div>
      <div className="border-t border-slate-100 p-3">
        <Button className="w-full" variant={best ? 'primary' : 'secondary'} onClick={onChoose}>Ask {shortFacility(m.facility.name)} to see me</Button>
      </div>
    </article>
  )
}

function SendReferral({ patient, triage, match, need, onSent }: { patient: PatientProfile; triage: TriageResult; match: HospitalSearchResult; need: string; onSent: (r: Referral) => void }) {
  const [share, setShare] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const name = shortFacility(match.facility.name)
  const u = URGENCY[triage.urgency_level as keyof typeof URGENCY] ?? URGENCY.ROUTINE_GREEN
  const symptoms = triage.symptoms_structured.map((s) => s.symptom)
  const d = triage.symptoms_structured[0]?.duration_days
  const reason = `${symptoms.join(', ')}${d ? ` for ${d === 1 ? 'today' : `${d} days`}` : ''}`
  const needLabel = CARE_NEEDS.find((c) => c.key === need)?.label ?? need

  async function send() {
    setBusy(true); setError(null)
    try {
      if (share) {
        await api('/connect/qr-grants', {
          method: 'POST',
          json: { patient_id: patient.id, grantee_facility_id: match.facility.id, scope: SHARE_SCOPE, purpose: `Shared by patient with CareConnect referral to ${name}`, duration_minutes: 24 * 60 },
        })
      }
      const r = await api<Referral>('/referrals', {
        method: 'POST',
        json: {
          patient_id: patient.id, destination_facility_id: match.facility.id, urgency: u.referral,
          clinical_reason: `${reason[0].toUpperCase()}${reason.slice(1)}. CareConnect symptom check: ${u.title.toLowerCase()}.${share ? ' Patient shared their VITALIS record with this referral.' : ''}`,
          service_needed: needLabel,
        },
      })
      onSent(r)
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <>
      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="text-sm text-slate-500">Sending to</div>
        <div className="text-lg font-semibold text-slate-900">{name}</div>
        <dl className="mt-3 space-y-2 text-sm">
          <div><dt className="text-slate-500">Why you need care</dt><dd className="font-medium text-slate-900">{reason[0].toUpperCase() + reason.slice(1)}</dd></div>
          <div><dt className="text-slate-500">Care needed</dt><dd className="font-medium text-slate-900">{needLabel}</dd></div>
        </dl>
      </section>

      <label className={clsx('flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition-colors duration-150', share ? 'border-brand-300 bg-brand-50' : 'border-slate-300 bg-white')}>
        <input type="checkbox" checked={share} onChange={(e) => setShare(e.target.checked)} className="mt-1 size-5 accent-brand-700" />
        <div>
          <div className="text-base font-semibold text-slate-900">Share my records from other hospitals</div>
          <p className="mt-1 text-sm text-slate-600">So the doctors at {name} see your full history before you arrive:</p>
          <ul className="mt-2 space-y-1 text-sm text-slate-700">
            {SCOPE_TEXT.map((s) => <li key={s} className="flex items-center gap-2"><Check className="size-4 text-brand-700" />{s}</li>)}
          </ul>
          <p className="mt-2 text-sm text-slate-600">Only {name} can see them, for 24 hours. You can remove access at any time.</p>
        </div>
      </label>
      {!share && <p className="text-sm text-slate-600">{name} will only see your referral. Staff can still ask for your records at the desk with a one-time code.</p>}

      <ErrorNote message={error} />
      <Button size="lg" className="w-full" loading={busy} icon={<Send className="size-5" />} onClick={send}>
        {share ? `Share and send to ${name}` : `Send to ${name}`}
      </Button>
    </>
  )
}

const STATUS_VIEW: Record<string, { title: string; tone: 'sky' | 'brand' | 'rose' | 'amber' | 'slate' }> = {
  pending: { title: 'Waiting for the hospital to confirm', tone: 'sky' },
  accepted: { title: 'The hospital can see you', tone: 'brand' },
  rejected: { title: 'The hospital can’t take you right now', tone: 'rose' },
  more_information: { title: 'The hospital needs more information', tone: 'amber' },
  completed: { title: 'You’ve checked in', tone: 'brand' },
  cancelled: { title: 'Referral cancelled', tone: 'slate' },
}

const TONE_BORDER = {
  brand: 'border-brand-200 border-l-brand-600', rose: 'border-rose-200 border-l-rose-600', amber: 'border-amber-200 border-l-amber-500',
  sky: 'border-sky-200 border-l-sky-600', slate: 'border-slate-200 border-l-slate-400',
}

function PendingDot({ tone = 'sky' }: { tone?: 'sky' | 'rose' }) {
  return (
    <span className="relative flex size-2.5 shrink-0">
      <span className={clsx('absolute inline-flex size-full animate-ping rounded-full opacity-75 motion-reduce:hidden', tone === 'rose' ? 'bg-rose-400' : 'bg-sky-400')} />
      <span className={clsx('relative inline-flex size-2.5 rounded-full', tone === 'rose' ? 'bg-rose-600' : 'bg-sky-600')} />
    </span>
  )
}

export function ReferralStatusView({ referral, patient, onChooseAnother, onDone }: { referral: Referral; patient: PatientProfile; onChooseAnother: () => void; onDone: () => void }) {
  const mine = useResource<Referral[]>('/referrals/me', { poll: 2500 })
  const facilities = useResource<Facility[]>('/facilities')
  const r = mine.data?.find((x) => x.id === referral.id) ?? referral
  const name = shortFacility(facilities.data?.find((f) => f.id === r.destination_facility_id)?.name) || 'The hospital'
  const v = STATUS_VIEW[r.status] ?? STATUS_VIEW.pending

  return (
    <>
      <section key={r.status} aria-live="polite" className={clsx('rounded-lg border border-l-4 bg-white p-4 animate-slide-up', TONE_BORDER[v.tone])}>
        <div className="text-sm font-medium text-slate-500">{name} · {r.referral_number}</div>
        <div className="mt-1 flex items-center gap-2 text-lg font-semibold text-slate-900">
          {r.status === 'pending' && <PendingDot />}
          {(r.status === 'accepted' || r.status === 'completed') && <CheckCircle2 className="size-5 text-brand-700" />}
          {r.status === 'rejected' && <XCircle className="size-5 text-rose-600" />}
          {v.title}
        </div>
        {r.status === 'pending' && <p className="mt-2 text-base text-slate-700">{name} has your referral. Don’t travel yet: VITALIS waits for the hospital to confirm it can see you.</p>}
        {r.status === 'accepted' && (
          <div className="mt-2 space-y-3">
            <p className="text-base text-slate-700">{name} confirmed {timeAgo(r.responded_at)}. Go to the main reception today and give your VITALIS ID.</p>
            <div className="rounded-md bg-slate-900 py-3 text-center font-mono text-2xl font-semibold tracking-wider text-white">{patient.patient_number}</div>
          </div>
        )}
        {r.facility_response_reason && r.status !== 'completed' && <p className="mt-2 text-base text-slate-700">“{r.facility_response_reason}”</p>}
        {r.status === 'completed' && <p className="mt-2 text-base text-slate-700">Your visit has started. You can follow it under Visits.</p>}
      </section>

      {r.clinical_reason.includes('shared their VITALIS record') && r.status !== 'rejected' && (
        <p className="flex items-start gap-2 text-sm text-slate-600"><ShieldCheck className="mt-0.5 size-4 shrink-0 text-brand-700" />You shared your records with {name} for 24 hours. See or remove access under “Who looked”.</p>
      )}

      {(r.status === 'rejected' || r.status === 'more_information') && <Button size="lg" className="w-full" onClick={onChooseAnother}>Choose another hospital</Button>}
      <Button size="lg" variant="secondary" className="w-full" onClick={onDone}>Back to home</Button>
    </>
  )
}

/** Live view of an emergency request: which hospital is being asked, who declined, and the confirmed hospital + transport. */
export function EmergencyStatusView({ request, patient, onDone }: { request: EmergencyRequest; patient: PatientProfile; onDone: () => void }) {
  const live = useResource<EmergencyRequest>(`/emergency/requests/${request.id}`, { poll: 2500 })
  const em = live.data ?? request
  const current = em.candidate_facilities.find((c) => c.facility_id === em.current_candidate_facility_id)
  const confirmed = em.candidate_facilities.find((c) => c.facility_id === em.confirmed_facility_id)
  const waiting = em.status === 'awaiting_hospital_confirmation'
  const noOne = !em.current_candidate_facility_id && !em.confirmed_facility_id

  return (
    <>
      <section key={em.status + (em.current_candidate_facility_id ?? '')} aria-live="assertive"
        className={clsx('rounded-lg border border-l-4 bg-white p-4 animate-slide-up', confirmed ? TONE_BORDER.brand : TONE_BORDER.rose)}>
        <div className="text-sm font-medium text-slate-500">{em.emergency_type} · {em.emergency_number}</div>
        {confirmed ? (
          <>
            <div className="mt-1 flex items-center gap-2 text-lg font-semibold text-slate-900"><CheckCircle2 className="size-5 text-brand-700" />{shortFacility(confirmed.facility_name)} is ready for you</div>
            <p className="mt-2 text-base text-slate-700">The hospital confirmed it can receive you and has been told you are coming.</p>
          </>
        ) : waiting && current ? (
          <>
            <div className="mt-1 flex items-center gap-2 text-lg font-semibold text-slate-900"><PendingDot tone="rose" />Asking {shortFacility(current.facility_name)} to confirm</div>
            <p className="mt-2 text-base text-slate-700">Chosen because it can treat this ({current.matched_capabilities.slice(0, 3).join(', ')}), {current.distance_km.toFixed(1)} km away. Keep your phone with you.</p>
          </>
        ) : (
          <>
            <div className="mt-1 text-lg font-semibold text-rose-800">No hospital has confirmed yet</div>
            <p className="mt-2 text-base text-slate-700">Call 112 now. VITALIS keeps looking for a hospital that can take you.</p>
          </>
        )}
      </section>

      {em.transport && confirmed && (
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="flex items-center gap-2 text-base font-semibold text-slate-900"><Ambulance className="size-5 text-slate-500" />{em.transport.vehicle_type}</div>
          <div className="mt-1 text-sm text-slate-600">{em.transport.provider_name} · <span className="font-mono">{em.transport.vehicle_callsign}</span></div>
          <div className="mt-3 grid grid-cols-2 divide-x divide-slate-100 rounded-md bg-slate-50 text-center">
            <div className="py-2"><div className="text-2xl font-semibold tabular">{em.transport.estimated_pickup_minutes} min</div><div className="text-xs text-slate-500">to pick you up</div></div>
            <div className="py-2"><div className="text-2xl font-semibold tabular">{em.transport.estimated_hospital_arrival_minutes} min</div><div className="text-xs text-slate-500">to the hospital</div></div>
          </div>
          <p className="mt-2 text-xs text-slate-500">Ambulance dispatch is simulated in this prototype.</p>
        </section>
      )}

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-slate-900">Hospitals VITALIS asked</h3>
        <ol className="mt-2 space-y-2">
          {em.candidate_facilities.map((c) => (
            <li key={c.facility_id} className="flex items-center justify-between gap-2 text-sm">
              <span className="min-w-0 truncate text-slate-800">{shortFacility(c.facility_name)} <span className="text-slate-400">· {c.distance_km.toFixed(1)} km</span></span>
              <span className={clsx('shrink-0 font-medium', c.confirmation_state === 'accepted' ? 'text-brand-800' : c.confirmation_state === 'declined' ? 'text-rose-700' : c.facility_id === em.current_candidate_facility_id ? 'text-sky-700' : 'text-slate-400')}>
                {c.confirmation_state === 'accepted' ? 'Confirmed' : c.confirmation_state === 'declined' ? 'Can’t take you' : c.facility_id === em.current_candidate_facility_id ? 'Asking now' : 'Next if needed'}
              </span>
            </li>
          ))}
          {em.candidate_facilities.length === 0 && <li className="text-sm text-slate-500">No hospital reports the capabilities needed and is accepting emergencies.</li>}
        </ol>
      </section>

      {(noOne || !confirmed) && (
        <a href="tel:112" className="flex h-12 items-center justify-center gap-2 rounded-md bg-rose-700 text-base font-semibold text-white hover:bg-rose-800"><Phone className="size-5" />Call 112</a>
      )}
      {confirmed && <p className="text-center text-sm text-slate-600">Show your VITALIS ID on arrival: <span className="font-mono font-semibold text-slate-900">{patient.patient_number}</span></p>}
      <Button size="lg" variant="secondary" className="w-full" onClick={onDone}>Back to home</Button>
    </>
  )
}
