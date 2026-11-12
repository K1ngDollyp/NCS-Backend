import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './components/Layout'
import { ToastProvider } from './components/ui'
import { AuthProvider, useAuth } from './lib/auth'
import { homeFor } from './lib/format'
import type { Role } from './lib/types'
import Admin from './pages/Admin'
import Diagnostics from './pages/Diagnostics'
import { DoctorQueue, DoctorWorkspace } from './pages/Doctor'
import Login from './pages/Login'
import Nursing from './pages/Nursing'
import PatientApp from './pages/PatientApp'
import Reception from './pages/Reception'

function Guard({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  if (!roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />
  return <>{children}</>
}

function Home() {
  const { user } = useAuth()
  return <Navigate to={user ? homeFor(user.role) : '/login'} replace />
}

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/me" element={<Guard roles={['patient']}><PatientApp /></Guard>} />
            <Route element={<AppLayout />}>
              <Route path="/reception" element={<Guard roles={['reception', 'facility_admin']}><Reception /></Guard>} />
              <Route path="/nursing" element={<Guard roles={['nurse']}><Nursing /></Guard>} />
              <Route path="/doctor" element={<Guard roles={['doctor']}><DoctorQueue /></Guard>} />
              <Route path="/doctor/encounter/:id" element={<Guard roles={['doctor']}><DoctorWorkspace /></Guard>} />
              <Route path="/lab" element={<Guard roles={['lab_tech']}><Diagnostics department="laboratory" /></Guard>} />
              <Route path="/radiology" element={<Guard roles={['radiologist']}><Diagnostics department="radiology" /></Guard>} />
              <Route path="/admin" element={<Guard roles={['facility_admin', 'network_admin']}><Admin /></Guard>} />
            </Route>
            <Route path="*" element={<Home />} />
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </AuthProvider>
  )
}
