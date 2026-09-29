import { useEffect, useState } from 'react'
import { Link, NavLink as RouterNavLink, Outlet } from 'react-router-dom'
import NotificationsBell from '../NotificationsBell'
import { getRole } from '../lib/auth'

const NAV = [
  { label: 'Dashboard', to: '/app', icon: '📊' },
  { label: 'Personnel', to: '/app/personnel', icon: '👨‍🔬' },
  { label: 'Cargo', to: '/app/cargo', icon: '📦' },
  { label: 'Inventory', to: '/app/inventory', icon: '📈' },
  { label: 'Generate Plan', to: '/app/plan', icon: '🧭' },
  { label: 'Field Missions', to: '/app/missions', icon: '🚩' },
  { label: 'SITREPs & AI', to: '/app/reports', icon: '📝' },
  { label: 'Audit & Log', to: '/app/audit', icon: '🛡️' },
]

export default function Shell({ token, onLogout }: { token: string; onLogout: () => void }) {
  const role = getRole(token)
  const [stationTime, setStationTime] = useState('')
  const [station, setStation] = useState('BHARATI')
  const [mobileOpen, setMobileOpen] = useState(false)

  useEffect(() => {
    function updateClock() {
      const now = new Date()
      const utc = now.getTime() + now.getTimezoneOffset() * 60000
      const offset = station === 'BHARATI' ? 5 : station === 'MAITRI' ? 5 : 1
      const local = new Date(utc + 3600000 * offset)
      setStationTime(
        local.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
      )
    }

    updateClock()
    const timer = setInterval(updateClock, 1000)
    return () => clearInterval(timer)
  }, [station])

  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900">
      {/* Sidebar for Desktop */}
      <aside className="hidden w-64 flex-col border-r border-slate-200 bg-white shadow-sm md:flex">
        {/* Brand */}
        <div className="flex h-16 items-center justify-between border-b border-slate-100 px-5">
          <Link to="/app" className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-tr from-sky-600 to-indigo-600 text-white font-bold shadow-sm">
              ❄
            </span>
            <span className="font-mono text-lg font-extrabold tracking-wider text-slate-800">
              POLARIS
            </span>
          </Link>
          <span className="rounded-md bg-sky-50 px-2 py-0.5 text-[10px] font-mono font-bold text-sky-700 border border-sky-200">
            SIH 2026
          </span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1 p-3">
          {NAV.map((n) => (
            <RouterNavLink
              key={n.to}
              to={n.to}
              end={n.to === '/app'}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-sky-50 text-sky-700 font-semibold shadow-xs border border-sky-200/80'
                    : 'text-slate-600 hover:bg-slate-100/80 hover:text-slate-900'
                }`
              }
            >
              <span className="text-base">{n.icon}</span>
              <span>{n.label}</span>
            </RouterNavLink>
          ))}
        </nav>

        {/* User Role Card */}
        <div className="border-t border-slate-100 p-4">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 shadow-xs">
            <div className="text-[11px] font-mono font-bold text-slate-400 uppercase">ACTIVE SESSION</div>
            <div className="mt-1 flex items-center justify-between">
              <span className="font-mono text-xs font-bold text-slate-700">{role || 'USER'}</span>
              <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
            </div>
            <button
              onClick={onLogout}
              className="mt-3 w-full rounded-lg border border-rose-200 bg-white py-1.5 text-xs font-semibold text-rose-600 hover:bg-rose-50 transition-colors"
            >
              Log Out
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top Header */}
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-200 bg-white/80 px-4 backdrop-blur-md md:px-6 shadow-xs">
          {/* Mobile Menu Button & Station Selector */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileOpen(!mobileOpen)}
              className="rounded-lg border border-slate-200 p-2 text-slate-600 hover:bg-slate-100 md:hidden"
            >
              ☰
            </button>

            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-slate-500 font-mono hidden sm:inline">STATION:</span>
              <select
                value={station}
                onChange={(e) => setStation(e.target.value)}
                className="rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-mono font-semibold text-slate-800 shadow-xs focus:border-sky-500 focus:outline-none"
              >
                <option value="BHARATI">Bharati Station (76°E, 69°S)</option>
                <option value="MAITRI">Maitri Station (11°E, 70°S)</option>
                <option value="HIMADRI">Himadri Arctic (78°N, 11°E)</option>
              </select>
            </div>
          </div>

          {/* Clock & Status & Notifications */}
          <div className="flex items-center gap-4">
            <div className="hidden items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-1 font-mono text-xs text-slate-700 sm:flex">
              <span className="h-2 w-2 rounded-full bg-sky-500"></span>
              <span>{station} TIME:</span>
              <span className="font-bold text-slate-900">{stationTime || '--:--:--'}</span>
            </div>

            <NotificationsBell token={token} />
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>

      {/* Mobile Drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden">
          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs" onClick={() => setMobileOpen(false)} />
          <div className="relative flex w-64 flex-col bg-white p-4 shadow-xl border-r border-slate-200">
            <div className="mb-4 flex items-center justify-between border-b border-slate-100 pb-3">
              <span className="font-mono text-lg font-extrabold text-slate-800">POLARIS</span>
              <button onClick={() => setMobileOpen(false)} className="text-slate-400 hover:text-slate-700">✕</button>
            </div>
            <nav className="space-y-1">
              {NAV.map((n) => (
                <RouterNavLink
                  key={n.to}
                  to={n.to}
                  end={n.to === '/app'}
                  onClick={() => setMobileOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium transition-all ${
                      isActive ? 'bg-sky-50 text-sky-700 font-semibold' : 'text-slate-600 hover:bg-slate-100'
                    }`
                  }
                >
                  <span>{n.icon}</span>
                  <span>{n.label}</span>
                </RouterNavLink>
              ))}
            </nav>
          </div>
        </div>
      )}
    </div>
  )
}
