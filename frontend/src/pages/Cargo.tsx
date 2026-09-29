import { useEffect, useState } from 'react'
import { api } from '../lib/auth'

type Shipment = { id: string; expedition_id: string; origin: string; destination: string; status: string; current_location: string }
type Pkg = { id: string; description: string; weight_kg: number; status: string; location: string; qr_code: string }
type Doc = { id: string; doc_type: string; status: string }

const CARGO_STATES = ['DECLARED', 'VERIFIED', 'PACKED', 'INSPECTED', 'DISPATCHED', 'IN_TRANSIT', 'AT_GATEWAY', 'LOADED', 'ARRIVED_ANTARCTICA', 'RECEIVED_AT_STATION', 'STORED', 'DELAYED', 'DAMAGED', 'MISSING', 'QUARANTINED', 'RETURNED', 'CANCELLED']

export default function Cargo({ token }: { token: string }) {
  const [ships, setShips] = useState<Shipment[]>([])
  const [sel, setSel] = useState<Shipment | null>(null)
  const [pkgs, setPkgs] = useState<Pkg[]>([])
  const [docs, setDocs] = useState<Doc[]>([])
  const [scan, setScan] = useState({ id: '', status: 'RECEIVED_AT_STATION', location: '' })
  const [scanOut, setScanOut] = useState('')
  const [err, setErr] = useState('')

  async function load() {
    try {
      const data = await api<Shipment[]>('/api/v1/shipments', token)
      setShips(data)
      if (data.length > 0 && !sel) {
        select(data[0])
      }
    } catch (e) {
      setErr(String(e))
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  async function select(s: Shipment) {
    setSel(s)
    setScanOut('')
    try {
      const [p, d] = await Promise.all([
        api<Pkg[]>(`/api/v1/shipments/${s.id}/packages`, token),
        api<Doc[]>(`/api/v1/shipments/${s.id}/documents`, token),
      ])
      setPkgs(p)
      setDocs(d)
    } catch (e) {
      setPkgs([])
      setDocs([])
    }
  }

  async function doScan() {
    try {
      const r = await api<{ detail: string }>(`/api/v1/scan`, token, {
        method: 'POST',
        body: JSON.stringify({ package_id: scan.id, to_status: scan.status || undefined, location: scan.location || undefined }),
      })
      setScanOut(`✓ ${r.detail}`)
      if (sel) select(sel)
    } catch (e) {
      setScanOut(`⚠️ ${e}`)
    }
  }

  async function moveShip(to: string) {
    if (!sel) return
    try {
      const u = await api<Shipment>(`/api/v1/shipments/${sel.id}/status`, token, { method: 'PATCH', body: JSON.stringify({ to_status: to }) })
      setSel(u)
      load()
    } catch (e) {
      setErr(String(e))
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 flex items-center gap-3">
            <span>📦</span> Expedition Cargo & QR Operations
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            End-to-end supply chain tracking from Goa HQ to Bharati Station via Cape Town staging hub.
          </p>
        </div>
      </div>

      {err && <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 font-mono">{err}</div>}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left Column: Shipment List */}
        <div className="card lg:col-span-1">
          <div className="card-title mb-3 flex items-center justify-between">
            <span>ACTIVE SHIPMENTS ({ships.length})</span>
            <span className="text-[10px] font-mono text-sky-700 font-bold">REAL-TIME STATUS</span>
          </div>

          <ul className="space-y-2 max-h-[520px] overflow-y-auto pr-1">
            {ships.map((s) => (
              <li key={s.id}>
                <button
                  onClick={() => select(s)}
                  className={`w-full text-left p-3 rounded-xl border transition-all ${
                    sel?.id === s.id
                      ? 'border-sky-300 bg-sky-50 shadow-xs font-semibold'
                      : 'border-slate-200 bg-white hover:bg-slate-50 hover:border-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold text-slate-900">{s.id.slice(0, 10)}…</span>
                    <span className="rounded px-2 py-0.5 text-[10px] font-mono font-bold bg-sky-100 text-sky-800 border border-sky-200">
                      {s.status}
                    </span>
                  </div>
                  <div className="mt-2 text-xs text-slate-600 flex items-center gap-1.5">
                    <span>📍</span>
                    <span>{s.origin}</span>
                    <span>→</span>
                    <span>{s.destination}</span>
                  </div>
                  <div className="mt-1 text-[11px] font-mono text-slate-500">Loc: {s.current_location}</div>
                </button>
              </li>
            ))}
          </ul>
        </div>

        {/* Right Column: Selected Shipment Detail & QR Scan Tool */}
        <div className="space-y-6 lg:col-span-2">
          {sel && (
            <div className="card">
              <div className="flex items-center justify-between border-b border-slate-200 pb-3">
                <div>
                  <h3 className="text-base font-bold font-mono text-sky-800">
                    SHIPMENT #{sel.id}
                  </h3>
                  <p className="text-xs text-slate-600 mt-0.5">
                    Route: <span className="text-slate-900 font-semibold">{sel.origin}</span> to <span className="text-slate-900 font-semibold">{sel.destination}</span>
                  </p>
                </div>
                <span className="rounded-lg bg-emerald-100 text-emerald-800 border border-emerald-300 px-3 py-1 text-xs font-mono font-bold">
                  {sel.status}
                </span>
              </div>

              <div className="mt-4">
                <div className="text-[11px] font-mono text-slate-500 font-bold mb-2">UPDATE SHIPMENT STATE MACHINE:</div>
                <div className="flex flex-wrap gap-1.5">
                  {['DELAYED', 'IN_TRANSIT', 'ARRIVED_ANTARCTICA', 'RECEIVED_AT_STATION', 'STORED'].map((s) => (
                    <button
                      key={s}
                      onClick={() => moveShip(s)}
                      className="rounded bg-white hover:bg-sky-50 border border-slate-300 px-2.5 py-1 text-xs font-mono font-semibold text-slate-700 transition-all shadow-2xs"
                    >
                      → {s}
                    </button>
                  ))}
                </div>
              </div>

              {/* Documents */}
              <div className="mt-5 border-t border-slate-200 pt-4">
                <div className="card-title mb-2">COMPLIANCE & MANIFEST DOCUMENTS ({docs.length})</div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {docs.map((d) => (
                    <div key={d.id} className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-xs font-mono">
                      <span className="text-slate-800 font-medium">📄 {d.doc_type}</span>
                      <span className="text-emerald-700 font-bold text-[10px]">{d.status}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Packages */}
              <div className="mt-5 border-t border-slate-200 pt-4">
                <div className="card-title mb-2">CONSIGNED QR PACKAGES ({pkgs.length})</div>
                <div className="max-h-56 overflow-y-auto space-y-1.5 pr-1">
                  {pkgs.map((p) => (
                    <div key={p.id} className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-xs">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-sky-700 font-bold">{p.id}</span>
                        <span className="text-slate-800 truncate max-w-xs">{p.description || 'General Expedition Consignment'}</span>
                      </div>
                      <div className="flex items-center gap-3 font-mono text-[11px]">
                        <span className="text-slate-500">{p.weight_kg} kg</span>
                        <span className="rounded bg-sky-100 text-sky-800 px-1.5 py-0.5 border border-sky-200 font-bold">{p.status}</span>
                        <button
                          onClick={() => { setScan((s) => ({ ...s, id: p.id })); document.getElementById('qr-scan-id')?.focus() }}
                          title="Load this package into the scanner below (avoids typos)"
                          className="rounded bg-sky-600 px-2 py-0.5 font-bold text-white hover:bg-sky-700"
                        >
                          SCAN →
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* QR Scanner Tool */}
          <div className="card border-sky-200 shadow-xs">
            <div className="card-title mb-3 flex items-center gap-2">
              <span>📱</span> QUICK QR SCANNER / PACKAGE INGESTION
            </div>
            <div className="grid gap-3 sm:grid-cols-4">
              <input
                id="qr-scan-id"
                value={scan.id}
                onChange={(e) => setScan({ ...scan, id: e.target.value })}
                placeholder="Package ID (e.g. BX-46-2026-000001 — use SCAN → above, never type it)"
                className="input sm:col-span-2 font-mono text-xs"
              />
              <select
                value={scan.status}
                onChange={(e) => setScan({ ...scan, status: e.target.value })}
                className="input font-mono text-xs"
              >
                {CARGO_STATES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              <input
                value={scan.location}
                onChange={(e) => setScan({ ...scan, location: e.target.value })}
                placeholder="Checkpoint Loc"
                className="input font-mono text-xs"
              />
            </div>

            <div className="mt-3 flex items-center gap-3">
              <button onClick={doScan} className="btn-aurora text-xs py-2 px-6">
                ⚡ Process QR Scan Event
              </button>
              {scanOut && (
                <span className="text-xs font-mono text-sky-800 bg-sky-50 p-2 rounded border border-sky-200 font-bold">
                  {scanOut}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
