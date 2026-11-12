import clsx from 'clsx'
import { ArrowRight, Check, Inbox, Lock, ShieldCheck, X } from 'lucide-react'
import { useState } from 'react'
import { api } from '../lib/api'
import { timeAgo } from '../lib/format'
import { useResource } from '../lib/hooks'
import type { LookupResult, PatientProfile, Referral } from '../lib/types'
import { Button, Card, ErrorNote, Field, Modal, Textarea, useToast } from './ui'

export interface ArrivalTarget { patient_id: string; full_name: string; patient_number: string; complaint: string; referralId: string }

/** Incoming CareConnect referrals for this hospital: confirm (or decline with a reason), then check the patient in. */
export function IncomingReferrals({ facilityId, onArrived }: { facilityId: string; onArrived: (t: ArrivalTarget) => void }) {
  const list = useResource<Referral[]>(`/referrals/facility/${facilityId}`, { poll: 4000 })
  const open = (list.data ?? []).filter((r) => r.status === 'pending' || r.status === 'accepted' || r.status === 'more_information')
  const [declining, setDeclining] = useState<Referral | null>(null)
  if (!list.data || open.length === 0) return null
  return (
    <Card className="animate-slide-up border-sky-200">
      <div className="flex items-center gap-2 border-b border-slate-100 px-5 py-3.5">
        <Inbox className="size-5 text-sky-700" />
        <h2 className="text-base font-semibold text-slate-900">Incoming referrals</h2>
        <span className="rounded-md bg-sky-100 px-2 py-0.5 text-sm font-semibold text-sky-800 tabular">{open.length}</span>
        <span className="ml-auto hidden text-sm text-slate-500 sm:block">Patients wait until you confirm</span>
      </div>
      <div className="divide-y divide-slate-100">
        {open.map((r) => <ReferralRow key={r.id} r={r} onChanged={() => list.reload(true)} onDecline={() => setDeclining(r)} onArrived={onArrived} />)}
      </div>
      <DeclineReferral referral={declining} onClose={() => setDeclining(null)} onDone={() => { setDeclining(null); list.reload(true) }} />
    </Card>
  )
}

function ReferralRow({ r, onChanged, onDecline, onArrived }: { r: Referral; onChanged: () => void; onDecline: () => void; onArrived: (t: ArrivalTarget) => void }) {
  const toast = useToast()
  const p = useResource<PatientProfile>(`/patients/${r.patient_id}`)
  const look = useResource<LookupResult[]>(p.data ? `/records/lookup?q=${encodeURIComponent(p.data.patient_number)}` : null, { poll: 8000 })
  const info = look.data?.find((l) => l.patient_id === r.patient_id)
  const [busy, setBusy] = useState(false)
  const name = p.data ? `${p.data.first_name} ${p.data.last_name}` : '…'

  async function accept() {
    setBusy(true)
    try {
      await api(`/referrals/${r.id}/status`, { method: 'PATCH', json: { status: 'accepted' } })
      toast({ tone: 'success', title: `${name} confirmed`, description: 'The patient’s phone now says to come in today.' })
      onChanged()
    } catch (e) { toast({ tone: 'error', title: 'Could not confirm', description: (e as Error).message }) } finally { setBusy(false) }
  }

  return (
    <div className="px-5 py-4">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-lg font-semibold text-slate-900">{name}</span>
        {p.data && <span className="font-mono text-sm font-semibold text-slate-600">{p.data.patient_number}</span>}
        <span className={clsx('rounded-md px-2 py-0.5 text-xs font-semibold uppercase tracking-wide', r.urgency === 'emergency' ? 'bg-rose-100 text-rose-800' : r.urgency === 'urgent' ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-700')}>{r.urgency}</span>
        <span className="text-sm text-slate-500">via CareConnect · {timeAgo(r.created_at)}</span>
      </div>
      <p className="mt-1.5 text-base text-slate-700">{r.clinical_reason}</p>
      <div className="mt-1 text-sm text-slate-500">Care needed: <span className="font-medium text-slate-700">{r.service_needed}</span></div>
      {info && (
        <div className="mt-2 flex items-center gap-2 text-sm">
          {info.has_full_access
            ? <><ShieldCheck className="size-4 shrink-0 text-brand-700" /><span className="font-medium text-brand-800">Patient shared their records{info.external_facilities.length ? ` from ${info.external_facilities.length} other hospital${info.external_facilities.length === 1 ? '' : 's'}` : ''}</span></>
            : info.external_facilities.length > 0 && <><Lock className="size-4 shrink-0 text-amber-700" /><span className="font-medium text-amber-800">Records from other hospitals not shared yet</span></>}
        </div>
      )}
      <div className="mt-3 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        {r.status === 'pending' && <>
          <Button variant="ghost" onClick={onDecline} icon={<X className="size-4" />}>Can’t take</Button>
          <Button onClick={accept} loading={busy} icon={<Check className="size-4" />}>Confirm we can see this patient</Button>
        </>}
        {r.status === 'accepted' && p.data && (
          <>
            <span className="self-center text-sm font-medium text-brand-800 sm:mr-auto">Confirmed {timeAgo(r.responded_at)}. Waiting for the patient to arrive.</span>
            <Button onClick={() => onArrived({ patient_id: r.patient_id, full_name: name, patient_number: p.data!.patient_number, complaint: r.clinical_reason.split('. ')[0], referralId: r.id })} icon={<ArrowRight className="size-4" />}>Patient arrived: start visit</Button>
          </>
        )}
        {r.status === 'more_information' && <span className="text-sm text-amber-800">You asked for more information: “{r.facility_response_reason}”</span>}
      </div>
    </div>
  )
}

const DECLINE_REASONS = ['No specialist available today', 'Service at full capacity', 'Needs a higher level of care']

function DeclineReferral({ referral, onClose, onDone }: { referral: Referral | null; onClose: () => void; onDone: () => void }) {
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  async function submit() {
    if (!referral) return
    setBusy(true); setError(null)
    try {
      await api(`/referrals/${referral.id}/status`, { method: 'PATCH', json: { status: 'rejected', facility_response_reason: reason.trim() } })
      setReason(''); onDone()
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <Modal open={!!referral} onClose={onClose} label="Decline referral">
      <div className="p-7">
        <h2 className="text-xl font-semibold text-slate-900">Can’t take this patient</h2>
        <p className="mt-1 text-sm text-slate-500">The patient sees your reason and is asked to choose another hospital.</p>
        <div className="mt-5 flex flex-wrap gap-2">
          {DECLINE_REASONS.map((d) => <button key={d} onClick={() => setReason(d)} className="rounded-md border border-slate-200 px-2.5 py-1.5 text-sm text-slate-700 hover:bg-slate-50">{d}</button>)}
        </div>
        <Field label="Reason (required)" className="mt-4"><Textarea value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
        <div className="mt-3"><ErrorNote message={error} /></div>
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="danger" disabled={!reason.trim()} loading={busy} onClick={submit}>Decline referral</Button>
        </div>
      </div>
    </Modal>
  )
}
