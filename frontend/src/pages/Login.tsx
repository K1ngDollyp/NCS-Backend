import clsx from 'clsx'
import { ArrowRight, ChevronDown, ClipboardList, FlaskConical, HeartPulse, LayoutDashboard, Smartphone, Stethoscope } from 'lucide-react'
import { useState, type FormEvent, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { Logo } from '../components/Layout'
import { Button, ErrorNote, Field, Input } from '../components/ui'
import { useAuth } from '../lib/auth'
import { homeFor } from '../lib/format'

const DEMO_PASSWORD = 'vitalis2026'

interface Role { step?: number; email: string; role: string; person: string; place: string; icon: ReactNode }

const JOURNEY: Role[] = [
  { step: 1, email: 'reception@fmc.vitalis.ng', role: 'Reception', person: 'Amina Bello', place: 'Confirms referrals, checks patients in', icon: <ClipboardList /> },
  { step: 2, email: 'nurse@fmc.vitalis.ng', role: 'Nurse', person: 'Kehinde Adeyemi, RN', place: 'Records vital signs', icon: <HeartPulse /> },
  { step: 3, email: 'doctor@fmc.vitalis.ng', role: 'Doctor', person: 'Dr. Babatunde Ogundimu', place: 'Reviews full history with VITALIS AI', icon: <Stethoscope /> },
  { step: 4, email: 'lab@fmc.vitalis.ng', role: 'Laboratory', person: 'Chukwudi Okon', place: 'Sends verified results back', icon: <FlaskConical /> },
]
const OTHER: Role[] = [
  { email: 'folake@example.com', role: 'Patient’s phone', person: 'Folake Adewale', place: 'Checks symptoms, finds a hospital, shares records', icon: <Smartphone /> },
  { email: 'admin@fmc.vitalis.ng', role: 'Medical director', person: 'FMC Abeokuta', place: 'Audit trail', icon: <LayoutDashboard /> },
]

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)

  async function go(id: string, pw: string) {
    setBusy(id)
    setError(null)
    try {
      const s = await login(id, pw)
      navigate(homeFor(s.role))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    go(identifier, password)
  }

  const row = (d: Role) => (
    <button
      key={d.email}
      onClick={() => go(d.email, DEMO_PASSWORD)}
      disabled={!!busy}
      className="group flex w-full items-center gap-4 border-t border-slate-200 px-4 py-3 text-left transition-colors duration-150 first:border-t-0 hover:bg-slate-50 disabled:opacity-60"
    >
      <span className={clsx('grid size-8 shrink-0 place-items-center rounded-full text-sm font-semibold', d.step ? 'bg-brand-700 text-white' : 'bg-slate-100 text-slate-600 [&>svg]:size-4')}>
        {d.step ?? d.icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-base font-semibold text-slate-900">{d.role} <span className="font-normal text-slate-500">· {d.person}</span></span>
        <span className="block truncate text-sm text-slate-500">{d.place}</span>
      </span>
      {busy === d.email
        ? <span className="size-4 animate-spin rounded-full border-2 border-brand-600 border-t-transparent" />
        : <ArrowRight className="size-5 text-slate-300 transition-colors group-hover:text-brand-700" />}
    </button>
  )

  return (
    <div className="flex min-h-full flex-col lg:flex-row">
      {/* The story */}
      <section className="order-2 bg-brand-900 px-6 py-8 text-white sm:px-10 lg:order-1 lg:flex lg:w-[44%] lg:flex-col lg:justify-between lg:py-10">
        <Logo light size="lg" />
        <div className="mt-8 lg:mt-0">
          <h1 className="max-w-md text-3xl font-semibold leading-tight sm:text-4xl">
            Your medical history, available at any hospital you visit, with your permission.
          </h1>
          <p className="mt-4 max-w-md text-base leading-relaxed text-brand-100">
            VITALIS links hospital records across Ogun State into one record per patient.
            The patient approves each hospital with a one-time code, and doctors get decision support that reads the whole history.
          </p>
        </div>

        <div className="mt-8 rounded-lg border border-white/15 p-5 lg:mt-0">
          <div className="text-sm font-semibold text-brand-100">Today’s demo patient</div>
          <div className="mt-1 text-lg font-semibold">Folake Adewale, 54 · <span className="whitespace-nowrap font-mono text-base">VIT-2026-0002</span></div>
          <ul className="mt-3 space-y-1.5 text-sm text-brand-50">
            <li className="flex gap-2"><span className="mt-2 size-1.5 shrink-0 rounded-full bg-brand-300" />Seen twice at State Hospital, Sokenu, then once at Chrisland Health Services</li>
            <li className="flex gap-2"><span className="mt-2 size-1.5 shrink-0 rounded-full bg-brand-300" />Today she walks into FMC Abeokuta for the first time</li>
            <li className="flex gap-2"><span className="mt-2 size-1.5 shrink-0 rounded-full bg-brand-300" />Her allergy was recorded at a hospital FMC has never worked with</li>
          </ul>
        </div>
      </section>

      {/* Choose a role */}
      <section className="order-1 flex flex-1 items-start justify-center bg-white lg:order-2 px-4 py-8 sm:px-10 lg:items-center lg:py-10">
        <div className="w-full max-w-lg">
          <div className="mb-6 lg:hidden"><Logo /></div>
          <h2 className="text-2xl font-semibold text-slate-900">Choose a role to start</h2>
          <p className="mt-1 text-base text-slate-500">Follow one patient through the hospital, in order.</p>

          <div className="mt-5 overflow-hidden rounded-lg border border-slate-200">{JOURNEY.map(row)}</div>
          <div className="mt-3 overflow-hidden rounded-lg border border-slate-200">{OTHER.map(row)}</div>

          <ErrorNote message={showForm ? null : error} />

          <button onClick={() => setShowForm(!showForm)} className="mt-4 flex items-center gap-1 text-sm font-medium text-slate-600 hover:text-slate-900">
            Sign in with email instead <ChevronDown className={clsx('size-4 transition-transform', showForm && 'rotate-180')} />
          </button>
          {showForm && (
            <form onSubmit={submit} className="mt-3 space-y-3 animate-fade-in">
              <Field label="Email or phone">
                <Input value={identifier} onChange={(e) => setIdentifier(e.target.value)} placeholder="name@hospital.vitalis.ng" autoComplete="username" />
              </Field>
              <Field label="Password">
                <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
              </Field>
              <ErrorNote message={error} />
              <Button type="submit" className="w-full" loading={busy === identifier}>Sign in</Button>
            </form>
          )}
          <p className="mt-5 text-xs text-slate-500">Competition prototype. All patients and staff are fictional.</p>
        </div>
      </section>
    </div>
  )
}
