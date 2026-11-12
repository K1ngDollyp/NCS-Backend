import clsx from 'clsx'
import { AlertOctagon, BookOpen, BrainCircuit, Check, CheckCircle2, ChevronDown, CircleSlash, Cpu, FlaskConical, History, Info, Plus, ShieldAlert, Sparkles, TrendingUp, TriangleAlert, Users, X } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { api } from '../lib/api'
import type { Assessment, Evidence } from '../lib/types'
import { Badge, Button, Card, Textarea } from './ui'

const PRE_STEPS = [
  'Checking the patient’s consent for this hospital',
  'Collecting her records from other hospitals',
  'Lining up vital signs, lab results and notes by date',
]

export function AIAssessmentPanel({
  encounterId, priorVisits, facilities, assessment, onAssessment, onOrder, onUseInNote, disabledReason, runSignal,
}: {
  encounterId: string
  priorVisits: number
  facilities: number
  assessment: Assessment | null
  onAssessment: (a: Assessment) => void
  onOrder: (test: string) => void
  onUseInNote: (a: Assessment) => void
  disabledReason?: string | null
  /** Increment to start a run from outside (e.g. the button in the visit header). */
  runSignal?: number
}) {
  const [phase, setPhase] = useState<'idle' | 'running' | 'revealing' | 'done'>(assessment ? 'done' : 'idle')
  const [steps, setSteps] = useState<string[]>([])
  const [shown, setShown] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<Assessment | null>(null)
  const [review, setReview] = useState<'pending' | 'accepted' | 'rejected'>('pending')
  const rootRef = useRef<HTMLDivElement>(null)
  const lastSignal = useRef(runSignal ?? 0)

  useEffect(() => { if (assessment) setPhase('done') }, [assessment])

  async function run() {
    rootRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    setError(null)
    setPhase('running')
    setSteps(PRE_STEPS)
    setShown(0)
    setReview('pending')
    const started = Date.now()
    const tick = window.setInterval(() => setShown((s) => Math.min(s + 1, PRE_STEPS.length)), 350)
    try {
      const a = await api<Assessment>(`/intelligence/encounters/${encounterId}/assessment`, { method: 'POST' })
      const wait = Math.max(0, 1100 - (Date.now() - started))
      window.setTimeout(() => {
        window.clearInterval(tick)
        setSteps([...PRE_STEPS, ...a.analysis_trace])
        setShown(PRE_STEPS.length)
        setPending(a)
        setPhase('revealing')
      }, wait)
    } catch (e) {
      window.clearInterval(tick)
      setError((e as Error).message)
      setPhase('idle')
    }
  }

  useEffect(() => {
    if (runSignal !== undefined && runSignal !== lastSignal.current) {
      lastSignal.current = runSignal
      if (phase === 'idle' || phase === 'done') run()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runSignal])

  // Reveal the real analysis trace one step at a time
  useEffect(() => {
    if (phase !== 'revealing') return
    if (shown >= steps.length) {
      const id = window.setTimeout(() => {
        setPhase('done')
        if (pending) onAssessment(pending)
      }, 300)
      return () => window.clearTimeout(id)
    }
    const id = window.setTimeout(() => setShown((s) => s + 1), 260)
    return () => window.clearTimeout(id)
  }, [phase, shown, steps.length, pending, onAssessment])

  async function decide(action: 'accepted' | 'rejected', rationale?: string) {
    if (!assessment) return
    await api(`/intelligence/insights/${assessment.insight_id}/review`, { method: 'POST', json: { action, rationale } })
    setReview(action)
    if (action === 'accepted') onUseInNote(assessment)
  }

  return (
    <div ref={rootRef} className="scroll-mt-24 overflow-hidden rounded-lg border border-slate-200 border-l-4 border-l-ai-600 bg-white">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
        <div className="flex items-start gap-3">
          <BrainCircuit className="mt-0.5 size-6 shrink-0 text-ai-600" />
          <div>
            <h3 className="text-lg font-semibold text-slate-900">VITALIS AI <span className="font-normal text-slate-500">· decision support</span></h3>
            <p className="text-sm text-slate-500">
              Reads today’s visit together with {priorVisits} earlier visit{priorVisits === 1 ? '' : 's'} at {facilities} other hospital{facilities === 1 ? '' : 's'}. Runs on VITALIS servers, using models trained by our team.
            </p>
          </div>
        </div>
        {phase === 'done' && <Button variant="secondary" size="sm" onClick={run}>Run again</Button>}
      </div>

      {phase === 'idle' && (
        <div className="flex flex-col items-start gap-4 px-5 py-5 sm:flex-row sm:items-center sm:justify-between">
          <p className="max-w-xl text-base text-slate-600">
            Suggests possible conditions, with the evidence for each, and checks common treatments against this patient’s allergies and medicines from every hospital.
          </p>
          <div className="flex flex-col items-start gap-2">
            <Button variant="ai" size="lg" onClick={run} icon={<Sparkles className="size-5" />}>Run VITALIS AI</Button>
            {disabledReason && <p className="max-w-xs text-xs text-amber-800">{disabledReason}</p>}
          </div>
        </div>
      )}
      {error && <div className="px-5 pb-4 text-sm text-rose-700">{error}</div>}

      {(phase === 'running' || phase === 'revealing') && (
        <ol className="space-y-2 px-5 py-5" aria-live="polite">
          {steps.slice(0, Math.max(1, shown + (phase === 'running' ? 1 : 0))).map((s, i) => {
            const done = i < shown
            const key = /trend|Ran NCS|flagged|Red-flag/.test(s)
            return (
              <li key={i} className="flex items-start gap-3 text-base animate-fade-in">
                <span className={clsx('mt-0.5 grid size-5 shrink-0 place-items-center rounded-full', done ? 'bg-ai-600 text-white' : 'border-2 border-ai-300')}>
                  {done && <Check className="size-3" strokeWidth={3} />}
                </span>
                <span className={clsx(done ? 'text-slate-700' : 'text-slate-500', key && done && 'font-semibold text-slate-900')}>{s}</span>
              </li>
            )
          })}
        </ol>
      )}

      {phase === 'done' && assessment && <AssessmentBody a={assessment} onOrder={onOrder} review={review} onDecide={decide} />}
    </div>
  )
}

/* ====================================================================== */
function AssessmentBody({ a, onOrder, review, onDecide }: { a: Assessment; onOrder: (t: string) => void; review: string; onDecide: (x: 'accepted' | 'rejected', r?: string) => void }) {
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState('')
  const avoid = a.medication_options.filter((m) => m.safety === 'avoid')

  return (
    <div className="divide-y divide-slate-100 animate-fade-in">
      {/* Summary */}
      <section className="px-5 py-4">
        <SectionTitle title="Summary" />
        <p className="mt-1.5 text-base leading-relaxed text-slate-800">{a.summary}</p>
        <p className="mt-2 text-sm text-slate-500">
          Based on {a.data_coverage.prior_encounters} earlier visits at {a.data_coverage.facilities.join(' and ') || 'this hospital'}: {a.data_coverage.vital_readings} vital-sign readings and {a.data_coverage.lab_values} lab results.
        </p>
      </section>

      {/* Safety first: red flags and blocked medicines */}
      {(a.red_flags.length > 0 || avoid.length > 0) && (
        <section className="space-y-3 px-5 py-4">
          {a.red_flags.map((f, i) => (
            <div key={i} className="flex gap-3 rounded-md border border-rose-200 border-l-4 border-l-rose-600 bg-rose-50 p-4">
              <AlertOctagon className="mt-0.5 size-5 shrink-0 text-rose-700" />
              <div>
                <div className="text-base font-semibold text-rose-800">{f.title}</div>
                <div className="text-sm text-rose-800">{f.detail}</div>
                <div className="mt-1 text-sm text-slate-800"><span className="font-semibold">Do now:</span> {f.action}</div>
              </div>
            </div>
          ))}
          {avoid.map((m) => (
            <div key={m.drug} className="flex gap-3 rounded-md border border-rose-200 border-l-4 border-l-rose-600 bg-white p-4">
              <ShieldAlert className="mt-0.5 size-5 shrink-0 text-rose-700" />
              <div>
                <div className="text-sm font-semibold text-rose-700">Safety alert from another hospital’s record</div>
                <div className="mt-0.5 text-base font-semibold text-slate-900">Do not give {m.drug.split(' ')[0]}. It is a usual {m.for_condition} medicine, but it conflicts with her history.</div>
                {m.alerts.map((al, i) => <div key={i} className="mt-1 text-sm text-slate-700">{al}</div>)}
              </div>
            </div>
          ))}
        </section>
      )}

      {/* Conditions */}
      <section className="px-5 py-4">
        <SectionTitle title="Possible conditions to consider" subtitle="Ranked by the evidence in her record. These are estimates, not diagnoses." />
        <div className="mt-3 space-y-2">
          {a.conditions.map((c, i) => <ConditionCard key={c.condition} c={c} defaultOpen={i === 0} onOrder={onOrder} />)}
        </div>
      </section>

      {/* Treatment options */}
      {a.medication_options.length > 0 && (
        <section className="px-5 py-4">
          <SectionTitle title="Treatment options, checked against her record" subtitle="Each option is checked against allergies, current medicines and conditions recorded at every hospital." />
          <div className="mt-3 divide-y divide-slate-100 rounded-md border border-slate-200">
            {a.medication_options.map((m, i) => (
              <div key={i} className={clsx('grid gap-x-4 gap-y-1 px-4 py-3 sm:grid-cols-[96px_1fr]', m.safety === 'avoid' && 'bg-rose-50')}>
                <div>
                  {m.safety === 'ok' && <Badge tone="emerald" icon={<CheckCircle2 />}>No conflict</Badge>}
                  {m.safety === 'caution' && <Badge tone="amber" icon={<TriangleAlert />}>Caution</Badge>}
                  {m.safety === 'avoid' && <Badge tone="rose" icon={<CircleSlash />}>Avoid</Badge>}
                </div>
                <div className="min-w-0">
                  <div className={clsx('text-base font-semibold', m.safety === 'avoid' ? 'text-rose-800 line-through decoration-rose-400' : 'text-slate-900')}>{m.drug}</div>
                  <div className="text-sm text-slate-500">{m.rationale}</div>
                  {m.alerts.map((al, k) => <div key={k} className={clsx('mt-1 text-sm', m.safety === 'avoid' ? 'font-medium text-rose-800' : 'text-amber-800')}>{al}</div>)}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ML models */}
      {a.ml_models.length > 0 && (
        <section className="px-5 py-4">
          <SectionTitle title="Risk models trained by the VITALIS team" subtitle="Run on the patient’s documented readings. We show exactly which inputs were measured and which were assumed." />
          <div className="mt-3 grid gap-3 2xl:grid-cols-2">
            {a.ml_models.map((m) => <ModelCard key={m.key} m={m} />)}
          </div>
        </section>
      )}

      {/* Trends & missing data */}
      <section className="grid gap-6 px-5 py-4 md:grid-cols-2">
        <div>
          <SectionTitle title="Changes over time" icon={<TrendingUp className="size-4" />} />
          <ul className="mt-2 space-y-1.5">
            {a.trends.map((t) => (
              <li key={t.metric} className="flex gap-2 text-sm text-slate-700">
                <span className={clsx('mt-1.5 size-1.5 shrink-0 rounded-full', t.direction === 'rising' ? 'bg-rose-600' : t.direction === 'falling' ? 'bg-sky-600' : 'bg-slate-300')} />
                {t.text}
              </li>
            ))}
            {!a.trends.length && <li className="text-sm text-slate-500">Not enough earlier readings to show a trend.</li>}
          </ul>
        </div>
        <div>
          <SectionTitle title="What would make this more certain" icon={<Info className="size-4" />} />
          <ul className="mt-2 space-y-1.5">
            {a.missing_data.map((m, i) => <li key={i} className="flex gap-2 text-sm text-slate-700"><span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-amber-500" />{m}</li>)}
            {!a.missing_data.length && <li className="text-sm text-slate-500">Key information is complete.</li>}
          </ul>
        </div>
      </section>

      {/* Clinician review */}
      <section className="bg-slate-50 px-5 py-4">
        <div className="flex flex-col gap-3">
          <div className="text-sm text-slate-600">
            <span className="font-semibold text-slate-900">You decide.</span> {a.safety_disclaimer}
          </div>
          {review === 'pending' && !rejecting && (
            <div className="flex flex-wrap justify-end gap-2">
              <Button variant="secondary" onClick={() => setRejecting(true)} icon={<X className="size-4" />}>Reject</Button>
              <Button onClick={() => onDecide('accepted')} icon={<Check className="size-4" />}>Accept and draft note</Button>
            </div>
          )}
          {review === 'accepted' && <Badge tone="emerald" icon={<Check />}>Accepted. Draft added to your note below</Badge>}
          {review === 'rejected' && <Badge>Rejected. Your reason was recorded</Badge>}
        </div>
        {rejecting && review === 'pending' && (
          <div className="mt-3 flex flex-col gap-2 sm:flex-row">
            <Textarea className="!min-h-[44px] flex-1" placeholder="Why? (saved in the audit log)" value={reason} onChange={(e) => setReason(e.target.value)} />
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setRejecting(false)}>Cancel</Button>
              <Button variant="danger" onClick={() => onDecide('rejected', reason)}>Reject</Button>
            </div>
          </div>
        )}
        <div className="mt-2 font-mono text-xs text-slate-500">{a.model_version}</div>
      </section>
    </div>
  )
}

function SectionTitle({ title, subtitle, icon }: { title: string; subtitle?: string; icon?: ReactNode }) {
  return (
    <div>
      <h4 className="flex items-center gap-1.5 text-base font-semibold text-slate-900">{icon && <span className="text-slate-400">{icon}</span>}{title}</h4>
      {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
    </div>
  )
}

const KIND: Record<Evidence['kind'], { icon: ReactNode; label: string }> = {
  current: { icon: <Sparkles />, label: 'Today' },
  history: { icon: <History />, label: 'History' },
  lab: { icon: <FlaskConical />, label: 'Lab' },
  family: { icon: <Users />, label: 'Family' },
  ml: { icon: <Cpu />, label: 'Model' },
  rule: { icon: <BookOpen />, label: 'Guideline' },
}

function ConditionCard({ c, defaultOpen, onOrder }: { c: Assessment['conditions'][number]; defaultOpen?: boolean; onOrder: (t: string) => void }) {
  const [open, setOpen] = useState(!!defaultOpen)
  const [ordered, setOrdered] = useState<string[]>([])
  const pct = Math.round(c.likelihood * 100)
  return (
    <Card className={clsx(open && 'border-ai-200')}>
      <button onClick={() => setOpen(!open)} aria-expanded={open} className="flex w-full items-center gap-4 px-4 py-3 text-left">
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-slate-900 text-sm font-semibold text-white">{c.rank}</span>
        <div className="min-w-0 flex-1">
          <div className="text-base font-semibold text-slate-900">{c.condition}</div>
          <div className="mt-1.5 flex items-center gap-3">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100" role="meter" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Likelihood">
              <div className="h-full rounded-full bg-ai-600 transition-[width] duration-500" style={{ width: `${pct}%` }} />
            </div>
            <span className="w-32 shrink-0 text-right text-sm font-semibold text-slate-700 tabular">{c.likelihood_label} likelihood</span>
          </div>
        </div>
        <ChevronDown className={clsx('size-5 shrink-0 text-slate-400 transition-transform duration-150', open && 'rotate-180')} />
      </button>
      {open && (
        <div className="space-y-5 border-t border-slate-100 px-4 py-4 animate-fade-in">
          <div>
            <div className="mb-2 text-sm font-semibold text-slate-700">Why this is suggested</div>
            <ul className="space-y-2.5">
              {c.evidence.map((e, i) => (
                <li key={i} className="flex gap-3">
                  <span className="mt-0.5 inline-flex h-6 w-24 shrink-0 items-center gap-1 rounded-md bg-slate-100 px-2 text-xs font-medium text-slate-700 [&>svg]:size-3.5">{KIND[e.kind].icon}{KIND[e.kind].label}</span>
                  <div className="min-w-0">
                    <div className="text-sm text-slate-900">{e.text}</div>
                    <div className="text-xs text-slate-500">{e.source}</div>
                  </div>
                </li>
              ))}
            </ul>
            {c.against.length > 0 && (
              <>
                <div className="mb-1.5 mt-4 text-sm font-semibold text-slate-700">Against</div>
                <ul className="space-y-1">{c.against.map((e, i) => <li key={i} className="text-sm text-slate-600">{e.text}</li>)}</ul>
              </>
            )}
            <div className="mt-4 flex items-center gap-1.5 text-xs text-slate-500"><BookOpen className="size-3.5" />{c.guideline}</div>
          </div>
          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <div className="mb-2 text-sm font-semibold text-slate-700">Suggested tests</div>
              <div className="divide-y divide-slate-100 rounded-md border border-slate-200">
                {c.recommended_investigations.map((t) => (
                  <div key={t} className="flex items-center justify-between gap-2 px-3 py-2 text-sm">
                    <span className="text-slate-800">{t}</span>
                    {ordered.includes(t)
                      ? <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700"><Check className="size-3.5" />Ordered</span>
                      : <button onClick={() => { onOrder(t); setOrdered([...ordered, t]) }} className="inline-flex h-8 shrink-0 items-center gap-1 rounded-md px-2 text-sm font-semibold text-brand-700 hover:bg-brand-50"><Plus className="size-4" />Order</button>}
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div className="mb-2 text-sm font-semibold text-slate-700">Things to consider</div>
              <ul className="space-y-1">{c.management_considerations.map((m) => <li key={m} className="flex gap-2 text-sm text-slate-700"><span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-slate-400" />{m}</li>)}</ul>
            </div>
          </div>
        </div>
      )}
    </Card>
  )
}

const SRC: Record<string, string> = {
  measured: 'text-emerald-700',
  derived: 'text-sky-700',
  record: 'text-slate-700',
  assumed: 'text-amber-800',
  imputed: 'text-amber-800',
}

function ModelCard({ m }: { m: Assessment['ml_models'][number] }) {
  const [open, setOpen] = useState(false)
  // The models are not calibrated for this population, so we show a qualitative band, never a probability.
  const band = m.probability >= 0.6 ? 2 : m.probability >= 0.3 ? 1 : 0
  const BANDS = ['Low', 'Moderate', 'High']
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-base font-semibold text-slate-900">{m.name}</div>
          <div className="text-sm text-slate-500">{m.algorithm}</div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-semibold text-ai-700">{BANDS[band]}</div>
          <div className="whitespace-nowrap text-xs text-slate-500">screening band</div>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-1" aria-hidden>
        {BANDS.map((b, i) => <div key={b} className={clsx('h-1.5 rounded-full', i <= band ? 'bg-ai-600' : 'bg-slate-100')} />)}
      </div>
      <div className="mt-2 text-sm font-medium text-slate-700">{m.label}</div>
      <p className="mt-1 text-xs text-slate-500">Not a calibrated probability. Not yet validated on Nigerian patients.</p>
      <button onClick={() => setOpen(!open)} aria-expanded={open} className="mt-3 flex w-full items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
        <span>{m.measured_inputs} of {m.total_inputs} inputs came from the patient’s record</span>
        <ChevronDown className={clsx('size-4 transition-transform duration-150', open && 'rotate-180')} />
      </button>
      {open && (
        <div className="mt-2 divide-y divide-slate-100 animate-fade-in">
          {m.inputs.map((i) => (
            <div key={i.feature} className="flex items-center justify-between gap-2 py-1.5 text-sm" title={i.detail}>
              <span className="text-slate-600">{i.label}</span>
              <span className="flex items-center gap-2">
                <span className="font-semibold text-slate-900 tabular">{i.value}</span>
                <span className={clsx('w-16 text-right text-xs font-semibold capitalize', SRC[i.source])}>{i.source}</span>
              </span>
            </div>
          ))}
          {m.note && <p className="pt-2 text-xs text-slate-500">{m.note}</p>}
        </div>
      )}
      <div className="mt-2 font-mono text-xs text-slate-500">{m.model_version}</div>
    </Card>
  )
}
