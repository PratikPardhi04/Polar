import { useState } from 'react'
import { API, getRole } from './lib/auth'

/** Simulation Control (ADMIN only): each button fires a real backend endpoint
 *  that mutates real records through the real state machines. */
export default function SimulationPanel({ token }: { token: string }) {
  const [out, setOut] = useState('')
  const [busy, setBusy] = useState<string | null>(null)

  if (getRole(token) !== 'ADMIN') return <p className="text-sm text-slate-500 font-mono">Simulation Control is restricted to ADMIN roles.</p>

  async function fire(path: string, body: Record<string, unknown> = {}) {
    setBusy(path)
    setOut('')
    try {
      const r = await fetch(`${API}/api/v1/simulate/${path}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ body }),
      })
      const text = await r.text()
      setOut(`[HTTP ${r.status}] ${path.toUpperCase()} → ${text.slice(0, 300)}`)
    } catch (e) {
      setOut(`[ERROR] ${path} failed: ${e}`)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="card relative overflow-hidden border border-rose-200 bg-rose-50/50 shadow-xs animate-fade-in">
      {/* Hazard stripe top bar */}
      <div className="absolute top-0 left-0 right-0 h-1 bg-[repeating-linear-gradient(45deg,#ef4444,#ef4444_10px,#fff_10px,#fff_20px)] opacity-90" />
      
      <div className="flex items-center justify-between mb-3 pt-1">
        <div className="flex items-center gap-2">
          <span className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-rose-500"></span>
          </span>
          <h3 className="text-xs font-bold font-mono tracking-wider text-rose-800 uppercase">
            SIMULATION INJECTION PANEL — DEMO CONTROLS
          </h3>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-100 text-rose-800 border border-rose-200 font-bold">
          REAL BACKEND STATE MUTATION
        </span>
      </div>

      <p className="text-xs text-slate-600 mb-4">
        Inject operational stressors directly into POLARIS state machines to demonstrate emergency protocols and AI mitigation.
      </p>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
        <button
          disabled={!!busy}
          onClick={() => fire('cargo-delay')}
          className="btn-danger text-xs py-2 px-3 flex items-center justify-center gap-1.5"
        >
          📦 Cargo Delay
        </button>
        <button
          disabled={!!busy}
          onClick={() => fire('network-outage', { online: false })}
          className="btn-danger text-xs py-2 px-3 flex items-center justify-center gap-1.5"
        >
          📡 Network Outage
        </button>
        <button
          disabled={!!busy}
          onClick={() => fire('network-outage', { online: true })}
          className="btn-secondary text-xs py-2 px-3 flex items-center justify-center gap-1.5 text-emerald-700 hover:bg-emerald-50 border-emerald-300"
        >
          📶 Restore Network
        </button>
        <button
          disabled={!!busy}
          onClick={() => fire('missed-check-in')}
          className="btn-danger text-xs py-2 px-3 flex items-center justify-center gap-1.5"
        >
          🚨 Missed Check-in
        </button>
        <button
          disabled={!!busy}
          onClick={() => fire('sos')}
          className="btn-danger text-xs py-2 px-3 flex items-center justify-center gap-1.5 bg-gradient-to-r from-red-600 to-rose-600 animate-pulse"
        >
          🆘 Trigger SOS
        </button>
        <button
          disabled={!!busy}
          onClick={() => fire('inventory-shortage')}
          className="btn-danger text-xs py-2 px-3 flex items-center justify-center gap-1.5"
        >
          ⚠️ Inventory Shortage
        </button>
        <button
          disabled={!!busy}
          onClick={() => fire('weather-event', { station: 'BHARATI' })}
          className="btn-danger text-xs py-2 px-3 flex items-center justify-center gap-1.5"
        >
          ❄️ Severe Weather
        </button>
      </div>

      {busy && (
        <div className="mt-3 text-xs text-rose-700 font-mono flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping"></span>
          Injecting event [{busy}]...
        </div>
      )}

      {out && (
        <div className="mt-3">
          <div className="text-[10px] font-mono text-slate-500 mb-1">STRESS TEST RESPONSE LOG:</div>
          <pre className="max-h-32 overflow-auto rounded-lg bg-slate-900 p-3 text-[11px] font-mono text-emerald-400 border border-slate-700 shadow-inner">
            {out}
          </pre>
        </div>
      )}
    </div>
  )
}
