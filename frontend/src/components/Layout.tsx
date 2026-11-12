import clsx from 'clsx'
import { Building2, ClipboardList, FlaskConical, HeartPulse, LayoutDashboard, LogOut, ScanLine, ShieldCheck, Stethoscope, UserRound } from 'lucide-react'
import type { ReactNode } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { ROLE_LABEL, shortFacility } from '../lib/format'
import { Avatar } from './ui'

export function Logo({ light = false, size = 'md' }: { light?: boolean; size?: 'md' | 'lg' }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className={clsx('grid place-items-center rounded-md', light ? 'bg-white text-brand-700' : 'bg-brand-700 text-white', size === 'lg' ? 'size-10' : 'size-8')}>
        <svg viewBox="0 0 64 64" className={size === 'lg' ? 'size-7' : 'size-5'} aria-hidden>
          <path d="M6 34h12l5-12 9 24 6-16 4 4h16" fill="none" stroke="currentColor" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <div className="leading-tight">
        <div className={clsx('font-bold tracking-tight', light ? 'text-white' : 'text-slate-900', size === 'lg' ? 'text-xl' : 'text-base')}>VITALIS</div>
        <div className={clsx('text-xs', light ? 'text-brand-100' : 'text-slate-500')}>Health record network</div>
      </div>
    </div>
  )
}

const NAV: Record<string, { to: string; label: string; icon: ReactNode }[]> = {
  reception: [{ to: '/reception', label: 'Front desk', icon: <ClipboardList /> }],
  nurse: [{ to: '/nursing', label: 'Triage & vitals', icon: <HeartPulse /> }],
  doctor: [{ to: '/doctor', label: 'My patients', icon: <Stethoscope /> }],
  lab_tech: [{ to: '/lab', label: 'Lab worklist', icon: <FlaskConical /> }],
  radiologist: [{ to: '/radiology', label: 'Imaging worklist', icon: <ScanLine /> }],
  patient: [{ to: '/me', label: 'My health record', icon: <UserRound /> }],
  facility_admin: [{ to: '/admin', label: 'Audit & governance', icon: <LayoutDashboard /> }],
  network_admin: [{ to: '/admin', label: 'Audit & governance', icon: <LayoutDashboard /> }],
}

const JOURNEY = [
  { role: 'reception', label: 'Reception', hint: 'Referrals and check-in' },
  { role: 'nurse', label: 'Nursing', hint: 'Record vital signs' },
  { role: 'doctor', label: 'Doctor', hint: 'Review history, decide' },
  { role: 'lab_tech', label: 'Lab & imaging', hint: 'Results back to doctor' },
]

export function AppLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  if (!user) return null
  const items = NAV[user.role] ?? []
  const stepIdx = JOURNEY.findIndex((j) => j.role === user.role || (j.role === 'lab_tech' && user.role === 'radiologist'))

  return (
    <div className="flex min-h-full">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-slate-200 bg-white lg:flex">
        <div className="px-5 py-5"><Logo /></div>

        <nav className="flex-1 space-y-1 px-3" aria-label="Main">
          {items.map((i) => (
            <NavLink
              key={i.to}
              to={i.to}
              className={({ isActive }) => clsx(
                'flex h-10 items-center gap-3 rounded-md px-3 text-sm font-medium transition-colors duration-150 [&>svg]:size-[18px]',
                isActive ? 'bg-brand-50 text-brand-800' : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900',
              )}
            >
              {i.icon}
              {i.label}
            </NavLink>
          ))}

          {stepIdx >= 0 && (
            <div className="pt-8">
              <div className="px-3 pb-3 text-xs font-semibold text-slate-500">Patient journey</div>
              <ol className="space-y-0.5 px-3">
                {JOURNEY.map((j, i) => (
                  <li key={j.role} className="flex gap-3">
                    <div className="flex flex-col items-center">
                      <span className={clsx(
                        'grid size-6 place-items-center rounded-full text-xs font-semibold',
                        i === stepIdx ? 'bg-brand-700 text-white' : i < stepIdx ? 'bg-brand-100 text-brand-800' : 'bg-slate-100 text-slate-500',
                      )}>{i + 1}</span>
                      {i < JOURNEY.length - 1 && <span className="my-0.5 h-5 w-px bg-slate-200" />}
                    </div>
                    <div className="pt-0.5">
                      <div className={clsx('text-sm', i === stepIdx ? 'font-semibold text-slate-900' : 'text-slate-500')}>{j.label}</div>
                      {i === stepIdx && <div className="text-xs text-slate-500">{j.hint}</div>}
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </nav>

        {user.facility_name && (
          <div className="border-t border-slate-200 px-5 py-4">
            <div className="flex items-start gap-2 text-sm font-semibold text-slate-900">
              <Building2 className="mt-0.5 size-4 shrink-0 text-slate-400" />
              {shortFacility(user.facility_name)}
            </div>
            <div className="mt-1 flex items-center gap-1.5 text-xs text-slate-500">
              <ShieldCheck className="size-3.5 text-brand-600" /> Connected · every access logged
            </div>
          </div>
        )}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 border-b border-slate-200 bg-white">
          <div className="flex h-16 items-center justify-between gap-4 px-4 sm:px-8">
            <div className="lg:hidden"><Logo /></div>
            <div className="hidden min-w-0 items-center gap-2 text-sm lg:flex">
              <span className="font-semibold text-slate-900">{ROLE_LABEL[user.role]}</span>
              {user.facility_name && <><span className="text-slate-300">/</span><span className="truncate text-slate-500">{user.facility_name}</span></>}
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2.5">
                <Avatar name={user.full_name} className="size-9 text-xs" />
                <div className="hidden leading-tight sm:block">
                  <div className="text-sm font-semibold text-slate-900">{user.full_name.replace(/\s*\(.*\)$/, '')}</div>
                  <div className="text-xs text-slate-500">{ROLE_LABEL[user.role]}</div>
                </div>
              </div>
              <button
                onClick={() => { logout(); navigate('/login') }}
                className="flex h-9 items-center gap-1.5 rounded-md px-2.5 text-sm font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900"
              >
                <LogOut className="size-4" /><span className="hidden sm:inline">Sign out</span>
              </button>
            </div>
          </div>
          {/* Mobile: where am I */}
          <div className="flex items-center gap-2 border-t border-slate-100 px-4 py-2 text-sm lg:hidden">
            <span className="font-semibold text-slate-900">{ROLE_LABEL[user.role]}</span>
            {user.facility_name && <span className="truncate text-slate-500">· {shortFacility(user.facility_name)}</span>}
          </div>
        </header>
        <main className="flex-1 px-4 py-6 sm:px-8 sm:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
