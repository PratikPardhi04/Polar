import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { API } from '../lib/auth'

const FEATURES = [
  { icon: '▣', title: 'Expedition Logistics', desc: 'Shipments, containers and QR-tracked packages from Goa HQ to Bharati station.' },
  { icon: '📈', title: 'Inventory & Forecast', desc: 'Real-time stock ledger with daily burn-rate stockout predictions.' },
  { icon: '🚩', title: 'Field Missions', desc: 'Enforced state machine lifecycle with Go/No-Go safety gates & check-in tracking.' },
  { icon: '🆘', title: 'Emergency Response', desc: 'Rule engine + AI co-pilot for incident triage & automated response plans.' },
  { icon: '🔄', title: 'Offline-First Sync', desc: 'Local SQLite engine with cryptographic hash conflict resolution.' },
  { icon: '🛡️', title: 'Audit & Compliance', desc: 'Append-only audit trail for all operational state changes & PDF report export.' },
]

export default function Landing() {
  const [stats, setStats] = useState({ personnel: 20, packages: 100, stations: 3 })

  useEffect(() => {
    fetch(`${API}/api/v1/dashboard/summary`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d) setStats({ personnel: d.personnel_total || 20, packages: 100, stations: 3 })
      })
      .catch(() => {})
  }, [])

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans selection:bg-sky-500 selection:text-white">
      {/* Top Navbar */}
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-sky-600 to-indigo-600 text-white font-bold shadow-sm">
              ❄
            </span>
            <span className="font-mono text-xl font-extrabold tracking-wider text-slate-900">
              POLARIS
            </span>
          </div>

          <div className="flex items-center gap-4">
            <Link
              to="/login"
              className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-bold text-slate-700 shadow-xs hover:bg-slate-50 transition-all"
            >
              Sign In
            </Link>
            <Link
              to="/login"
              className="btn-aurora text-xs px-5 py-2"
            >
              Access Command Centre →
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative overflow-hidden py-20 md:py-32">
        <div className="mx-auto max-w-7xl px-6 text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-sky-200 bg-sky-50 px-4 py-1 text-xs font-mono font-bold text-sky-800 shadow-xs">
            <span>❄ SIH 2026 SUBMISSION</span>
            <span>·</span>
            <span>PROBLEM STATEMENT 26062</span>
          </div>

          <h1 className="mt-6 text-4xl font-extrabold tracking-tight text-slate-900 sm:text-5xl md:text-6xl max-w-4xl mx-auto leading-tight">
            Integrated Polar Expedition Logistics & Asset Management
          </h1>

          <p className="mt-6 text-lg text-slate-600 max-w-2xl mx-auto font-sans leading-relaxed">
            Mission control system powering Antarctic logistics, overwinter inventory forecasting, field traverse safety, and automated emergency response protocols.
          </p>

          <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
            <Link
              to="/login"
              className="btn-aurora text-sm px-8 py-3 shadow-md"
            >
              Launch POLARIS Demo System →
            </Link>
          </div>

          {/* Quick Metrics Banner */}
          <div className="mt-16 grid grid-cols-1 sm:grid-cols-3 gap-6 max-w-3xl mx-auto">
            <div className="card text-center">
              <div className="text-3xl font-extrabold font-mono text-sky-700">{stats.personnel}</div>
              <div className="text-xs font-mono text-slate-500 uppercase mt-1">Expedition Personnel</div>
            </div>
            <div className="card text-center">
              <div className="text-3xl font-extrabold font-mono text-indigo-700">{stats.packages}+</div>
              <div className="text-xs font-mono text-slate-500 uppercase mt-1">QR Tracked Assets</div>
            </div>
            <div className="card text-center">
              <div className="text-3xl font-extrabold font-mono text-emerald-700">{stats.stations}</div>
              <div className="text-xs font-mono text-slate-500 uppercase mt-1">Research Stations</div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="py-16 bg-white border-t border-slate-200">
        <div className="mx-auto max-w-7xl px-6">
          <div className="text-center max-w-2xl mx-auto">
            <h2 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
              Engineered for Extreme Antarctic Conditions
            </h2>
            <p className="mt-2 text-sm text-slate-500 font-mono">
              Designed for low-bandwidth satellite links, offline field operations, and zero data loss.
            </p>
          </div>

          <div className="mt-12 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {FEATURES.map((f, i) => (
              <div key={i} className="card hover:border-sky-300">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-50 text-xl text-sky-700 border border-sky-200">
                  {f.icon}
                </div>
                <h3 className="mt-4 text-base font-bold text-slate-900">{f.title}</h3>
                <p className="mt-2 text-xs text-slate-600 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-slate-50 py-8">
        <div className="mx-auto max-w-7xl px-6 text-center text-xs font-mono text-slate-500">
          POLARIS — Smart India Hackathon 2026 · Bharati Station Expedition Unit (EXP-46ISEA-2026)
        </div>
      </footer>
    </div>
  )
}
