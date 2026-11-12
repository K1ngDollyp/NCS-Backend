import clsx from 'clsx'
import { AlertTriangle, ArrowLeft, ArrowRight, CheckCircle2, Clock, FileSignature, FlaskConical, History, Lock, Pill, Plus, ScanLine, ShieldAlert, ShieldCheck, Sparkles, Stethoscope } from 'lucide-react'
import { useCallback, useMemo, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { AIAssessmentPanel } from '../components/AIAssessment'
import { FamilyHistory, LabFlagValue, LabHistory, NetworkFacilities, NetworkTimeline, PatientBanner, TrendChart, VitalTiles } from '../components/clinical'
import { ConsentFlow } from '../components/ConsentFlow'
import { Badge, Button, Card, CardHeader, EmptyState, ErrorNote, Field, Input, Modal, PageHeader, PriorityBadge, Select, Skeleton, SkeletonList, StatusBadge, Textarea, useToast } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { fmtTime, timeAgo, VITAL_BY_KEY } from '../lib/format'
import { useResource } from '../lib/hooks'
import type { Assessment, Encounter, UnifiedRecord } from '../lib/types'

/* =============================================================== Queue */
export function DoctorQueue() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const queue = useResource<Encounter[]>(user?.facility_id ? `/encounters/queue/doctor?facility_id=${user.facility_id}` : null, { poll: 4000 })
  const list = queue.data ?? []

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader eyebrow="Doctor" title="Patients waiting to see you" subtitle="Most urgent first. Open a patient to see their history from every hospital and run VITALIS AI." />
      <Card>
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3 text-sm text-slate-500">
          <span>{queue.data ? `${list.length} patient${list.length === 1 ? '' : 's'} waiting` : 'Loading…'}</span>
          <span>Updates automatically</span>
        </div>
        <div className="divide-y divide-slate-100">
          {queue.loading && !queue.data && <SkeletonList rows={3} />}
          {queue.data && list.length === 0 && <EmptyState icon={<Stethoscope />} title="No one waiting" description="Patients appear here once the nurse sends them to you." />}
          {list.map((e) => {
            const warn = e.nursing_observations.filter((v) => v.is_warning)
            const sbp = e.nursing_observations.find((v) => v.observation_type === 'systolic_bp')?.value
            const dbp = e.nursing_observations.find((v) => v.observation_type === 'diastolic_bp')?.value
            return (
              <button
                key={e.id}
                onClick={() => navigate(`/doctor/encounter/${e.id}`)}
                className={clsx('group flex w-full items-center gap-4 border-l-4 px-5 py-4 text-left transition-colors duration-150 hover:bg-slate-50',
                  e.priority === 'emergency' ? 'border-l-rose-600' : e.priority === 'urgent' ? 'border-l-amber-500' : 'border-l-transparent')}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span className="text-lg font-semibold text-slate-900">{e.patient_name}</span>
                    <span className="font-mono text-sm text-slate-500">{e.patient_number}</span>
                    <PriorityBadge priority={e.priority} />
                    {e.status === 'results_ready' && <StatusBadge status={e.status} />}
                  </div>
                  <div className="mt-0.5 truncate text-base text-slate-600">{e.reception_intake?.presenting_complaint}</div>
                  {(sbp || warn.length > 0) && (
                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm tabular">
                      {sbp && <span className={clsx(sbp >= 140 ? 'font-semibold text-rose-700' : 'text-slate-600')}>BP {sbp}/{dbp}</span>}
                      {warn.filter((w) => !w.observation_type.includes('bp')).map((w) => <span key={w.observation_type} className="font-semibold text-rose-700">{VITAL_BY_KEY[w.observation_type]?.short ?? w.observation_type} {w.value}</span>)}
                    </div>
                  )}
                </div>
                <div className="hidden shrink-0 items-center gap-1 text-sm text-slate-500 sm:flex"><Clock className="size-4" />{timeAgo(e.opened_at)}</div>
                <ArrowRight className="size-5 shrink-0 text-slate-300 transition-colors group-hover:text-brand-700" />
              </button>
            )
          })}
        </div>
      </Card>
    </div>
  )
}

/* =============================================================== Workspace */
const RADIOLOGY = /x-ray|xray|ultrasound|\bct\b|mri|echocardio|scan/i
const LAB = /hba1c|glucose|urinalysis|creatinine|electrolyte|urea|lipid|blood count|fbc|rdt|film|culture|sputum|ketone|egfr|malaria|widal|profile|troponin/i

export function DoctorWorkspace() {
  const { id } = useParams()
  const { user } = useAuth()
  const toast = useToast()
  const enc = useResource<Encounter>(`/encounters/${id}`, { poll: 6000 })
  const rec = useResource<UnifiedRecord>(enc.data ? `/records/patients/${enc.data.patient_id}` : null)
  const [assessment, setAssessment] = useState<Assessment | null>(null)
  const [consentOpen, setConsentOpen] = useState(false)
  const [orderOpen, setOrderOpen] = useState(false)
  const [noteDraft, setNoteDraft] = useState<NoteDraft | null>(null)
  const [runSignal, setRunSignal] = useState(0)

  const previous = useMemo(() => {
    const m: Record<string, { value: number; facility: string; date: string }> = {}
    for (const v of rec.data?.vitals_series ?? []) {
      if (v.encounter_id === id) continue
      m[v.observation_type] = { value: v.value, facility: v.facility_name, date: v.measured_at }
    }
    return m
  }, [rec.data, id])

  const placeOrder = useCallback(async (test: string, department?: 'laboratory' | 'radiology', indication?: string, priority = 'routine') => {
    if (!enc.data) return
    const dept = department ?? (RADIOLOGY.test(test) ? 'radiology' : LAB.test(test) ? 'laboratory' : null)
    if (!dept) {
      setNoteDraft((d) => ({ ...(d ?? emptyNote(enc.data!)), plan: `${(d ?? emptyNote(enc.data!)).plan}\n• ${test}`.trim() }))
      toast({ tone: 'info', title: `${test} added to your plan`, description: 'This is done at the bedside, so it goes into the clinical note.' })
      return
    }
    try {
      await api(`/encounters/${enc.data.id}/investigation-orders`, {
        method: 'POST',
        json: { department: dept, test_or_modality: test, clinical_indication: indication ?? enc.data.reception_intake?.presenting_complaint, priority },
      })
      toast({ tone: 'success', title: `${test} ordered`, description: `Sent to the ${dept === 'laboratory' ? 'lab' : 'imaging'} worklist.` })
      enc.reload(true)
    } catch (e) {
      toast({ tone: 'error', title: 'Could not place the order', description: (e as Error).message })
    }
  }, [enc, toast])

  const onAssessment = useCallback((a: Assessment) => setAssessment(a), [])

  if (enc.loading && !enc.data) return <WorkspaceSkeleton />
  if (!enc.data) return <ErrorNote message={enc.error} />
  const e = enc.data
  const r = rec.data
  const locked = r?.access.level === 'facility_only' && r.access.hidden_encounters > 0
  const prior = r ? r.encounters.filter((x) => x.id !== e.id) : []
  const otherHospitals = new Set(prior.map((x) => x.facility_id)).size
  const completed = e.status === 'completed'
  const abnormal = e.nursing_observations.filter((v) => v.is_warning).length

  return (
    <div className="mx-auto max-w-[1440px] space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Link to="/doctor" className="inline-flex h-9 items-center gap-1.5 rounded-md text-sm font-medium text-slate-600 hover:text-slate-900"><ArrowLeft className="size-4" />All patients</Link>
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <span className="font-mono">{e.encounter_number}</span>
          <PriorityBadge priority={e.priority} />
          <StatusBadge status={e.status} />
        </div>
      </div>

      {r ? (
        <PatientBanner
          patient={r.patient}
          access={r.access}
          extra={locked ? <Button variant="secondary" size="sm" onClick={() => setConsentOpen(true)} icon={<Lock className="size-4" />}>Ask patient for access</Button> : undefined}
        />
      ) : <Card className="space-y-2 p-5"><Skeleton className="h-6 w-1/3" /><Skeleton className="h-4 w-1/2" /></Card>}

      {e.status === 'results_ready' && (
        <div className="flex items-center gap-3 rounded-md border border-brand-200 bg-brand-50 px-4 py-3 text-base text-brand-900 animate-slide-up" role="status">
          <FlaskConical className="size-5 shrink-0 text-brand-700" /><span><b>New results are ready.</b> The lab has verified them. See Tests below.</span>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        {/* ---------------- Main column */}
        <div className="min-w-0 space-y-4">
          <Card>
            <div className="flex flex-wrap items-start justify-between gap-3 px-5 pt-4 pb-3">
              <div className="min-w-0">
                <div className="text-sm text-slate-500">Today at {e.facility_name.replace(', Abeokuta', '')} · arrived {fmtTime(e.opened_at)}</div>
                <p className="mt-1 text-lg font-medium text-slate-900">{e.reception_intake?.presenting_complaint}</p>
              </div>
              {!assessment && (
                <Button variant="ai" onClick={() => setRunSignal((n) => n + 1)} icon={<Sparkles className="size-4" />}>Run VITALIS AI</Button>
              )}
            </div>
            <div className="flex items-center justify-between px-5 pb-2 text-sm">
              <span className="font-medium text-slate-700">Vital signs {e.nursing_observations[0] && <span className="font-normal text-slate-500">· taken {fmtTime(e.nursing_observations[0].measured_at)}</span>}</span>
              {abnormal > 0 && <span className="inline-flex items-center gap-1 font-semibold text-rose-700"><AlertTriangle className="size-4" />{abnormal} abnormal</span>}
            </div>
            <VitalTiles vitals={e.nursing_observations} previous={previous} />
          </Card>

          <AIAssessmentPanel
            encounterId={e.id}
            priorVisits={prior.length}
            facilities={otherHospitals}
            assessment={assessment}
            onAssessment={onAssessment}
            onOrder={(t) => placeOrder(t)}
            onUseInNote={(a) => setNoteDraft(draftFromAI(e, a))}
            disabledReason={locked ? 'Records from other hospitals are locked, so only this hospital’s data will be used.' : null}
            runSignal={runSignal}
          />

          <Investigations encounter={e} onNew={() => setOrderOpen(true)} />

          {!completed ? (
            <NoteEditor encounter={e} draft={noteDraft} setDraft={setNoteDraft} onSigned={(discharged) => { setNoteDraft(null); enc.reload(true); rec.reload(true); if (discharged) toast({ tone: 'success', title: 'Visit completed' }) }} patientId={e.patient_id} />
          ) : (
            <Card className="flex items-start gap-3 p-5">
              <CheckCircle2 className="size-6 shrink-0 text-emerald-600" />
              <div>
                <div className="font-semibold text-slate-900">Visit completed and signed</div>
                <p className="text-sm text-slate-500">This visit is now part of her VITALIS record, available to any hospital she approves.</p>
              </div>
            </Card>
          )}
        </div>

        {/* ---------------- History column */}
        <div className="min-w-0 space-y-4">
          {r ? (
            <>
              <Card>
                <CardHeader title="History from other hospitals" subtitle={`${prior.length} earlier visit${prior.length === 1 ? '' : 's'}`} icon={<History />} />
                <div className="px-5 pb-3"><NetworkFacilities record={r} hereFacilityId={user?.facility_id} /></div>
                <div className="max-h-[560px] overflow-y-auto border-t border-slate-100 pt-4">
                  <NetworkTimeline record={r} currentEncounterId={e.id} hereFacilityId={user?.facility_id} />
                </div>
              </Card>
              {!locked && (
                <>
                  <TrendChart record={r} metric="systolic_bp" secondary="diastolic_bp" title="Blood pressure over time" unit="mmHg" normalMax={140} />
                  <TrendChart record={r} metric="weight" title="Weight over time" unit="kg" />
                  <Card>
                    <CardHeader title="Lab results" icon={<FlaskConical />} subtitle="All hospitals, newest first" />
                    <LabHistory record={r} />
                  </Card>
                  <FamilyHistory record={r} />
                </>
              )}
            </>
          ) : <Card><SkeletonList rows={3} /></Card>}
        </div>
      </div>

      {r && (
        <ConsentFlow
          open={consentOpen}
          target={{ patient_id: r.patient.id, full_name: r.patient.full_name, masked_phone: r.patient.phone ? `${r.patient.phone.slice(0, 4)}*****${r.patient.phone.slice(-3)}` : null, external_facilities: r.access.hidden_facilities, network_encounters: r.access.hidden_encounters }}
          onClose={() => setConsentOpen(false)}
          onApproved={() => { setConsentOpen(false); rec.reload() }}
        />
      )}
      <OrderModal open={orderOpen} onClose={() => setOrderOpen(false)} onSubmit={async (t, d, i, p) => { await placeOrder(t, d, i, p); setOrderOpen(false) }} />
    </div>
  )
}

function WorkspaceSkeleton() {
  return (
    <div className="mx-auto max-w-[1440px] space-y-4" aria-busy="true" aria-label="Opening patient">
      <Card className="space-y-2 p-5"><Skeleton className="h-7 w-1/3" /><Skeleton className="h-4 w-1/2" /><Skeleton className="h-4 w-2/3" /></Card>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Card className="space-y-3 p-5"><Skeleton className="h-5 w-3/4" /><div className="grid grid-cols-3 gap-3"><Skeleton className="h-20" /><Skeleton className="h-20" /><Skeleton className="h-20" /></div></Card>
        <Card><SkeletonList rows={3} /></Card>
      </div>
    </div>
  )
}

/* --------------------------------------------------------------- Tests */
function Investigations({ encounter, onNew }: { encounter: Encounter; onNew: () => void }) {
  const orders = encounter.investigation_orders
  return (
    <Card>
      <CardHeader title="Tests" subtitle="Orders go straight to the lab and imaging worklists." icon={<FlaskConical />} action={<Button variant="secondary" size="sm" onClick={onNew} icon={<Plus className="size-4" />}>Order a test</Button>} />
      <div className="border-t border-slate-100">
        {orders.length === 0 && <p className="px-5 py-4 text-sm text-slate-500">No tests ordered for this visit yet.</p>}
        <div className="divide-y divide-slate-100">
          {orders.map((o) => (
            <div key={o.id} className="px-5 py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2.5">
                  {o.department === 'radiology' ? <ScanLine className="size-4 text-slate-400" /> : <FlaskConical className="size-4 text-slate-400" />}
                  <span className="font-semibold text-slate-900">{o.test_or_modality}</span>
                  <span className="font-mono text-xs text-slate-500">{o.order_number}</span>
                </div>
                <div className="flex items-center gap-2">
                  {o.priority !== 'routine' && <Badge tone="amber">{o.priority === 'stat' ? 'STAT' : 'Urgent'}</Badge>}
                  <StatusBadge status={o.status} />
                </div>
              </div>
              {o.lab_result && (
                <div className="mt-2 divide-y divide-slate-100 rounded-md border border-slate-200">
                  {Object.entries(o.lab_result.result_payload).map(([k, v]) => (
                    <div key={k} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                      <span className="text-slate-700">{k} {v.reference_range && <span className="text-slate-500">(normal {v.reference_range})</span>}</span>
                      <LabFlagValue v={v} />
                    </div>
                  ))}
                  {o.lab_result.verified_by && <div className="flex items-center gap-1.5 px-3 py-2 text-xs text-emerald-700"><ShieldCheck className="size-3.5" />Verified by {o.lab_result.verified_by}</div>}
                </div>
              )}
              {o.radiology_report && (
                <div className="mt-2 rounded-md border border-slate-200 p-3 text-sm">
                  <p><span className="font-semibold">Findings:</span> {o.radiology_report.findings}</p>
                  <p className="mt-1"><span className="font-semibold">Impression:</span> {o.radiology_report.impression}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </Card>
  )
}

const COMMON_TESTS = ['HbA1c', 'Fasting Blood Glucose', 'Urinalysis', 'Serum Electrolytes, Urea & Creatinine', 'Lipid Profile', 'Full Blood Count', 'Malaria RDT', 'Chest X-Ray (PA)', 'Abdominal Ultrasound']

function OrderModal({ open, onClose, onSubmit }: { open: boolean; onClose: () => void; onSubmit: (t: string, d: 'laboratory' | 'radiology', i: string, p: string) => Promise<void> }) {
  const [test, setTest] = useState('')
  const [dept, setDept] = useState<'laboratory' | 'radiology'>('laboratory')
  const [ind, setInd] = useState('')
  const [prio, setPrio] = useState('routine')
  const [busy, setBusy] = useState(false)
  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    try { await onSubmit(test, dept, ind, prio); setTest(''); setInd('') } finally { setBusy(false) }
  }
  return (
    <Modal open={open} onClose={onClose} label="Order a test">
      <form onSubmit={submit} className="p-6">
        <h2 className="text-xl font-semibold text-slate-900">Order a test</h2>
        <div className="mt-5 space-y-4">
          <Field label="Test">
            <Input required list="tests" value={test} onChange={(e) => { setTest(e.target.value); if (RADIOLOGY.test(e.target.value)) setDept('radiology') }} placeholder="Start typing, e.g. HbA1c" />
            <datalist id="tests">{COMMON_TESTS.map((t) => <option key={t} value={t} />)}</datalist>
          </Field>
          <Field label="Department">
            <Select value={dept} onChange={(e) => setDept(e.target.value as 'laboratory' | 'radiology')}><option value="laboratory">Laboratory</option><option value="radiology">Imaging (radiology)</option></Select>
          </Field>
          <Field label="Reason for the test"><Input value={ind} onChange={(e) => setInd(e.target.value)} placeholder="e.g. Confirm suspected type 2 diabetes" /></Field>
          <Field label="How urgent"><Select value={prio} onChange={(e) => setPrio(e.target.value)}><option value="routine">Routine</option><option value="urgent">Urgent</option><option value="stat">STAT (immediately)</option></Select></Field>
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={busy}>Place order</Button>
        </div>
      </form>
    </Modal>
  )
}

/* --------------------------------------------------------------- Clinical note */
interface NoteDraft {
  history: string
  exam: string
  assessment: string
  differentials: string[]
  plan: string
  disposition: string
  aiAssisted: boolean
  aiRaw?: string
}

function emptyNote(e: Encounter): NoteDraft {
  return { history: e.reception_intake?.presenting_complaint ?? '', exam: '', assessment: '', differentials: [], plan: '', disposition: 'outpatient', aiAssisted: false }
}

function draftFromAI(e: Encounter, a: Assessment): NoteDraft {
  const safe = a.medication_options.filter((m) => m.safety === 'ok')
  const avoid = a.medication_options.filter((m) => m.safety === 'avoid')
  const plan = [
    ...a.red_flags.map((f) => `URGENT: ${f.action}`),
    ...a.conditions.slice(0, 2).flatMap((c) => c.recommended_investigations.slice(0, 3)).filter((v, i, arr) => arr.indexOf(v) === i).map((t) => `Test: ${t}`),
    ...safe.slice(0, 2).map((m) => `Consider: ${m.drug}`),
    ...avoid.map((m) => `AVOID ${m.drug.split(' ')[0]}: ${m.alerts[0] ?? 'contraindicated'}`),
    'Review with results; home blood pressure monitoring.',
  ]
  return {
    history: e.reception_intake?.presenting_complaint ?? '',
    exam: '',
    assessment: a.conditions.map((c) => `${c.condition} (${c.likelihood_label.toLowerCase()} likelihood)`).join('; '),
    differentials: a.conditions.map((c) => c.condition),
    plan: plan.map((p) => `• ${p}`).join('\n'),
    disposition: 'outpatient',
    aiAssisted: true,
    aiRaw: a.summary,
  }
}

/** Demo shortcut: a realistic examination finding for the demo patient. */
const DEMO_EXAM = 'Fundoscopy: grade II hypertensive retinopathy (AV nipping), no papilloedema. Chest clear. Heart sounds normal. No pedal oedema.'

function NoteEditor({ encounter, draft, setDraft, onSigned, patientId }: { encounter: Encounter; draft: NoteDraft | null; setDraft: (d: NoteDraft) => void; onSigned: (discharged: boolean) => void; patientId: string }) {
  const toast = useToast()
  const d = draft ?? emptyNote(encounter)
  const set = (k: keyof NoteDraft) => (ev: { target: { value: string } }) => setDraft({ ...d, [k]: ev.target.value })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [meds, setMeds] = useState('')
  const [medResult, setMedResult] = useState<{ is_safe_to_proceed: boolean; allergy_conflicts: { warning: string }[]; drug_interactions: { interacting_pair: string; severity: string; clinical_significance: string }[]; contraindications_and_warnings: { warning: string }[] } | null>(null)
  const [checking, setChecking] = useState(false)
  const signedNotes = encounter.clinical_notes.filter((n) => n.signed_at)

  async function checkMeds() {
    setChecking(true)
    try {
      setMedResult(await api('/intelligence/medication-safety-check', { method: 'POST', json: { patient_id: patientId, proposed_medications: meds.split(',').map((m) => m.trim()).filter(Boolean) } }))
    } finally {
      setChecking(false)
    }
  }

  async function sign() {
    setBusy(true); setError(null)
    try {
      const plan = meds ? `${d.plan}\nPrescribed: ${meds}` : d.plan
      await api(`/encounters/${encounter.id}/clinical-notes`, {
        method: 'POST',
        json: {
          history_of_complaint: d.history, examination_findings: d.exam, assessment: d.assessment,
          differential_considerations: d.differentials, clinical_plan: plan, disposition: d.disposition,
          is_draft: false, is_ai_assisted: d.aiAssisted, ai_raw_draft: d.aiRaw ?? null,
        },
      })
      toast({ tone: 'success', title: 'Note signed', description: d.disposition === 'discharged' ? 'The visit is complete and saved to her record.' : 'Saved to her record. The visit stays open for results.' })
      setMeds(''); setMedResult(null)
      onSigned(d.disposition === 'discharged')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader
        title="Clinical note"
        subtitle="You review, edit and sign. Nothing from VITALIS AI enters the record until you sign."
        icon={<FileSignature />}
        action={d.aiAssisted ? <Badge tone="ai" icon={<Sparkles />}>Drafted from the AI suggestions you accepted</Badge> : undefined}
      />
      <div className="space-y-4 border-t border-slate-100 px-5 py-4">
        {signedNotes.length > 0 && (
          <div className="flex items-start gap-2 rounded-md bg-emerald-50 px-3 py-2.5 text-sm text-emerald-800">
            <CheckCircle2 className="mt-0.5 size-4 shrink-0" />
            <span><b>{signedNotes.length} note{signedNotes.length > 1 ? 's' : ''} already signed</b> for this visit. Write a new note to add results or discharge.</span>
          </div>
        )}
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="History of the complaint"><Textarea value={d.history} onChange={set('history')} /></Field>
          <Field label="Examination findings" hint={!d.exam ? <button type="button" className="font-medium text-brand-700 hover:underline" onClick={() => setDraft({ ...d, exam: DEMO_EXAM })}>Use demo finding</button> : undefined}>
            <Textarea value={d.exam} onChange={set('exam')} placeholder="What you found on examination" />
          </Field>
        </div>
        <Field label="Assessment"><Textarea value={d.assessment} onChange={set('assessment')} className="!min-h-[64px]" placeholder="Your impression of what is going on" /></Field>
        <Field label="Plan"><Textarea value={d.plan} onChange={set('plan')} className="!min-h-[120px] font-mono !text-sm" placeholder="Tests, treatment, follow-up" /></Field>

        <div className="rounded-md border border-slate-200 p-4">
          <div className="mb-2 flex items-center gap-2 text-base font-semibold text-slate-900"><Pill className="size-4 text-slate-400" />Prescribe</div>
          <p className="mb-2 text-sm text-slate-500">Checked against her allergies and medicines from every hospital before you sign.</p>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input value={meds} onChange={(e) => { setMeds(e.target.value); setMedResult(null) }} placeholder="e.g. Lisinopril 10 mg once daily" />
            <Button variant="secondary" onClick={checkMeds} loading={checking} disabled={!meds.trim()} icon={<ShieldCheck className="size-4" />}>Check safety</Button>
          </div>
          {medResult && (
            <div role="status" className={clsx('mt-3 rounded-md border p-3 text-sm animate-fade-in', medResult.is_safe_to_proceed ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-rose-200 bg-rose-50 text-rose-800')}>
              <div className="flex items-center gap-2 font-semibold">{medResult.is_safe_to_proceed ? <><CheckCircle2 className="size-4" />No conflict with her record</> : <><ShieldAlert className="size-4" />Do not prescribe: conflict found</>}</div>
              {medResult.allergy_conflicts.map((c, i) => <div key={i} className="mt-1">{c.warning}</div>)}
              {medResult.drug_interactions.map((c, i) => <div key={i} className="mt-1">{c.severity}: {c.interacting_pair}. {c.clinical_significance}</div>)}
              {medResult.contraindications_and_warnings.map((c, i) => <div key={i} className="mt-1">{c.warning}</div>)}
            </div>
          )}
        </div>

        <div className="flex flex-col gap-4 border-t border-slate-100 pt-4 sm:flex-row sm:items-end sm:justify-between">
          <Field label="After this note" className="sm:w-72">
            <Select value={d.disposition} onChange={set('disposition')}>
              <option value="outpatient">Keep visit open, waiting for results</option>
              <option value="discharged">Discharge and complete the visit</option>
              <option value="admitted">Admit to ward</option>
              <option value="referred">Refer to a specialist</option>
            </Select>
          </Field>
          <div className="flex flex-col items-stretch gap-2 sm:items-end">
            <ErrorNote message={error} />
            <Button size="lg" onClick={sign} loading={busy} disabled={!d.assessment.trim()} icon={<FileSignature className="size-4" />}>Sign note</Button>
            {!d.assessment.trim() && <span className="text-xs text-slate-500">Write an assessment first, or accept the AI draft above.</span>}
          </div>
        </div>
      </div>
    </Card>
  )
}
