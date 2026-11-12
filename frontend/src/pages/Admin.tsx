import clsx from 'clsx'
import { FileSearch, KeyRound, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { Badge, Button, Card, CardHeader, PageHeader, Select, SkeletonList, Stat } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useNavigate } from 'react-router-dom'
import { ROLE_LABEL, fmtDateTime, shortFacility } from '../lib/format'
import { useResource } from '../lib/hooks'

interface Overview {
  total_patients: number
  total_facilities: number
  encounters_overview: { total: number; awaiting_nursing: number; awaiting_doctor: number; awaiting_investigation: number; results_ready: number; completed: number }
}
interface AuditRow {
  id: string; action: string; resource_type: string; timestamp: string
  actor_name: string | null; actor_role: string | null; facility_name: string | null
  patient_name: string | null; patient_number: string | null; event_metadata: Record<string, unknown>
}

const GROUPS: Record<string, { label: string; match: RegExp; tone: 'brand' | 'amber' | 'ai' | 'sky' | 'rose' | 'slate' }> = {
  all: { label: 'All events', match: /.*/, tone: 'slate' },
  access: { label: 'Network access & consent', match: /NETWORK|CONSENT|QR_/, tone: 'amber' },
  ai: { label: 'AI & decision support', match: /INTELLIGENCE|NCS_ML|MEDICATION/, tone: 'ai' },
  clinical: { label: 'Clinical workflow', match: /ENCOUNTER|VITALS|NOTE|ORDER|INVESTIGATION|DIAGNOSTIC|LAB|RADIOLOGY/, tone: 'brand' },
  auth: { label: 'Authentication', match: /LOGIN|REGISTER/, tone: 'sky' },
}

function toneFor(action: string) {
  for (const [k, g] of Object.entries(GROUPS)) if (k !== 'all' && g.match.test(action)) return g.tone
  return 'slate' as const
}

export default function Admin() {
  const overview = useResource<Overview>('/admin/analytics/overview', { poll: 8000 })
  const audit = useResource<AuditRow[]>('/admin/audit-events?limit=200', { poll: 5000 })
  const [group, setGroup] = useState('all')
  const [resetting, setResetting] = useState(false)
  const { logout } = useAuth()
  const navigate = useNavigate()

  async function resetDemo() {
    if (!window.confirm('Reset all demo data to the starting story? Everyone will need to sign in again.')) return
    setResetting(true)
    try {
      await api('/admin/demo/reset', { method: 'POST' })
    } finally {
      logout()
      navigate('/login')
    }
  }
  const rows = (audit.data ?? []).filter((r) => GROUPS[group].match.test(r.action))
  const o = overview.data

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader eyebrow="Governance" title="Who did what, and when" subtitle="Every record view, consent, AI suggestion and clinical action is logged permanently."
        action={<Button variant="secondary" onClick={resetDemo} loading={resetting} icon={<RotateCcw className="size-4" />}>Reset demo data</Button>} />
      {o ? (
        <Card className="mb-6">
          <div className="grid grid-cols-2 divide-slate-100 sm:grid-cols-4 sm:divide-x [&>*]:border-b [&>*]:border-slate-100 sm:[&>*]:border-b-0">
            <Stat label="Patients on the network" value={o.total_patients} />
            <Stat label="Connected hospitals" value={o.total_facilities} />
            <Stat label="Visits recorded" value={o.encounters_overview.total} />
            <Stat label="Visits completed" value={o.encounters_overview.completed} />
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-1 border-t border-slate-100 px-4 py-3 text-sm text-slate-600">
            <span>Right now:</span>
            <span><b className="text-slate-900 tabular">{o.encounters_overview.awaiting_nursing}</b> waiting for triage</span>
            <span><b className="text-slate-900 tabular">{o.encounters_overview.awaiting_doctor}</b> waiting for a doctor</span>
            <span><b className="text-slate-900 tabular">{o.encounters_overview.awaiting_investigation}</b> in the lab</span>
            <span><b className="text-slate-900 tabular">{o.encounters_overview.results_ready}</b> with results ready</span>
          </div>
        </Card>
      ) : <Card className="mb-6"><SkeletonList rows={1} /></Card>}

      <Card>
        <CardHeader title="Audit trail" subtitle={`${rows.length} events. Entries cannot be edited or deleted.`} icon={<FileSearch />}
          action={<Select value={group} onChange={(e) => setGroup(e.target.value)} className="!w-60">{Object.entries(GROUPS).map(([k, g]) => <option key={k} value={k}>{g.label}</option>)}</Select>} />
        <div className="overflow-x-auto px-2 pb-3">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-y border-slate-100 bg-slate-50 text-left text-xs font-semibold text-slate-600">
                <th className="px-3 py-2">Time</th><th className="px-3 py-2">Event</th><th className="px-3 py-2">Actor</th><th className="px-3 py-2">Patient</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-slate-100 align-top">
                  <td className="whitespace-nowrap px-3 py-2.5 text-xs text-slate-500">{fmtDateTime(r.timestamp)}</td>
                  <td className="px-3 py-2.5">
                    <Badge tone={toneFor(r.action)} icon={/NETWORK|CONSENT/.test(r.action) ? <KeyRound className="size-3" /> : undefined}>{r.action.replaceAll('_', ' ').toLowerCase()}</Badge>
                  </td>
                  <td className="px-3 py-2.5">
                    <div className={clsx('font-medium text-slate-800')}>{r.actor_name ?? '—'}</div>
                    <div className="text-xs text-slate-400">{r.actor_role ? ROLE_LABEL[r.actor_role] : ''}{r.facility_name && ` · ${shortFacility(r.facility_name)}`}</div>
                  </td>
                  <td className="px-3 py-2.5 text-xs text-slate-600">{r.patient_name ? <>{r.patient_name} <span className="font-mono text-slate-400">{r.patient_number}</span></> : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
