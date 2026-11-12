import clsx from 'clsx'
import { CheckCircle2, Clock, PackageCheck, ShieldCheck, TestTube2, Wand2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { LabFlagValue } from '../components/clinical'
import { Badge, Button, Card, CardHeader, EmptyState, ErrorNote, Field, Input, SkeletonList, PageHeader, Select, StatusBadge, Textarea, useToast } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { timeAgo } from '../lib/format'
import { useResource } from '../lib/hooks'
import type { LabValue, OrderResult } from '../lib/types'

interface Param { name: string; unit: string; ref: string; demo: string; options?: string[] }

const TEMPLATES: { match: RegExp; specimen: string; params: Param[] }[] = [
  { match: /hba1c|a1c/i, specimen: 'Whole blood (EDTA)', params: [{ name: 'HbA1c', unit: '%', ref: '4.0-5.6', demo: '7.4' }] },
  { match: /fasting.*(glucose|sugar)/i, specimen: 'Plasma (fluoride)', params: [{ name: 'Fasting Blood Glucose', unit: 'mg/dL', ref: '70-99', demo: '142' }] },
  { match: /malaria/i, specimen: 'Whole blood', params: [{ name: 'Malaria RDT (P. falciparum)', unit: '', ref: 'Negative', demo: 'Positive', options: ['Negative', 'Positive'] }] },
  { match: /blood count|fbc/i, specimen: 'Whole blood (EDTA)', params: [
    { name: 'Haemoglobin', unit: 'g/dL', ref: '12.0-15.5', demo: '12.4' },
    { name: 'WBC', unit: 'x10^9/L', ref: '4.0-11.0', demo: '7.2' },
    { name: 'Platelets', unit: 'x10^9/L', ref: '150-400', demo: '265' },
  ] },
  { match: /lipid/i, specimen: 'Serum', params: [
    { name: 'Total Cholesterol', unit: 'mg/dL', ref: '<200', demo: '244' },
    { name: 'LDL Cholesterol', unit: 'mg/dL', ref: '<130', demo: '165' },
    { name: 'HDL Cholesterol', unit: 'mg/dL', ref: '>50', demo: '41' },
    { name: 'Triglycerides', unit: 'mg/dL', ref: '<150', demo: '198' },
  ] },
  { match: /urinalysis|urine/i, specimen: 'Urine (mid-stream)', params: [
    { name: 'Urine Protein', unit: '', ref: 'Negative', demo: '1+', options: ['Negative', 'Trace', '1+', '2+', '3+'] },
    { name: 'Urine Glucose', unit: '', ref: 'Negative', demo: '2+', options: ['Negative', 'Trace', '1+', '2+', '3+'] },
    { name: 'Urine Ketones', unit: '', ref: 'Negative', demo: 'Negative', options: ['Negative', 'Trace', '1+', '2+'] },
  ] },
  { match: /electrolyte|creatinine|urea|e\/u\/cr/i, specimen: 'Serum', params: [
    { name: 'Sodium', unit: 'mmol/L', ref: '135-145', demo: '139' },
    { name: 'Potassium', unit: 'mmol/L', ref: '3.5-5.1', demo: '4.2' },
    { name: 'Urea', unit: 'mmol/L', ref: '2.5-7.1', demo: '5.8' },
    { name: 'Creatinine', unit: 'mg/dL', ref: '0.6-1.1', demo: '0.9' },
  ] },
]

function templateFor(test: string): { specimen: string; params: Param[] } {
  return TEMPLATES.find((t) => t.match.test(test)) ?? { specimen: 'Specimen', params: [{ name: test, unit: '', ref: '', demo: '' }] }
}

function flagFor(value: string, ref: string): string {
  const v = parseFloat(value)
  if (ref.toLowerCase() === 'negative') return value && value.toLowerCase() !== 'negative' ? 'A' : ''
  if (Number.isNaN(v)) return ''
  const range = ref.match(/^([\d.]+)\s*-\s*([\d.]+)$/)
  if (range) return v < parseFloat(range[1]) ? 'L' : v > parseFloat(range[2]) ? 'H' : ''
  const lt = ref.match(/^<\s*([\d.]+)/)
  if (lt) return v >= parseFloat(lt[1]) ? 'H' : ''
  const gt = ref.match(/^>\s*([\d.]+)/)
  if (gt) return v <= parseFloat(gt[1]) ? 'L' : ''
  return ''
}

export default function Diagnostics({ department }: { department: 'laboratory' | 'radiology' }) {
  const { user } = useAuth()
  const isLab = department === 'laboratory'
  const queue = useResource<OrderResult[]>(user?.facility_id ? `/diagnostics/work-queue?department=${department}&facility_id=${user.facility_id}` : null, { poll: 4000 })
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const list = queue.data ?? []
  const selected = list.find((o) => o.id === selectedId) ?? null

  useEffect(() => {
    if ((!selectedId || !list.some((o) => o.id === selectedId)) && list.length) setSelectedId(list[list.length - 1].id)
  }, [list, selectedId])

  const counts = {
    requested: list.filter((o) => o.status === 'requested').length,
    progress: list.filter((o) => ['acknowledged', 'sample_collected', 'in_progress'].includes(o.status)).length,
    verify: list.filter((o) => o.status === 'result_entered').length,
  }

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader
        eyebrow={isLab ? 'Laboratory' : 'Imaging'}
        title={isLab ? 'Tests to run' : 'Scans to report'}
        subtitle="Orders arrive straight from the doctor. When you verify a result, it goes back to the doctor and into the patient’s record."
        action={<div className="text-sm text-slate-500"><b className="text-slate-900">{counts.requested}</b> new · <b className="text-slate-900">{counts.progress}</b> in progress · <b className="text-slate-900">{counts.verify}</b> to verify</div>}
      />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[360px_1fr]">
        <Card className="h-fit">
          <CardHeader title="Orders" subtitle="Oldest first · updates automatically" />
          <div className="divide-y divide-slate-100 border-t border-slate-100">
            {queue.loading && !queue.data && <SkeletonList rows={3} />}
            {!queue.loading && list.length === 0 && <EmptyState icon={<PackageCheck className="size-6" />} title="Worklist clear" description="New orders from doctors appear here automatically." />}
            {list.map((o) => (
              <button key={o.id} onClick={() => setSelectedId(o.id)} className={clsx('block w-full border-l-[3px] px-4 py-3 text-left transition-colors duration-150', o.id === selectedId ? 'border-brand-700 bg-brand-50' : 'border-transparent hover:bg-slate-50')}>
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-slate-800">{o.test_or_modality}</span>
                  {o.priority !== 'routine' && <Badge tone="amber">{o.priority === 'stat' ? 'STAT' : 'Urgent'}</Badge>}
                </div>
                <div className="mt-0.5 text-xs text-slate-500">{o.patient_name} · <span className="font-mono">{o.patient_number}</span></div>
                <div className="mt-2 flex items-center justify-between">
                  <StatusBadge status={o.status} />
                  <span className="flex items-center gap-1 text-xs text-slate-400"><Clock className="size-3" />{timeAgo(o.ordered_at)}</span>
                </div>
              </button>
            ))}
          </div>
        </Card>
        {selected ? <OrderPanel key={selected.id + selected.status} order={selected} isLab={isLab} onChange={() => queue.reload(true)} />
          : <Card><EmptyState icon={<TestTube2 className="size-6" />} title="Select an order" /></Card>}
      </div>
    </div>
  )
}

function OrderPanel({ order, isLab, onChange }: { order: OrderResult; isLab: boolean; onChange: () => void }) {
  const toast = useToast()
  const tpl = templateFor(order.test_or_modality)
  const [vals, setVals] = useState<Record<string, string>>({})
  const [comment, setComment] = useState('')
  const [rad, setRad] = useState({ modality: 'X-Ray', body_region: 'Chest', findings: '', impression: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function act(fn: () => Promise<unknown>, msg: string, desc?: string) {
    setBusy(true); setError(null)
    try { await fn(); toast({ tone: 'success', title: msg, description: desc }); onChange() } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  const acknowledge = () => act(() => api(`/diagnostics/orders/${order.id}/status?new_status=acknowledged`, { method: 'PATCH' }), isLab ? 'Sample collected' : 'Patient received for imaging')
  const enterLab = () => {
    const payload: Record<string, LabValue> = {}
    for (const p of tpl.params) {
      const v = vals[p.name] ?? ''
      const num = parseFloat(v)
      payload[p.name] = { value: !Number.isNaN(num) && /^[\d.]+$/.test(v) ? num : v, unit: p.unit, reference_range: p.ref, flag: flagFor(v, p.ref) }
    }
    return act(() => api(`/diagnostics/orders/${order.id}/lab-results`, { method: 'POST', json: { specimen_type: tpl.specimen, result_payload: payload, comments: comment || null } }), 'Result entered', 'Awaiting verification before release')
  }
  const enterRad = () => act(() => api(`/diagnostics/orders/${order.id}/radiology-reports`, { method: 'POST', json: rad }), 'Report entered', 'Awaiting verification before release')
  const verify = () => act(() => api(`/diagnostics/orders/${order.id}/verify`, { method: 'POST' }), 'Verified & released to doctor', 'The doctor’s workspace updates automatically.')

  const steps = ['requested', 'acknowledged', 'result_entered', 'verified']
  const stepIdx = Math.max(0, steps.indexOf(order.status === 'sample_collected' || order.status === 'in_progress' ? 'acknowledged' : order.status))

  return (
    <Card className="animate-fade-in">
      <div className="border-b border-slate-100 p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="font-mono text-xs text-slate-400">{order.order_number}</div>
            <h2 className="mt-0.5 text-2xl font-semibold text-slate-900">{order.test_or_modality}</h2>
            <div className="mt-1 text-sm text-slate-600">{order.patient_name} · <span className="font-mono">{order.patient_number}</span></div>
          </div>
          <StatusBadge status={order.status} />
        </div>
        <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <div className="rounded-md bg-slate-50 px-3.5 py-2.5"><div className="text-xs font-medium text-slate-500">Ordered by</div>{order.ordered_by ?? '—'}</div>
          <div className="rounded-md bg-slate-50 px-3.5 py-2.5"><div className="text-xs font-medium text-slate-500">Reason for test</div>{order.clinical_indication ?? '—'}</div>
        </div>
        <div className="mt-5 grid grid-cols-2 gap-2 sm:flex sm:items-center">
          {['Ordered', isLab ? 'Sample collected' : 'Imaging done', 'Result entered', 'Verified'].map((s, i) => (
            <div key={s} className="flex flex-1 items-center gap-2">
              <div className={clsx('grid size-6 shrink-0 place-items-center rounded-full text-xs font-semibold', i <= stepIdx ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-400')}>{i < stepIdx ? '✓' : i + 1}</div>
              <span className={clsx('text-xs', i <= stepIdx ? 'font-semibold text-slate-700' : 'text-slate-400')}>{s}</span>
              {i < 3 && <div className={clsx('hidden h-px flex-1 sm:block', i < stepIdx ? 'bg-brand-300' : 'bg-slate-200')} />}
            </div>
          ))}
        </div>
      </div>

      <div className="p-6">
        <ErrorNote message={error} />
        {order.status === 'requested' && (
          <div className="flex flex-col items-center py-6 text-center">
            <TestTube2 className="size-10 text-slate-300" />
            <p className="mt-2 text-sm text-slate-600">{isLab ? 'Collect the specimen and acknowledge the order.' : 'Receive the patient and acknowledge the order.'}</p>
            <Button className="mt-4" onClick={acknowledge} loading={busy} icon={<CheckCircle2 className="size-4" />}>{isLab ? 'Sample collected' : 'Acknowledge'}</Button>
          </div>
        )}

        {['acknowledged', 'sample_collected', 'in_progress'].includes(order.status) && isLab && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="text-sm font-bold text-slate-800">Enter results <span className="font-normal text-slate-400">· {tpl.specimen}</span></div>
              <Button variant="ghost" size="sm" onClick={() => setVals(Object.fromEntries(tpl.params.map((p) => [p.name, p.demo])))} icon={<Wand2 className="size-4" />}>Fill demo result</Button>
            </div>
            {tpl.params.map((p) => {
              const v = vals[p.name] ?? ''
              const flag = flagFor(v, p.ref)
              return (
                <div key={p.name} className={clsx('grid items-center gap-3 rounded-md border p-3.5 sm:grid-cols-[1fr_180px_140px]', flag ? 'border-rose-200 bg-rose-50' : 'border-slate-200')}>
                  <div>
                    <div className="text-sm font-semibold text-slate-800">{p.name}</div>
                    <div className="text-xs text-slate-500">Reference {p.ref || '—'} {p.unit}</div>
                  </div>
                  {p.options ? (
                    <Select value={v} onChange={(e) => setVals({ ...vals, [p.name]: e.target.value })}><option value="">Select…</option>{p.options.map((o) => <option key={o}>{o}</option>)}</Select>
                  ) : (
                    <Input value={v} onChange={(e) => setVals({ ...vals, [p.name]: e.target.value })} placeholder="Value" inputMode="decimal" />
                  )}
                  <div className="text-right">{v && <LabFlagValue v={{ value: v, unit: p.unit, flag }} />}</div>
                </div>
              )
            })}
            <Field label="Comment"><Textarea value={comment} onChange={(e) => setComment(e.target.value)} className="min-h-[60px]" placeholder="Optional laboratory comment" /></Field>
            <div className="flex justify-end">
              <Button onClick={enterLab} loading={busy} disabled={tpl.params.some((p) => !vals[p.name])}>Save result</Button>
            </div>
          </div>
        )}

        {['acknowledged', 'sample_collected', 'in_progress'].includes(order.status) && !isLab && (
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Modality"><Select value={rad.modality} onChange={(e) => setRad({ ...rad, modality: e.target.value })}>{['X-Ray', 'Ultrasound', 'CT', 'MRI'].map((m) => <option key={m}>{m}</option>)}</Select></Field>
              <Field label="Body region"><Input value={rad.body_region} onChange={(e) => setRad({ ...rad, body_region: e.target.value })} /></Field>
            </div>
            <Field label="Findings"><Textarea value={rad.findings} onChange={(e) => setRad({ ...rad, findings: e.target.value })} /></Field>
            <Field label="Impression"><Textarea value={rad.impression} onChange={(e) => setRad({ ...rad, impression: e.target.value })} className="min-h-[60px]" /></Field>
            <div className="flex justify-between">
              <Button variant="ghost" size="sm" onClick={() => setRad({ modality: 'X-Ray', body_region: 'Chest (PA)', findings: 'Normal cardiac silhouette (CTR 0.48). Clear lung fields bilaterally. No pleural effusion. Bony thorax intact.', impression: 'Normal chest radiograph.' })} icon={<Wand2 className="size-4" />}>Fill demo result</Button>
              <Button onClick={enterRad} loading={busy} disabled={!rad.findings || !rad.impression}>Save report</Button>
            </div>
          </div>
        )}

        {order.status === 'result_entered' && (
          <div className="space-y-3">
            <div className="text-sm font-bold text-slate-800">Review before release</div>
            {order.lab_result && Object.entries(order.lab_result.result_payload).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between rounded-xl bg-slate-50 px-4 py-2.5 text-sm">
                <span className="text-slate-700">{k} <span className="text-xs text-slate-400">ref {v.reference_range}</span></span>
                <LabFlagValue v={v} />
              </div>
            ))}
            {order.radiology_report && (
              <div className="rounded-xl bg-slate-50 p-4 text-sm"><p><b>Findings:</b> {order.radiology_report.findings}</p><p className="mt-1"><b>Impression:</b> {order.radiology_report.impression}</p></div>
            )}
            <div className="flex items-center justify-between pt-3">
              <span className="text-xs text-slate-500">Entered by {order.lab_result?.entered_by ?? order.radiology_report?.reported_by}</span>
              <Button onClick={verify} loading={busy} icon={<ShieldCheck className="size-4" />}>Verify & release to doctor</Button>
            </div>
          </div>
        )}
      </div>
    </Card>
  )
}
