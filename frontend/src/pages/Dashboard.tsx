import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { API } from '../lib/auth'

type Summary = {
  expedition: string
  station: string
  personnel_total: number
  readiness_breakdown: Record<string, number>
  open_incidents: number
  critical_incidents: number
  shipments_in_transit: number
  low_stock_items: number
  conflicts_unresolved: number
  weather: { station: string; temp_c: number; wind_kph: number; condition: string; updated_at: string } | null
}

function AnimatedNumber({ value }: { value: number }) {
  const [display, setDisplay] = useState(0)
  const prevVal = useRef(0)

  useEffect(() => {
    const start = prevVal.current
    const end = value
    const duration = 800
    const startTime = performance.now()

    function step(now: number) {
      const progress = Math.min((now - startTime) / duration, 1)
      const current = Math.floor(start + (end - start) * progress)
      setDisplay(current)
      if (progress < 1) {
        requestAnimationFrame(step)
      } else {
        prevVal.current = end
      }
    }

    requestAnimationFrame(step)
  }, [value])

  return <span>{display}</span>
}

export default function Dashboard({ token }: { token: string }) {
  const [data, setData] = useState<Summary | null>(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    fetch(`${API}/api/v1/dashboard/summary`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error(`Dashboard API ${r.status}`)
        return r.json()
      })
      .then(setData)
      .catch((e) => setErr(String(e)))
  }, [token])

  if (err) return <div className="card border-rose-300 bg-rose-50 text-rose-700 text-sm font-mono">{err}</div>
  if (!data) return <div className="p-8 text-center text-sm font-mono text-slate-500">Loading expedition summary...</div>

  const totalReady = (data.readiness_breakdown?.MISSION_READY || 0) + (data.readiness_breakdown?.AT_STATION || 0)
  const percentReady = data.personnel_total > 0 ? Math.round((totalReady / data.personnel_total) * 100) : 0

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Expedition Header Banner */}
      <div className="relative overflow-hidden rounded-2xl border border-sky-200 bg-gradient-to-r from-sky-600 via-blue-600 to-indigo-700 p-6 text-white shadow-md">
        <div className="relative z-10 flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-white/20 px-2.5 py-0.5 text-xs font-mono font-bold tracking-wider uppercase backdrop-blur-md">
                ACTIVE EXPEDITION
              </span>
              <span className="text-xs font-mono text-sky-100">SIH 2026 · PS 26062</span>
            </div>
            <h1 className="mt-1 text-2xl font-extrabold tracking-tight md:text-3xl">
              {data.expedition || 'EXP-46ISEA-2026'}
            </h1>
            <p className="mt-1 text-xs text-sky-100">
              Bharati Station Logistics & Asset Command Centre · Antarctic Continent
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link
              to="/app/missions"
              className="rounded-xl bg-white px-4 py-2 text-xs font-bold text-sky-800 shadow-sm transition-all hover:bg-sky-50 active:scale-95"
            >
              🚩 Deploy Field Team
            </Link>
            <Link
              to="/app/cargo"
              className="rounded-xl border border-white/30 bg-white/10 px-4 py-2 text-xs font-bold text-white backdrop-blur-md transition-all hover:bg-white/20 active:scale-95"
            >
              📦 Scan Cargo
            </Link>
          </div>
        </div>

        {/* Expedition Timeline Progress */}
        <div className="mt-5 border-t border-white/20 pt-4">
          <div className="flex justify-between text-[11px] font-mono text-sky-100">
            <span>Expedition Start: Nov 01, 2025</span>
            <span className="font-bold text-white">DAY 47 OF 180 (OVERWINTER SEASON)</span>
            <span>Target Return: Apr 30, 2026</span>
          </div>
          <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-black/20">
            <div className="h-full w-[26%] bg-gradient-to-r from-emerald-300 to-cyan-300 shadow-xs" />
          </div>
        </div>
      </div>

      {/* Sync Conflict Alert Bar */}
      {data.conflicts_unresolved > 0 && (
        <div className="flex items-center justify-between rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-900 shadow-xs">
          <div className="flex items-center gap-3">
            <span className="flex h-3 w-3 rounded-full bg-amber-500 animate-ping" />
            <span className="text-xs font-mono font-bold">
              ⚠️ ATTENTION: {data.conflicts_unresolved} offline sync conflict(s) require manual resolution.
            </span>
          </div>
          <Link
            to="/app/audit"
            className="rounded-lg bg-amber-200 px-3 py-1 text-xs font-mono font-bold text-amber-900 hover:bg-amber-300 transition-colors"
          >
            Review Conflicts →
          </Link>
        </div>
      )}

      {/* Primary Telemetry Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Personnel Readiness */}
        <div className="card relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-bold text-slate-500 uppercase">PERSONNEL READINESS</span>
            <span className="text-xl">👨‍🔬</span>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-slate-900">
              <AnimatedNumber value={data.personnel_total} />
            </span>
            <span className="text-xs font-mono text-emerald-600 font-semibold">{percentReady}% Mission Ready</span>
          </div>

          <div className="mt-3 flex items-center gap-2">
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full bg-gradient-to-r from-emerald-500 to-teal-500"
                style={{ width: `${percentReady}%` }}
              />
            </div>
            <span className="text-[10px] font-mono text-slate-500">{totalReady}/{data.personnel_total}</span>
          </div>
        </div>

        {/* Operational Incidents */}
        <div className="card relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-bold text-slate-500 uppercase">ACTIVE INCIDENTS</span>
            <span className="text-xl">🚨</span>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-slate-900">
              <AnimatedNumber value={data.open_incidents} />
            </span>
            {data.critical_incidents > 0 ? (
              <span className="text-xs font-mono text-rose-600 font-bold bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
                {data.critical_incidents} CRITICAL
              </span>
            ) : (
              <span className="text-xs font-mono text-emerald-600 font-medium">All Clear</span>
            )}
          </div>
          <div className="mt-3 text-[11px] font-mono text-slate-500">
            Automated AI mitigation engine active
          </div>
        </div>

        {/* Cargo In Transit */}
        <div className="card relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-bold text-slate-500 uppercase">SHIPMENTS IN TRANSIT</span>
            <span className="text-xl">📦</span>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-slate-900">
              <AnimatedNumber value={data.shipments_in_transit} />
            </span>
            <span className="text-xs font-mono text-sky-600 font-semibold">QR Tracked</span>
          </div>
          <div className="mt-3 text-[11px] font-mono text-slate-500">
            Route: Goa → Mumbai → Cape Town → Bharati
          </div>
        </div>

        {/* Low Stock Watch */}
        <div className="card relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-bold text-slate-500 uppercase">LOW STOCK ALERT</span>
            <span className="text-xl">📈</span>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-slate-900">
              <AnimatedNumber value={data.low_stock_items} />
            </span>
            <span className="text-xs font-mono text-amber-600 font-semibold">Items Below Min</span>
          </div>
          <div className="mt-3 text-[11px] font-mono text-slate-500">
            AI Stockout Model Predicts 14-day window
          </div>
        </div>
      </div>

      {/* Station Weather Instrument Card */}
      {data.weather && (
        <div className="card border-sky-200 bg-gradient-to-r from-sky-50 via-indigo-50/50 to-white">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-sky-100 text-2xl border border-sky-200">
                🌡️
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-bold text-sky-800 uppercase">STATION METEOROLOGICAL TELEMETRY</span>
                  <span className="rounded bg-sky-100 px-2 py-0.5 text-[10px] font-mono text-sky-700 font-bold">{data.weather.station}</span>
                </div>
                <div className="mt-1 flex items-baseline gap-3">
                  <span className="text-2xl font-extrabold font-mono text-slate-900">{data.weather.temp_c}°C</span>
                  <span className="text-xs text-slate-600 font-medium">Condition: <b className="text-slate-800">{data.weather.condition}</b></span>
                  <span className="text-xs text-slate-600 font-medium">Wind: <b className="text-slate-800">{data.weather.wind_kph} km/h</b></span>
                </div>
              </div>
            </div>

            <div className="text-[11px] font-mono text-slate-500">
              Updated: {data.weather.updated_at ? new Date(data.weather.updated_at).toLocaleTimeString() : 'Just now'}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
