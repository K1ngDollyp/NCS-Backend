import clsx from 'clsx'
import { AlertTriangle, ArrowRight, Clock, HeartPulse, Lock, UserRound, Wand2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { FacilityChip } from '../components/clinical'
import { Badge, Button, Card, CardHeader, EmptyState, ErrorNote, PageHeader, PriorityBadge, SkeletonList, Textarea, useToast } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { shortFacility, timeAgo, VITALS, vitalStatus } from '../lib/format'
import { useResource } from '../lib/hooks'
import type { Encounter, UnifiedRecord } from '../lib/types'

/** Readings for the demo patient, so the presenter never types on stage. */
const DEMO_VALUES: Record<string, string> = {
  systolic_bp: '174', diastolic_bp: '108', pulse_rate: '96', respiratory_rate: '18', temperature: '36.8',
  spo2: '97', blood_glucose: '236', pain_score: '4', weight: '84', height: '162',
}

export default function Nursing() {
  const { user } = useAuth()
  const queue = useResource<Encounter[]>(user?.facility_id ? `/encounters/queue/nursing?facility_id=${user.facility_id}` : null, { poll: 4000 })
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const list = queue.data ?? []
  const selected = list.find((e) => e.id === selectedId) ?? null

  useEffect(() => {
    if (!selectedId && list.length) setSelectedId(list[list.length - 1].id)
  }, [list, selectedId])

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader eyebrow="Nursing" title="Record vital signs" subtitle="Enter readings once. The doctor sees them straight away, next to this patient's readings from other hospitals." />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[300px_1fr]">
        <Card className="h-fit">
          <CardHeader title="Waiting for you" subtitle={queue.data ? `${list.length} patient${list.length === 1 ? '' : 's'}` : undefined} />
          <div className="divide-y divide-slate-100 border-t border-slate-100">
            {queue.loading && !queue.data && <SkeletonList rows={3} />}
            {queue.data && list.length === 0 && <EmptyState icon={<HeartPulse />} title="No one waiting" description="Patients sent by reception appear here automatically." />}
            {list.map((e) => (
              <button
                key={e.id}
                onClick={() => setSelectedId(e.id)}
                aria-current={e.id === selectedId}
                className={clsx('block w-full border-l-[3px] px-4 py-3 text-left transition-colors duration-150', e.id === selectedId ? 'border-brand-700 bg-brand-50' : 'border-transparent hover:bg-slate-50')}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-slate-900">{e.patient_name}</span>
                  <PriorityBadge priority={e.priority} />
                </div>
                <div className="mt-0.5 line-clamp-2 text-sm text-slate-500">{e.reception_intake?.presenting_complaint}</div>
                <div className="mt-1 flex items-center gap-1 text-xs text-slate-500"><Clock className="size-3.5" />Waiting {timeAgo(e.opened_at).replace(' ago', '')}</div>
              </button>
            ))}
          </div>
        </Card>

        {selected ? (
          <VitalsForm key={selected.id} encounter={selected} onDone={() => { setSelectedId(null); queue.reload(true) }} />
        ) : (
          <Card><EmptyState icon={<UserRound />} title="Choose a patient" description="Select someone from the list to record their vital signs." /></Card>
        )}
      </div>
    </div>
  )
}

function VitalsForm({ encounter, onDone }: { encounter: Encounter; onDone: () => void }) {
  const toast = useToast()
  const record = useResource<UnifiedRecord>(`/records/patients/${encounter.patient_id}`)
  const [values, setValues] = useState<Record<string, string>>({})
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const previous = useMemo(() => {
    const m: Record<string, { value: number; facility: string; date: string }> = {}
    for (const v of record.data?.vitals_series ?? []) {
      if (v.encounter_id === encounter.id) continue
      m[v.observation_type] = { value: v.value, facility: v.facility_name, date: v.measured_at }
    }
    return m
  }, [record.data, encounter.id])

  const entered = VITALS.filter((v) => values[v.key] !== undefined && values[v.key] !== '')
  const abnormal = entered.filter((v) => ['high', 'low'].includes(vitalStatus(v.key, parseFloat(values[v.key]))))
  const bmi = values.weight && values.height ? parseFloat(values.weight) / (parseFloat(values.height) / 100) ** 2 : null

  async function submit() {
    setBusy(true); setError(null)
    try {
      await api(`/encounters/${encounter.id}/observations`, {
        method: 'POST',
        json: {
          observations: entered.map((v) => ({ observation_type: v.key, value: parseFloat(values[v.key]), unit: v.unit })),
          general_nurse_note: note || null,
          handover_to_doctor: true,
        },
      })
      toast({ tone: 'success', title: `${encounter.patient_name} sent to the doctor`, description: abnormal.length ? `${abnormal.length} abnormal reading(s) flagged. Priority raised to urgent.` : 'All readings within normal range.' })
      onDone()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const p = record.data?.patient
  const locked = record.data?.access.level === 'facility_only' && record.data.access.hidden_encounters > 0

  return (
    <div className="min-w-0 space-y-4 animate-fade-in">
      <Card className="px-5 py-4">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h2 className="text-xl font-semibold text-slate-900">{encounter.patient_name}</h2>
          <span className="font-mono text-sm font-semibold text-slate-600">{encounter.patient_number}</span>
          <PriorityBadge priority={encounter.priority} />
        </div>
        {p && <div className="mt-0.5 text-sm text-slate-500">{p.gender}, {p.age} yrs · Blood {p.blood_group ?? 'unknown'} · Genotype {p.genotype ?? 'unknown'}</div>}
        <p className="mt-3 text-base text-slate-800"><span className="text-slate-500">Complaint: </span>{encounter.reception_intake?.presenting_complaint}</p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {p?.allergies.map((a) => <Badge key={a} tone="rose" icon={<AlertTriangle />} className="!h-auto !py-1 !whitespace-normal">Allergy: {a}</Badge>)}
          {record.data && record.data.facilities.filter((f) => f.facility_id !== encounter.facility_id).map((f) => <FacilityChip key={f.facility_id} name={f.facility_name} />)}
          {locked && <Badge tone="amber" icon={<Lock />}>History at other hospitals locked</Badge>}
        </div>
      </Card>

      <Card>
        <CardHeader
          title="Vital signs"
          subtitle="Readings outside the normal range turn red as you type."
          action={<Button variant="ghost" size="sm" onClick={() => setValues(DEMO_VALUES)} icon={<Wand2 className="size-4" />}>Fill demo readings</Button>}
        />
        <div className="grid grid-cols-2 border-y border-slate-100 xl:grid-cols-3">
          {VITALS.map((v) => {
            const raw = values[v.key] ?? ''
            const status = vitalStatus(v.key, raw === '' ? null : parseFloat(raw))
            const bad = status === 'high' || status === 'low'
            const prev = previous[v.key]
            return (
              <label key={v.key} htmlFor={v.key} className={clsx('block cursor-text px-4 py-3 shadow-[inset_-1px_-1px_0_var(--color-slate-100)] transition-colors duration-150', bad ? 'bg-rose-50' : 'bg-white')}>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-slate-700">{v.label}</span>
                  {bad && <span className="text-xs font-semibold text-rose-700">{status === 'high' ? 'High' : 'Low'}</span>}
                  {status === 'normal' && v.min !== undefined && <span className="text-xs font-semibold text-emerald-700">Normal</span>}
                </div>
                <div className="mt-1 flex items-baseline gap-1.5">
                  <input
                    id={v.key}
                    type="number"
                    step={v.step ?? 1}
                    inputMode="decimal"
                    value={raw}
                    placeholder="—"
                    onChange={(e) => setValues({ ...values, [v.key]: e.target.value })}
                    className={clsx('w-full min-w-0 bg-transparent text-3xl font-semibold tabular outline-none placeholder:font-normal placeholder:text-slate-300', bad ? 'text-rose-700' : 'text-slate-900')}
                  />
                  <span className="shrink-0 text-sm text-slate-500">{v.displayUnit}</span>
                </div>
                <div className="mt-1 space-y-0.5 text-xs text-slate-500">
                  <div>{v.min !== undefined ? `Normal ${v.min}–${v.max}` : 'Used for BMI'}</div>
                  {prev && <div className="truncate" title={`${prev.facility}`}>Last {prev.value} · {shortFacility(prev.facility).split(',')[0]}</div>}
                </div>
              </label>
            )
          })}
        </div>
        {bmi !== null && Number.isFinite(bmi) && (
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3 text-sm">
            <span className="text-slate-600">BMI, calculated from weight and height</span>
            <span className={clsx('text-lg font-semibold tabular', bmi >= 30 ? 'text-amber-800' : 'text-slate-900')}>{bmi.toFixed(1)} <span className="text-sm font-normal text-slate-500">{bmi >= 30 ? 'obese range' : bmi >= 25 ? 'overweight' : 'healthy'}</span></span>
          </div>
        )}
        <div className="px-5 py-4">
          <label className="mb-1.5 block text-sm font-medium text-slate-700" htmlFor="nurse-note">Nursing note (optional)</label>
          <Textarea id="nurse-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Appearance, concerns, anything the doctor should know" className="min-h-[64px]" />
          <div className="mt-3"><ErrorNote message={error} /></div>
          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-sm">
              {abnormal.length > 0
                ? <span className="inline-flex items-center gap-1.5 font-semibold text-rose-700"><AlertTriangle className="size-4" />{abnormal.length} abnormal: {abnormal.map((a) => a.short).join(', ')}. Priority will be raised.</span>
                : <span className="text-slate-500">{entered.length ? `${entered.length} reading(s) entered` : 'No readings entered yet'}</span>}
            </div>
            <Button size="lg" onClick={submit} loading={busy} disabled={entered.length === 0}>
              Save and send to doctor <ArrowRight className="size-4" />
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}
