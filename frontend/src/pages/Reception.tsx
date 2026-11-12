import clsx from 'clsx'
import { ArrowRight, Building2, CheckCircle2, Clock, HeartPulse, Lock, Search, ShieldCheck, Siren, Smartphone, UserPlus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { ConsentFlow } from '../components/ConsentFlow'
import { EmergencyInbox } from '../components/EmergencyInbox'
import { IncomingReferrals } from '../components/IncomingReferrals'
import { FacilityChip } from '../components/clinical'
import { Button, Card, CardHeader, EmptyState, ErrorNote, Field, Input, Modal, PageHeader, PriorityBadge, Select, SkeletonList, Stat, StatusBadge, Textarea, useToast } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { fmtDate, fmtDateTime, timeAgo } from '../lib/format'
import { useResource } from '../lib/hooks'
import type { Encounter, LookupResult, PatientProfile } from '../lib/types'

export default function Reception() {
  const { user } = useAuth()
  const toast = useToast()
  const [q, setQ] = useState('')
  const [results, setResults] = useState<LookupResult[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [consentFor, setConsentFor] = useState<LookupResult | null>(null)
  const [visitFor, setVisitFor] = useState<VisitTarget | null>(null)
  const [registering, setRegistering] = useState(false)
  const board = useResource<Encounter[]>(user?.facility_id ? `/encounters/queue/all?facility_id=${user.facility_id}` : null, { poll: 5000 })

  async function search(term = q) {
    if (term.trim().length < 3) return
    setSearching(true); setError(null)
    try {
      setResults(await api<LookupResult[]>(`/records/lookup?q=${encodeURIComponent(term.trim())}`))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSearching(false)
    }
  }

  const enc = board.data ?? []
  const count = (s: string[]) => enc.filter((e) => s.includes(e.status)).length

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader eyebrow="Front desk" title="Find a patient" subtitle="Search by VITALIS ID. If they have been to another hospital on the network, you can ask for their records here." />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-4">
          {user?.facility_id && <EmergencyInbox facilityId={user.facility_id} onArrived={(t) => setVisitFor(t)} />}
          {user?.facility_id && <IncomingReferrals facilityId={user.facility_id} onArrived={(t) => setVisitFor(t)} />}
          <Card className="p-4 sm:p-5">
            <form onSubmit={(e: FormEvent) => { e.preventDefault(); search() }} className="flex flex-col gap-2 sm:flex-row">
              <label className="relative min-w-0 flex-1">
                <span className="sr-only">VITALIS ID, phone or name</span>
                <Search className="pointer-events-none absolute left-3.5 top-1/2 size-5 -translate-y-1/2 text-slate-400" />
                <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="VITALIS ID, phone or name" className="!h-12 !pl-11 !text-lg" autoFocus />
              </label>
              <Button type="submit" size="lg" loading={searching}>Search</Button>
            </form>
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
              <button onClick={() => { setQ('VIT-2026-0002'); search('VIT-2026-0002') }} className="text-slate-500 hover:text-slate-900">
                Demo patient: <span className="font-mono font-semibold text-brand-700 underline decoration-brand-200 underline-offset-4">VIT-2026-0002</span>
              </button>
              <button onClick={() => setRegistering(true)} className="inline-flex items-center gap-1.5 font-medium text-brand-700 hover:text-brand-800">
                <UserPlus className="size-4" /> New to VITALIS? Register patient
              </button>
            </div>
          </Card>

          <ErrorNote message={error} />

          {results === null && (
            <Card><EmptyState icon={<Search />} title="Search to begin" description="A patient registered at any VITALIS hospital can be found with their ID alone. Their records stay locked until they approve." /></Card>
          )}
          {results?.length === 0 && (
            <Card><EmptyState icon={<Search />} title="No patient with that ID" description="Check the ID with the patient, or register them now. Their new ID will work at every hospital on the network."
              action={<Button variant="secondary" onClick={() => setRegistering(true)} icon={<UserPlus className="size-4" />}>Register patient</Button>} /></Card>
          )}

          {results?.map((r) => {
            const locked = !r.has_full_access && r.external_facilities.length > 0
            return (
              <Card key={r.patient_id} className="animate-slide-up">
                <div className="p-5">
                  <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                    <span className="text-xl font-semibold text-slate-900">{r.full_name}</span>
                    <span className="font-mono text-sm font-semibold text-slate-600">{r.patient_number}</span>
                  </div>
                  <div className="mt-0.5 text-base text-slate-500">{r.gender}, {r.age} yrs · born {fmtDate(r.dob)} · phone {r.masked_phone ?? 'not recorded'}</div>

                  <div className="mt-4 rounded-md bg-slate-50 p-3.5">
                    {r.external_facilities.length > 0 ? (
                      <>
                        <div className="text-sm font-medium text-slate-700">{r.external_encounters} previous visit{r.external_encounters === 1 ? '' : 's'} at other hospitals</div>
                        <div className="mt-2 flex flex-wrap gap-2">{r.external_facilities.map((f) => <FacilityChip key={f} name={f} />)}</div>
                      </>
                    ) : <div className="text-sm text-slate-600">{r.seen_at_this_facility ? 'Only seen at this hospital before.' : 'No previous visits on the network.'}</div>}
                    <div className="mt-3 flex items-center gap-2 text-sm">
                      {r.has_full_access
                        ? <><ShieldCheck className="size-4 shrink-0 text-brand-700" /><span className="font-medium text-brand-800">Patient approved access until {fmtDateTime(r.access_expires_at).split(' · ')[1]}</span></>
                        : locked ? <><Lock className="size-4 shrink-0 text-amber-700" /><span className="font-medium text-amber-800">Locked. The patient must approve with a one-time code.</span></> : null}
                    </div>
                  </div>
                </div>
                <div className="flex flex-col-reverse gap-2 border-t border-slate-100 px-5 py-3 sm:flex-row sm:justify-end">
                  {locked ? (
                    <>
                      <Button variant="ghost" onClick={() => setVisitFor(r)}>Start visit without history</Button>
                      <Button onClick={() => setConsentFor(r)} icon={<Smartphone className="size-4" />}>Request access from patient</Button>
                    </>
                  ) : (
                    <Button onClick={() => setVisitFor(r)} icon={<ArrowRight className="size-4" />}>Start visit</Button>
                  )}
                </div>
              </Card>
            )
          })}
        </div>

        <Card className="h-fit">
          <CardHeader title="Today at this hospital" subtitle="Updates automatically" />
          <div className="grid grid-cols-3 divide-x divide-slate-100 border-y border-slate-100">
            <Stat label="Triage" value={count(['awaiting_nursing', 'registered'])} />
            <Stat label="Doctor" value={count(['awaiting_doctor', 'awaiting_disposition', 'results_ready'])} />
            <Stat label="Lab" value={count(['awaiting_investigation'])} />
          </div>
          <div className="max-h-[520px] divide-y divide-slate-100 overflow-y-auto">
            {board.loading && !board.data && <SkeletonList rows={4} />}
            {board.data && enc.length === 0 && <p className="px-5 py-8 text-center text-sm text-slate-500">No patients in the hospital yet today.</p>}
            {enc.map((e) => (
              <div key={e.id} className="px-5 py-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-semibold text-slate-900">{e.patient_name}</span>
                  <StatusBadge status={e.status} />
                </div>
                <div className="mt-0.5 truncate text-sm text-slate-500">{e.reception_intake?.presenting_complaint}</div>
                <div className="mt-1 flex items-center justify-between text-xs text-slate-500">
                  <span className="inline-flex items-center gap-1"><Clock className="size-3.5" />Arrived {timeAgo(e.opened_at)}</span>
                  <PriorityBadge priority={e.priority} />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <ConsentFlow
        open={!!consentFor}
        target={consentFor}
        onClose={() => setConsentFor(null)}
        onApproved={() => {
          setConsentFor(null)
          toast({ tone: 'success', title: 'Records unlocked', description: 'Nurses and doctors here can now see her full history.' })
          search()
        }}
      />
      <StartVisit
        target={visitFor}
        onClose={() => setVisitFor(null)}
        onDone={(name) => {
          setVisitFor(null)
          board.reload(true)
          toast({ tone: 'success', title: `${name} sent to triage`, description: 'They now appear in the nurse’s queue.' })
        }}
      />
      <RegisterPatient
        open={registering}
        onClose={() => setRegistering(false)}
        onRegistered={(p) => {
          setRegistering(false)
          setQ(p.patient_number)
          search(p.patient_number)
          setVisitFor({ patient_id: p.id, full_name: `${p.first_name} ${p.last_name}`, patient_number: p.patient_number })
        }}
      />
    </div>
  )
}

type VisitTarget = { patient_id: string; full_name: string; patient_number: string; complaint?: string; referralId?: string; emergencyId?: string; emergency?: boolean }

function StartVisit({ target, onClose, onDone }: { target: VisitTarget | null; onClose: () => void; onDone: (name: string) => void }) {
  const { user } = useAuth()
  const [complaint, setComplaint] = useState('')
  const [visitType, setVisitType] = useState('walk_in')
  const [emergency, setEmergency] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loadedFor, setLoadedFor] = useState<VisitTarget | null>(null)

  // A referral arrives with its reason already captured on the patient's phone.
  if (target !== loadedFor) {
    setLoadedFor(target)
    if (target?.referralId || target?.emergencyId) { setComplaint(target.complaint ?? ''); setVisitType('referred'); setEmergency(!!target.emergency) }
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!target || !user?.facility_id) return
    setBusy(true); setError(null)
    try {
      await api('/encounters', {
        method: 'POST',
        json: {
          patient_id: target.patient_id, facility_id: user.facility_id, presenting_complaint: complaint,
          visit_type: emergency ? 'emergency_arrival' : visitType, arrival_mode: visitType === 'referred' ? 'referral' : 'walk_in',
          is_emergency_flag: emergency,
        },
      })
      if (target.referralId) await api(`/referrals/${target.referralId}/status`, { method: 'PATCH', json: { status: 'completed', facility_response_reason: 'Patient arrived and visit started' } })
      if (target.emergencyId) await api(`/emergency/requests/${target.emergencyId}/status`, { method: 'PATCH', json: { status: 'handed_over', details: 'Patient arrived and handed over to the emergency team' } })
      setComplaint(''); setEmergency(false); setVisitType('walk_in')
      onDone(target.full_name)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open={!!target} onClose={onClose}>
      {target && (
        <form onSubmit={submit} className="p-7">
          <h2 className="text-xl font-semibold text-slate-900">Start a visit</h2>
          <p className="mt-1 text-sm text-slate-500">{target.full_name} · <span className="font-mono">{target.patient_number}</span></p>
          <div className="mt-6 space-y-4">
            <Field label="Presenting complaint (in the patient’s words)">
              <Textarea required value={complaint} onChange={(e) => setComplaint(e.target.value)} placeholder="e.g. Headache and blurred vision for a week; very thirsty, passing urine often" autoFocus />
            </Field>
            <div className="flex flex-wrap gap-2">
              {['Persistent headache and blurred vision for 1 week; excessive thirst, frequent urination and tiredness', 'Fever, chills and body aches for 3 days', 'Cough and difficulty breathing'].map((s) => (
                <button type="button" key={s} onClick={() => setComplaint(s)} className="rounded-md border border-slate-200 px-2.5 py-1.5 text-left text-sm text-slate-700 hover:bg-slate-50">{s.length > 48 ? s.slice(0, 48) + '…' : s}</button>
              ))}
            </div>
            <Field label="Visit type">
              <Select value={visitType} onChange={(e) => setVisitType(e.target.value)}>
                <option value="walk_in">Walk-in</option>
                <option value="referred">Referred</option>
                <option value="scheduled">Scheduled appointment</option>
              </Select>
            </Field>
            <label className={clsx('flex cursor-pointer items-center gap-3 rounded-md border p-4 transition-colors', emergency ? 'border-rose-300 bg-rose-50' : 'border-slate-300')}>
              <input type="checkbox" checked={emergency} onChange={(e) => setEmergency(e.target.checked)} className="size-4 accent-rose-600" />
              <Siren className={clsx('size-5', emergency ? 'text-rose-600' : 'text-slate-400')} />
              <div>
                <div className="text-sm font-semibold text-slate-800">Emergency: bypass the queue</div>
                <div className="text-xs text-slate-500">Escalates priority for nursing and doctor immediately</div>
              </div>
            </label>
            <ErrorNote message={error} />
          </div>
          <div className="mt-6 flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
            <Button type="submit" loading={busy} icon={<HeartPulse className="size-4" />}>Send to triage</Button>
          </div>
        </form>
      )}
    </Modal>
  )
}

function RegisterPatient({ open, onClose, onRegistered }: { open: boolean; onClose: () => void; onRegistered: (p: PatientProfile) => void }) {
  const [f, setF] = useState({ first_name: '', last_name: '', gender: 'Female', dob: '', phone: '', address: '', blood_group: '', genotype: '', allergies: '', emergency_contact_name: '', emergency_contact_phone: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [created, setCreated] = useState<PatientProfile | null>(null)
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value })

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      const p = await api<PatientProfile>('/patients', {
        method: 'POST',
        json: { ...f, allergies: f.allergies ? f.allergies.split(',').map((s) => s.trim()).filter(Boolean) : [], blood_group: f.blood_group || null, genotype: f.genotype || null },
      })
      setCreated(p)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function close() { setCreated(null); onClose() }

  return (
    <Modal open={open} onClose={close} width="max-w-2xl">
      {created ? (
        <div className="p-10 text-center">
          <CheckCircle2 className="mx-auto size-14 text-brand-500" />
          <h2 className="mt-4 text-xl font-semibold">Patient registered on VITALIS</h2>
          <p className="mt-1 text-sm text-slate-500">This ID works at every connected hospital.</p>
          <div className="mx-auto mt-6 w-fit rounded-lg bg-brand-900 px-8 py-5 text-white">
            <div className="text-xs text-brand-300">VITALIS ID</div>
            <div className="font-mono text-3xl font-bold tracking-wider">{created.patient_number}</div>
          </div>
          <Button className="mt-8" onClick={() => { const p = created; setCreated(null); onRegistered(p) }} icon={<ArrowRight className="size-4" />}>Continue to start visit</Button>
        </div>
      ) : (
        <form onSubmit={submit} className="p-7">
          <h2 className="text-xl font-semibold text-slate-900">Register a new patient</h2>
          <p className="mt-1 text-sm text-slate-500">Captured once, reused at every VITALIS facility.</p>
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <Field label="First name"><Input required value={f.first_name} onChange={set('first_name')} /></Field>
            <Field label="Last name"><Input required value={f.last_name} onChange={set('last_name')} /></Field>
            <Field label="Sex"><Select value={f.gender} onChange={set('gender')}><option>Female</option><option>Male</option></Select></Field>
            <Field label="Date of birth"><Input required type="date" value={f.dob} onChange={set('dob')} /></Field>
            <Field label="Phone (for consent codes)"><Input required value={f.phone} onChange={set('phone')} placeholder="+234-80…" /></Field>
            <Field label="Address"><Input value={f.address} onChange={set('address')} /></Field>
            <Field label="Blood group"><Select value={f.blood_group} onChange={set('blood_group')}><option value="">Unknown</option>{['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'].map((b) => <option key={b}>{b}</option>)}</Select></Field>
            <Field label="Genotype"><Select value={f.genotype} onChange={set('genotype')}><option value="">Unknown</option>{['AA', 'AS', 'SS', 'AC', 'SC'].map((b) => <option key={b}>{b}</option>)}</Select></Field>
            <Field label="Known allergies (comma-separated)" className="sm:col-span-2"><Input value={f.allergies} onChange={set('allergies')} placeholder="e.g. Penicillin" /></Field>
            <Field label="Emergency contact"><Input value={f.emergency_contact_name} onChange={set('emergency_contact_name')} /></Field>
            <Field label="Emergency contact phone"><Input value={f.emergency_contact_phone} onChange={set('emergency_contact_phone')} /></Field>
          </div>
          <div className="mt-4"><ErrorNote message={error} /></div>
          <div className="mt-6 flex items-center justify-between gap-2">
            <span className="flex items-center gap-1.5 text-xs text-slate-400"><Building2 className="size-3.5" /> A VITALIS ID is generated automatically</span>
            <div className="flex gap-2">
              <Button type="button" variant="ghost" onClick={close}>Cancel</Button>
              <Button type="submit" loading={busy} icon={<UserPlus className="size-4" />}>Register</Button>
            </div>
          </div>
        </form>
      )}
    </Modal>
  )
}
