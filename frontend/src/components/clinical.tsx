import clsx from 'clsx'
import { AlertTriangle, ChevronDown, FlaskConical, Lock, Pill, ShieldCheck, Sparkles, Stethoscope, Users } from 'lucide-react'
import { useMemo, useState, type ReactNode } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fmtDate, fmtDateTime, fmtVital, shortFacility, timeAgo, VITAL_BY_KEY, vitalStatus } from '../lib/format'
import type { LabValue, NetworkEncounter, PatientProfile, UnifiedRecord, Vital } from '../lib/types'
import { Badge, Card, CardHeader, StatusBadge } from './ui'

/* ------------------------------------------------------------ Facility identity
   Categorical colour, used only as small dots/lines so it never competes
   with the semantic (danger/warning/success) colours. */
// eslint-disable-next-line react-refresh/only-export-components
export function facilityColor(name?: string | null) {
  const n = name ?? ''
  if (n.includes('FMC') || n.includes('Federal')) return { dot: 'bg-fac-here', hex: '#0f5c4a' }
  if (n.includes('State')) return { dot: 'bg-fac-a', hex: '#8a5a2b' }
  if (n.includes('Chrisland')) return { dot: 'bg-fac-b', hex: '#7a3e6e' }
  return { dot: 'bg-fac-c', hex: '#4b5a55' }
}

export function FacilityChip({ name, here }: { name: string; here?: boolean }) {
  return (
    <span className="inline-flex h-6 items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2 text-xs font-medium whitespace-nowrap text-slate-700">
      <span className={clsx('size-2 rounded-full', facilityColor(name).dot)} />
      {shortFacility(name)}
      {here && <span className="text-slate-400">(here)</span>}
    </span>
  )
}

/* ------------------------------------------------------------ Patient header */
export function PatientBanner({ patient, access, extra }: { patient: PatientProfile; access?: UnifiedRecord['access']; extra?: ReactNode }) {
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3 px-5 pt-4 pb-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h2 className="text-2xl font-semibold text-slate-900">{patient.full_name}</h2>
            <span className="font-mono text-sm font-semibold text-slate-600">{patient.patient_number}</span>
          </div>
          <div className="mt-0.5 flex flex-wrap gap-x-3 text-sm text-slate-500">
            <span>{patient.gender}, {patient.age} yrs</span>
            <span>Born {fmtDate(patient.dob)}</span>
            {patient.blood_group && <span>Blood {patient.blood_group}</span>}
            {patient.genotype && <span>Genotype {patient.genotype}</span>}
            {patient.phone && <span className="tabular">{patient.phone}</span>}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {access && <AccessBadge access={access} />}
          {extra}
        </div>
      </div>
      <div className="space-y-1.5 border-t border-slate-100 px-5 py-3">
        <BannerCell icon={<AlertTriangle />} title="Allergies" tone="rose" locked={patient.restricted}>
          {patient.allergies.length ? patient.allergies.map((a) => <Badge key={a} tone="rose" className="!h-auto !py-1 !text-sm !whitespace-normal">{a}</Badge>) : <span className="text-sm text-slate-500">None known</span>}
        </BannerCell>
        <BannerCell icon={<Stethoscope />} title="Conditions" locked={patient.restricted}>
          {patient.chronic_conditions.length ? patient.chronic_conditions.map((c) => <span key={c} className="text-sm font-medium text-slate-800">{c}</span>) : <span className="text-sm text-slate-500">None recorded</span>}
        </BannerCell>
        <BannerCell icon={<Pill />} title="Medication" locked={patient.restricted}>
          {patient.current_medications.length ? patient.current_medications.map((m) => <span key={m} className="text-sm font-medium text-slate-800">{m}</span>) : <span className="text-sm text-slate-500">None recorded</span>}
        </BannerCell>
      </div>
    </Card>
  )
}

function BannerCell({ icon, title, tone, children, locked }: { icon: ReactNode; title: string; tone?: 'rose'; children: ReactNode; locked?: boolean }) {
  return (
    <div className="flex min-w-0 flex-col gap-1 sm:flex-row sm:items-start sm:gap-3">
      <span className={clsx('flex sm:w-28 shrink-0 items-center gap-1.5 pt-0.5 text-sm font-semibold [&>svg]:size-4', tone === 'rose' ? 'text-rose-700' : 'text-slate-500')}>{icon}{title}</span>
      <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
        {locked ? <span className="inline-flex items-center gap-1.5 text-sm text-slate-500"><Lock className="size-3.5" />Locked until the patient consents</span> : children}
      </div>
    </div>
  )
}

export function AccessBadge({ access }: { access: UnifiedRecord['access'] }) {
  if (access.level === 'full') {
    return (
      <div className="flex items-center gap-2 rounded-md border border-brand-200 bg-brand-50 px-3 py-1.5 text-sm">
        <ShieldCheck className="size-4 text-brand-700" />
        <span className="font-semibold text-brand-800">Patient consented</span>
        <span className="text-brand-700">until {fmtDateTime(access.expires_at).split(' · ')[1]}</span>
      </div>
    )
  }
  if (access.level === 'facility_only' && access.hidden_encounters > 0) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-1.5 text-sm">
        <Lock className="size-4 text-amber-700" />
        <span className="font-semibold text-amber-800">{access.hidden_encounters} visits at other hospitals locked</span>
      </div>
    )
  }
  return null
}

/* ------------------------------------------------------------ Vitals */
export function VitalTiles({ vitals, previous }: { vitals: Vital[]; previous?: Record<string, { value: number; facility: string; date: string }> }) {
  const latest = useMemo(() => {
    const m: Record<string, Vital> = {}
    for (const v of vitals) m[v.observation_type] = v
    return m
  }, [vitals])
  const order = ['systolic_bp', 'blood_glucose', 'pulse_rate', 'temperature', 'spo2', 'respiratory_rate', 'weight', 'pain_score']
  const bmi = latest.weight && latest.height ? latest.weight.value / (latest.height.value / 100) ** 2 : null
  const tiles = order.filter((k) => latest[k] || (k === 'systolic_bp' && latest.diastolic_bp))
  if (!tiles.length) return <p className="px-5 pb-5 text-sm text-slate-500">No vital signs recorded yet.</p>
  return (
    <div className="grid grid-cols-2 border-t border-slate-100 sm:grid-cols-[repeat(auto-fill,minmax(168px,1fr))]">
      {tiles.map((k) => {
        const v = latest[k]
        const isBp = k === 'systolic_bp'
        const warn = isBp ? (latest.systolic_bp?.is_warning || latest.diastolic_bp?.is_warning) : v?.is_warning
        const status = isBp ? vitalStatus('systolic_bp', latest.systolic_bp?.value) : vitalStatus(k, v?.value)
        const prev = previous?.[k]
        const delta = prev && v ? v.value - prev.value : null
        return (
          <div key={k} className={clsx('px-4 py-3 shadow-[inset_-1px_-1px_0_var(--color-slate-100)]', warn ? 'bg-rose-50' : 'bg-white')}>
            <div className="flex items-center justify-between gap-2 text-sm text-slate-500">
              <span className="truncate">{isBp ? 'Blood pressure' : VITAL_BY_KEY[k]?.label.replace(' (POC)', '')}</span>
              {warn && <span className="shrink-0 text-xs font-semibold text-rose-700">{status === 'low' ? 'Low' : 'High'}</span>}
            </div>
            <div className={clsx('mt-0.5 flex flex-wrap items-baseline gap-x-1 text-3xl font-semibold tabular', warn ? 'text-rose-700' : 'text-slate-900')}>
              {isBp ? `${latest.systolic_bp?.value ?? '—'}/${latest.diastolic_bp?.value ?? '—'}` : (Number.isInteger(v.value) ? v.value : v.value.toFixed(1))}
              <span className="text-sm font-normal text-slate-500">{isBp ? 'mmHg' : VITAL_BY_KEY[k]?.displayUnit}</span>
            </div>
            {prev && delta !== null && (
              <div className="mt-0.5 truncate text-xs text-slate-500" title={`${prev.facility}, ${fmtDate(prev.date)}`}>
                <span className={clsx('font-semibold', delta > 0 ? 'text-rose-700' : 'text-emerald-700')}>{delta > 0 ? '▲' : '▼'} {Math.abs(delta).toFixed(Number.isInteger(delta) ? 0 : 1)}</span>
                {' '}since {shortFacility(prev.facility).split(',')[0]}
              </div>
            )}
          </div>
        )
      })}
      {bmi && (
        <div className={clsx('px-4 py-3 shadow-[inset_-1px_-1px_0_var(--color-slate-100)]', bmi >= 30 ? 'bg-amber-50' : 'bg-white')}>
          <div className="flex items-center justify-between text-sm text-slate-500">BMI {bmi >= 30 && <span className="text-xs font-semibold text-amber-800">Obese</span>}</div>
          <div className={clsx('mt-0.5 text-3xl font-semibold tabular', bmi >= 30 ? 'text-amber-800' : 'text-slate-900')}>{bmi.toFixed(1)}</div>
          <div className="mt-0.5 text-xs text-slate-500">kg/m², from weight & height</div>
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------ Trend chart */
export function TrendChart({ record, metric, title, unit, normalMax, secondary }: { record: UnifiedRecord; metric: string; title: string; unit: string; normalMax?: number; secondary?: string }) {
  type Row = { date: string; facility: string; label?: string; [k: string]: number | string | undefined }
  const data = useMemo(() => {
    const byEnc = new Map<string, Row>()
    for (const v of record.vitals_series) {
      if (v.observation_type !== metric && v.observation_type !== secondary) continue
      const row = byEnc.get(v.encounter_id) ?? { date: v.measured_at, facility: v.facility_name }
      row[v.observation_type] = v.value
      byEnc.set(v.encounter_id, row)
    }
    return [...byEnc.values()].sort((a, b) => a.date.localeCompare(b.date)).map((r): Row => ({ ...r, label: fmtDate(r.date, { month: 'short', year: '2-digit' }) }))
  }, [record, metric, secondary])

  if (data.length < 2) return null
  const values = data.flatMap((d) => [d[metric], secondary ? d[secondary] : undefined]).filter((v): v is number => typeof v === 'number')
  const lo = Math.floor(Math.min(...values) * 0.85)
  const hi = Math.ceil(Math.max(...values) * 1.08)
  const first = data[0][metric] as number
  const last = data[data.length - 1][metric] as number

  return (
    <Card className="p-4">
      <div className="mb-2 flex items-start justify-between gap-3">
        <div>
          <div className="text-base font-semibold text-slate-900">{title}</div>
          <div className="text-sm text-slate-500">{data.length} readings, {new Set(data.map((d) => d.facility)).size} hospitals</div>
        </div>
        <span className={clsx('text-sm font-semibold tabular', last > first ? 'text-rose-700' : 'text-emerald-700')}>{last > first ? '▲' : '▼'} {Math.abs(last - first).toFixed(0)} {unit}</span>
      </div>
      <div className="h-40">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#eef2f0" vertical={false} />
            {normalMax && <ReferenceArea y1={normalMax} y2={hi} fill="#fef3f2" fillOpacity={1} />}
            <XAxis dataKey="label" tick={{ fontSize: 13, fill: '#4b5a55' }} axisLine={false} tickLine={false} />
            <YAxis domain={[lo, hi]} tick={{ fontSize: 13, fill: '#4b5a55' }} axisLine={false} tickLine={false} width={40} />
            <Tooltip
              contentStyle={{ borderRadius: 6, border: '1px solid #e3e7e5', fontSize: 13 }}
              formatter={(v, k) => [`${v} ${unit}`, VITAL_BY_KEY[String(k)]?.label ?? String(k)]}
              labelFormatter={(_, p) => (p?.[0] ? `${shortFacility(String(p[0].payload.facility))} · ${fmtDate(String(p[0].payload.date))}` : '')}
            />
            <Line isAnimationActive={false} type="monotone" dataKey={metric} stroke="#14201c" strokeWidth={2} dot={(p) => <circle key={p.index} cx={p.cx} cy={p.cy} r={5} fill={facilityColor(String(p.payload.facility)).hex} stroke="white" strokeWidth={2} />} />
            {secondary && <Line isAnimationActive={false} type="monotone" dataKey={secondary} stroke="#9aa6a2" strokeWidth={1.5} strokeDasharray="4 4" dot={{ r: 3, fill: '#9aa6a2' }} />}
          </LineChart>
        </ResponsiveContainer>
      </div>
      {normalMax && <div className="mt-1 text-xs text-slate-500">Shaded area: above normal ({normalMax} {unit}). Dots are coloured by hospital.</div>}
    </Card>
  )
}

/* ------------------------------------------------------------ Lab list */
export function LabHistory({ record }: { record: UnifiedRecord }) {
  if (!record.lab_series.length) return <p className="px-5 pb-5 text-sm text-slate-500">No laboratory results on record.</p>
  const rows = [...record.lab_series].reverse()
  return (
    <div className="divide-y divide-slate-100 border-t border-slate-100">
      {rows.map((l, i) => (
        <div key={i} className="flex items-start justify-between gap-3 px-5 py-2.5">
          <div className="min-w-0">
            <div className="text-sm font-medium text-slate-900">{l.parameter}</div>
            <div className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-500">
              <span className={clsx('size-2 rounded-full', facilityColor(l.facility_name).dot)} />
              {shortFacility(l.facility_name)} · {fmtDate(l.date)}
            </div>
          </div>
          <div className="text-right text-sm">
            <LabFlagValue v={{ value: l.value, unit: l.unit ?? undefined, flag: l.flag ?? undefined }} />
            {l.reference_range && <div className="text-xs text-slate-500">normal {l.reference_range}</div>}
          </div>
        </div>
      ))}
    </div>
  )
}

export function LabFlagValue({ v }: { v: LabValue }) {
  const flag = (v.flag ?? '').toUpperCase()
  const abnormal = ['H', 'L', 'A', 'HIGH', 'LOW', 'ABNORMAL', 'CRITICAL'].includes(flag)
  const word = flag === 'H' || flag === 'HIGH' ? 'High' : flag === 'L' || flag === 'LOW' ? 'Low' : 'Abnormal'
  return (
    <span className={clsx('font-semibold tabular whitespace-nowrap', abnormal ? 'text-rose-700' : 'text-slate-900')}>
      {String(v.value)} {v.unit && <span className="font-normal text-slate-500">{v.unit}</span>}
      {abnormal && <span className="ml-1.5 text-xs font-semibold">· {word}</span>}
    </span>
  )
}

/* ------------------------------------------------------------ Network timeline */
export function NetworkTimeline({ record, currentEncounterId, hereFacilityId }: { record: UnifiedRecord; currentEncounterId?: string; hereFacilityId?: string | null }) {
  const encounters = record.encounters.filter((e) => e.id !== currentEncounterId)
  return (
    <div className="px-5 pb-5">
      {record.access.level === 'facility_only' && record.access.hidden_encounters > 0 && (
        <div className="mb-4 flex items-start gap-3 rounded-md border border-dashed border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          <Lock className="mt-0.5 size-4 shrink-0" />
          <div><b>{record.access.hidden_encounters} visits</b> at {record.access.hidden_facilities.map(shortFacility).join(' and ')} are hidden until the patient approves access.</div>
        </div>
      )}
      {!encounters.length && record.access.level !== 'facility_only' && <p className="text-sm text-slate-500">No previous visits in the network.</p>}
      <ol className="relative space-y-3 border-l border-slate-200 pl-5">
        {encounters.map((e, i) => <TimelineItem key={e.id} enc={e} defaultOpen={i === 0} here={e.facility_id === hereFacilityId} />)}
      </ol>
    </div>
  )
}

function TimelineItem({ enc, defaultOpen, here }: { enc: NetworkEncounter; defaultOpen?: boolean; here?: boolean }) {
  const [open, setOpen] = useState(!!defaultOpen)
  const note = enc.clinical_notes[enc.clinical_notes.length - 1]
  const bp = { s: enc.vitals.find((v) => v.observation_type === 'systolic_bp')?.value, d: enc.vitals.find((v) => v.observation_type === 'diastolic_bp')?.value }
  const labs = enc.investigations.filter((o) => o.lab_result)
  return (
    <li className="relative">
      <span className={clsx('absolute -left-[25px] top-4 size-2.5 rounded-full ring-4 ring-white', facilityColor(enc.facility_name).dot)} />
      <div className="rounded-md border border-slate-200 bg-white">
        <button onClick={() => setOpen(!open)} aria-expanded={open} className="flex w-full items-start gap-3 p-3.5 text-left">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
              <span className="font-semibold text-slate-900">{shortFacility(enc.facility_name)}</span>
              {here && <span className="text-slate-500">(here)</span>}
              {enc.status !== 'completed' && <StatusBadge status={enc.status} />}
            </div>
            <div className="text-xs text-slate-500">{fmtDate(enc.opened_at)} · {timeAgo(enc.opened_at)}</div>
            <div className="mt-1 text-sm text-slate-800">{enc.presenting_complaint ?? 'Visit'}</div>
            {note?.assessment && <div className="mt-1 line-clamp-2 text-sm text-slate-500">{note.assessment}</div>}
            {(bp.s || labs.length > 0) && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {bp.s && <Badge tone={bp.s >= 140 ? 'rose' : 'slate'}>BP {bp.s}/{bp.d}</Badge>}
                {labs.slice(0, 3).map((o) => <Badge key={o.id} icon={<FlaskConical />}>{o.test_or_modality}</Badge>)}
              </div>
            )}
          </div>
          <ChevronDown className={clsx('mt-0.5 size-5 shrink-0 text-slate-400 transition-transform duration-150', open && 'rotate-180')} />
        </button>
        {open && (
          <div className="space-y-3 border-t border-slate-100 px-3.5 py-3 text-sm animate-fade-in">
            {enc.vitals.length > 0 && (
              <div>
                <div className="mb-1.5 text-xs font-semibold text-slate-500">Vital signs</div>
                <div className="flex flex-wrap gap-x-4 gap-y-1">
                  {enc.vitals.map((v, i) => (
                    <span key={i} className={clsx('tabular', v.is_warning ? 'font-semibold text-rose-700' : 'text-slate-700')}>
                      {VITAL_BY_KEY[v.observation_type]?.short ?? v.observation_type} {fmtVital(v.observation_type, v.value)}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {labs.length > 0 && (
              <div>
                <div className="mb-1.5 text-xs font-semibold text-slate-500">Results</div>
                <div className="divide-y divide-slate-100 rounded-md border border-slate-100">
                  {labs.flatMap((o) => Object.entries(o.lab_result!.result_payload).map(([k, v]) => (
                    <div key={o.id + k} className="flex justify-between gap-3 px-3 py-1.5">
                      <span className="text-slate-600">{k}</span>
                      <LabFlagValue v={v} />
                    </div>
                  )))}
                </div>
              </div>
            )}
            {note && (
              <div>
                <div className="mb-1.5 flex items-center justify-between text-xs font-semibold text-slate-500">
                  <span>Clinical note · {note.author}</span>
                  {note.is_ai_assisted && <Badge tone="ai" icon={<Sparkles />}>AI-assisted</Badge>}
                </div>
                <div className="space-y-1 text-slate-700">
                  {note.history_of_complaint && <p><span className="font-semibold">History:</span> {note.history_of_complaint}</p>}
                  {note.examination_findings && <p><span className="font-semibold">Exam:</span> {note.examination_findings}</p>}
                  {note.assessment && <p><span className="font-semibold">Assessment:</span> {note.assessment}</p>}
                  {note.clinical_plan && <p className="whitespace-pre-line"><span className="font-semibold">Plan:</span> {note.clinical_plan}</p>}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </li>
  )
}

/* ------------------------------------------------------------ Family history */
export function FamilyHistory({ record }: { record: UnifiedRecord }) {
  if (!record.family_history.length) return null
  return (
    <Card>
      <CardHeader title="Family history" icon={<Users />} />
      <div className="divide-y divide-slate-100 border-t border-slate-100">
        {record.family_history.map((f, i) => (
          <div key={i} className="flex items-center justify-between gap-3 px-5 py-2.5 text-sm">
            <div>
              <span className="font-semibold text-slate-900">{f.relationship_type}</span>
              <span className="text-slate-600"> · {f.condition}</span>
              {f.age_of_onset && <span className="text-slate-500"> (from age {f.age_of_onset})</span>}
            </div>
            {f.is_deceased && <span className="text-xs text-slate-500">Deceased</span>}
          </div>
        ))}
      </div>
    </Card>
  )
}

/* ------------------------------------------------------------ Hospitals that hold records */
export function NetworkFacilities({ record, hereFacilityId }: { record: UnifiedRecord; hereFacilityId?: string | null }) {
  return (
    <div className="space-y-1.5 text-sm">
      {record.facilities.map((f) => (
        <div key={f.facility_id} className="flex items-baseline gap-2">
          <span className={clsx('size-2.5 shrink-0 translate-y-[-1px] rounded-full', facilityColor(f.facility_name).dot)} />
          <span className="min-w-0 flex-1 font-medium text-slate-900">{shortFacility(f.facility_name)}</span>
          <span className="shrink-0 text-right text-slate-500">{f.facility_id === hereFacilityId ? 'today' : `${f.visits} visit${f.visits > 1 ? 's' : ''} · ${fmtDate(f.last_visit, { month: 'short', year: 'numeric' })}`}</span>
        </div>
      ))}
      {record.access.hidden_facilities.map((f) => (
        <div key={f} className="flex items-center gap-2 text-slate-500">
          <Lock className="size-3.5" /> {shortFacility(f)} (locked)
        </div>
      ))}
    </div>
  )
}
