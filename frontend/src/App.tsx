import { useState } from 'react'
import { HashRouter, Link, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import AskPolaris from './AskPolaris'
import AuditCompliance from './AuditCompliance'
import IncidentsPanel from './IncidentsPanel'
import MapView from './MapView'
import { login } from './lib/auth'
import Cargo from './pages/Cargo'
import Dashboard from './pages/Dashboard'
import Inventory from './pages/Inventory'
import Landing from './pages/Landing'
import Missions from './pages/Missions'
import Personnel from './pages/Personnel'
import Shell from './pages/Shell'
import SimulationPanel from './SimulationPanel'
import SituationReports from './SituationReports'

function LoginView({ onToken }: { onToken: (t: string) => void }) {
  const [email, setEmail] = useState('admin@bharati.in')
  const [password, setPassword] = useState('password123')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const nav = useNavigate()

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr('')
    setBusy(true)
    try {
      const token = await login(email, password)
      onToken(token)
      nav('/app')
    } catch (ex) {
      setErr(String(ex))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-4 font-sans text-slate-900 selection:bg-sky-500 selection:text-white">
      {/* Background Decor */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-96 h-96 bg-sky-200/40 rounded-full blur-3xl"></div>
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-blue-200/30 rounded-full blur-3xl"></div>
      </div>

      <div className="relative z-10 w-full max-w-md">
        {/* Brand logo */}
        <div className="text-center mb-6">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-tr from-sky-600 to-indigo-600 text-white font-bold text-xl shadow-md">
            ❄
          </div>
          <h1 className="mt-3 text-2xl font-extrabold tracking-tight text-slate-900 font-mono">
            POLARIS
          </h1>
          <p className="text-xs text-slate-500 font-mono mt-1">
            Polar Expedition Command Centre · SIH 2026
          </p>
        </div>

        <div className="card shadow-lg border-slate-200/80 bg-white/95">
          <div className="card-title mb-4 justify-center">
            <span>SECURE EXPEDITION AUTHENTICATION</span>
          </div>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="block text-xs font-mono font-bold text-slate-600 uppercase mb-1">
                Authorized Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-mono font-bold text-slate-600 uppercase mb-1">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input"
                required
              />
            </div>

            {err && (
              <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs font-mono text-rose-700">
                ⚠️ Error: {err}
              </div>
            )}

            <button
              type="submit"
              disabled={busy}
              className="btn-aurora w-full text-xs font-mono py-2.5 shadow-sm"
            >
              {busy ? 'Authenticating...' : 'Sign In to Command System →'}
            </button>
          </form>

          <div className="mt-4 pt-4 border-t border-slate-100 text-center">
            <span className="text-[11px] font-mono text-slate-500">
              Demo Credentials Pre-filled (Admin Account)
            </span>
          </div>
        </div>

        <div className="mt-6 text-center">
          <Link to="/" className="text-xs font-mono text-sky-700 hover:text-sky-800">
            ← Back to Landing Page
          </Link>
        </div>
      </div>
    </div>
  )
}

function ReportsPage({ token }: { token: string }) {
  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 flex items-center gap-3">
            <span>📝</span> SITREPs & AI Copilot
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Automated situation report generator and strict human-in-the-loop decision copilot.
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <AskPolaris token={token} />
        <SituationReports token={token} />
      </div>
    </div>
  )
}

function AuditPage({ token }: { token: string }) {
  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 flex items-center gap-3">
            <span>🛡️</span> Audit Trail & Conflict Engine
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Cryptographic event log, active session tracking, and offline sync conflict resolution.
          </p>
        </div>
      </div>

      <SimulationPanel token={token} />
      <IncidentsPanel token={token} />
      <AuditCompliance token={token} />
    </div>
  )
}

function DashboardPage({ token }: { token: string }) {
  return (
    <div className="space-y-6 animate-fade-in">
      <Dashboard token={token} />
      <MapView token={token} />
    </div>
  )
}

export default function App() {
  const [token, setToken] = useState<string>(() => localStorage.getItem('polaris_token') || '')

  function handleToken(t: string) {
    setToken(t)
    if (t) localStorage.setItem('polaris_token', t)
    else localStorage.removeItem('polaris_token')
  }

  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<LoginView onToken={handleToken} />} />
        {token ? (
          <Route path="/app" element={<Shell token={token} onLogout={() => handleToken('')} />}>
            <Route index element={<DashboardPage token={token} />} />
            <Route path="personnel" element={<Personnel token={token} />} />
            <Route path="cargo" element={<Cargo token={token} />} />
            <Route path="inventory" element={<Inventory token={token} />} />
            <Route path="missions" element={<Missions token={token} />} />
            <Route path="reports" element={<ReportsPage token={token} />} />
            <Route path="audit" element={<AuditPage token={token} />} />
          </Route>
        ) : (
          <Route path="/app/*" element={<Navigate to="/login" replace />} />
        )}
      </Routes>
    </HashRouter>
  )
}
