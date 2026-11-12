import { ArrowRight, Check, Siren, X } from 'lucide-react'
import { useState } from 'react'
import { api } from '../lib/api'
import { shortFacility, timeAgo } from '../lib/format'
import { useResource } from '../lib/hooks'
import type { EmergencyRequest } from '../lib/types'
import type { ArrivalTarget } from './IncomingReferrals'
import { Button, Card, ErrorNote, Field, Modal, Textarea, useToast } from './ui'

/** CareConnect emergency requests that need THIS hospital's explicit confirmation, and ones it has confirmed. */
export function EmergencyInbox({ facilityId, onArrived }: { facilityId: string; onArrived: (t: ArrivalTarget) => void }) {
  const list = useResource<EmergencyRequest[]>('/emergency/requests', { poll: 3000 })
  const [declining, setDeclining] = useState<EmergencyRequest | null>(null)
  const open = (list.data ?? []).filter((e) => e.status !== 'arrived' && e.status !== 'handed_over')
  if (!list.data || open.length === 0) return null
  return (
    <Card className="animate-slide-up border-rose-300">
      <div className="border-b border-rose-100 bg-rose-50 px-5 py-3.5">
        <div className="flex items-center gap-2">
          <Siren className="size-5 text-rose-700" />
          <h2 className="whitespace-nowrap text-base font-semibold text-rose-900">Emergency requests</h2>
          <span className="rounded-md bg-rose-100 px-2 py-0.5 text-sm font-semibold text-rose-800 tabular">{open.length}</span>
        </div>
        <p className="mt-0.5 text-sm text-rose-800">VITALIS chose your hospital for its capabilities. If you can’t take the patient, it asks the next one.</p>
      </div>
      <div className="divide-y divide-slate-100">
        {open.map((e) => <Row key={e.id} e={e} facilityId={facilityId} onChanged={() => list.reload(true)} onDecline={() => setDeclining(e)} onArrived={onArrived} />)}
      </div>
      <Decline request={declining} facilityId={facilityId} onClose={() => setDeclining(null)} onDone={() => { setDeclining(null); list.reload(true) }} />
    </Card>
  )
}

function Row({ e, facilityId, onChanged, onDecline, onArrived }: { e: EmergencyRequest; facilityId: string; onChanged: () => void; onDecline: () => void; onArrived: (t: ArrivalTarget) => void }) {
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const mine = e.candidate_facilities.find((c) => c.facility_id === facilityId)
  const confirmedHere = e.confirmed_facility_id === facilityId
  const declinedBefore = e.candidate_facilities.filter((c) => c.confirmation_state === 'declined')

  async function accept() {
    setBusy(true)
    try {
      await api(`/emergency/requests/${e.id}/confirmations`, { method: 'POST', json: { facility_id: facilityId, accepted: true, reason_or_notes: 'Resuscitation bay and on-call team ready' } })
      toast({ tone: 'success', title: 'Emergency accepted', description: 'Transport is coordinated and the patient’s phone shows your hospital.' })
      onChanged()
    } catch (err) { toast({ tone: 'error', title: 'Could not accept', description: (err as Error).message }) } finally { setBusy(false) }
  }

  return (
    <div className="px-5 py-4">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-lg font-semibold text-slate-900">{e.patient_name ?? 'Patient'}</span>
        {e.patient_number && <span className="font-mono text-sm font-semibold text-slate-600">{e.patient_number}</span>}
        <span className="rounded-md bg-rose-100 px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-rose-800">{e.emergency_type}</span>
        <span className="text-sm text-slate-500">{e.emergency_number} · {timeAgo(e.created_at)}</span>
      </div>
      <p className="mt-1.5 text-base text-slate-700">Reports: {e.presenting_complaint}</p>
      {e.red_flags_detected.length > 0 && <p className="mt-1 text-sm font-medium text-rose-800">{e.red_flags_detected.join('; ')}</p>}
      <div className="mt-1 text-sm text-slate-500">
        Needs: <span className="font-medium text-slate-700">{e.required_capabilities.join(', ') || 'Emergency care'}</span>
        {mine && <> · {mine.distance_km.toFixed(1)} km from {e.patient_address ?? 'the patient'}</>}
      </div>
      {declinedBefore.length > 0 && !confirmedHere && (
        <div className="mt-1 text-sm text-slate-500">Already declined by: {declinedBefore.map((d) => shortFacility(d.facility_name)).join(', ')}</div>
      )}
      <div className="mt-3 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        {!confirmedHere && e.status === 'awaiting_hospital_confirmation' && (
          <>
            <Button variant="ghost" onClick={onDecline} icon={<X className="size-4" />}>Can’t take</Button>
            <Button variant="danger" onClick={accept} loading={busy} icon={<Check className="size-4" />}>We can receive this patient</Button>
          </>
        )}
        {confirmedHere && (
          <>
            <span className="self-center text-sm font-medium text-brand-800 sm:mr-auto">
              Confirmed. {e.transport ? `${e.transport.vehicle_callsign} arriving in about ${e.transport.estimated_hospital_arrival_minutes} min.` : 'Awaiting arrival.'}
            </span>
            {e.patient_number != null && (
              <Button onClick={() => onArrived({
                patient_id: e.patient_id, full_name: e.patient_name ?? 'Patient', patient_number: e.patient_number ?? '',
                complaint: e.presenting_complaint.toLowerCase() === e.emergency_type.toLowerCase() ? e.emergency_type : `${e.emergency_type}: ${e.presenting_complaint}`, referralId: e.linked_referral_id ?? undefined, emergencyId: e.id, emergency: true,
              })} icon={<ArrowRight className="size-4" />}>Patient arrived: start visit</Button>
            )}
          </>
        )}
      </div>
    </div>
  )
}

const REASONS = ['Resuscitation bay full', 'No specialist on call', 'Theatre unavailable']

function Decline({ request, facilityId, onClose, onDone }: { request: EmergencyRequest | null; facilityId: string; onClose: () => void; onDone: () => void }) {
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  async function submit() {
    if (!request) return
    setBusy(true); setError(null)
    try {
      await api(`/emergency/requests/${request.id}/confirmations`, { method: 'POST', json: { facility_id: facilityId, accepted: false, reason_or_notes: reason.trim() } })
      setReason(''); onDone()
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <Modal open={!!request} onClose={onClose} label="Decline emergency">
      <div className="p-7">
        <h2 className="text-xl font-semibold text-slate-900">Can’t receive this patient</h2>
        <p className="mt-1 text-sm text-slate-500">VITALIS immediately asks the next hospital that can treat this emergency.</p>
        <div className="mt-5 flex flex-wrap gap-2">
          {REASONS.map((d) => <button key={d} onClick={() => setReason(d)} className="rounded-md border border-slate-200 px-2.5 py-1.5 text-sm text-slate-700 hover:bg-slate-50">{d}</button>)}
        </div>
        <Field label="Reason (required)" className="mt-4"><Textarea value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
        <div className="mt-3"><ErrorNote message={error} /></div>
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="danger" disabled={!reason.trim()} loading={busy} onClick={submit}>Decline and pass on</Button>
        </div>
      </div>
    </Modal>
  )
}
