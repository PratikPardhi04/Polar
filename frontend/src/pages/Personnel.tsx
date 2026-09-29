import { useEffect, useState } from 'react'
import { api } from '../lib/auth'

type Person = { id: string; full_name: string; email: string; role: string; current_readiness: string }

const CHAIN = [
  'NOMINATED',
  'DOCUMENTS_PENDING',
  'MEDICAL_SCHEDULED',
  'MEDICAL_CLEARED',
  'TRAINING_COMPLETED',
  'MISSION_READY',
  'INDUCTED',
  'AT_STATION',
  'FIELD_DEPLOYED',
  'DE_INDUCTION_SCHEDULED',
  'RETURNED',
  'CLOSED_OUT',
]

export default function Personnel({ token }: { token: string }) {
  const [list, setList] = useState<Person[]>([])
  const [q, setQ] = useState('')
  const [filter, setFilter] = useState('')
  const [sel, setSel] = useState<Person | null>(null)
  const [moves, setMoves] = useState<{ from_state: string | null; to_state: string; reason: string }[]>([])
  const [err, setErr] = useState('')

  async function load() {
    try {
      const qs = new URLSearchParams()
      if (q) qs.set('q', q)
      if (filter) qs.set('readiness', filter)
      const data = await api<Person[]>(`/api/v1/personnel?${qs}`, token)
      setList(data)
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

  async function select(p: Person) {
    setSel(p)
    try {
      setMoves(await api<{ from_state: string | null; to_state: string; reason: string }[]>(`/api/v1/personnel/${p.id}/movements`, token))
    } catch {
      setMoves([])
    }
  }

  async function advance() {
    if (!sel) return
    const next = CHAIN[CHAIN.indexOf(sel.current_readiness) + 1]
    if (!next) return
    try {
      const u = await api<Person>(`/api/v1/personnel/${sel.id}/readiness`, token, { method: 'PATCH', body: JSON.stringify({ to_state: next }) })
      setSel(u)
      load()
    } catch (e) {
      setErr(String(e))
    }
  }

  const currentIdx = sel ? CHAIN.indexOf(sel.current_readiness) : -1

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 flex items-center gap-3">
            <span>👨‍🔬</span> Expedition Personnel & Readiness Pipeline
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Enforced 12-stage medical, training, and deployment readiness lifecycle with audited movement logs.
          </p>
        </div>
      </div>

      {err && <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 font-mono">{err}</div>}

      <div className="flex flex-wrap items-center gap-3 bg-white p-3 rounded-2xl border border-slate-200 shadow-xs">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && load()}
          placeholder="🔍 Search by name or email..."
          className="input text-xs max-w-xs font-sans"
        />
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="input text-xs font-mono !w-auto"
        >
          <option value="">All Readiness States</option>
          {CHAIN.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <button onClick={load} className="btn-aurora text-xs py-1.5 px-4">
          Apply Search
        </button>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left Column: Personnel Roster */}
        <div className="card lg:col-span-1">
          <div className="card-title mb-3 flex items-center justify-between">
            <span>EXPEDITION ROSTER ({list.length})</span>
            <span className="text-[10px] font-mono text-sky-700 font-bold">STATE CONTROLLED</span>
          </div>

          <ul className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
            {list.map((p) => (
              <li key={p.id}>
                <button
                  onClick={() => select(p)}
                  className={`w-full text-left p-3 rounded-xl border transition-all ${
                    sel?.id === p.id
                      ? 'border-sky-300 bg-sky-50 shadow-xs font-semibold'
                      : 'border-slate-200 bg-white hover:bg-slate-50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-xs text-slate-900">{p.full_name}</span>
                    <span className="rounded px-2 py-0.5 text-[9px] font-mono font-bold bg-sky-100 text-sky-800 border border-sky-200">
                      {p.role}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-slate-500 font-mono">{p.email}</div>
                  <div className="mt-2 flex items-center gap-1 text-[10px] font-mono text-emerald-700 font-bold">
                    <span>STATUS:</span>
                    <span>{p.current_readiness}</span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </div>

        {/* Right Column: Personnel Detail & Timeline */}
        <div className="lg:col-span-2 space-y-6">
          {!sel && <div className="card text-center py-12 text-slate-500 font-mono text-xs">Select team member to inspect.</div>}

          {sel && (
            <div className="card space-y-5">
              <div className="flex items-center justify-between border-b border-slate-200 pb-3">
                <div>
                  <h3 className="text-lg font-bold text-slate-900">{sel.full_name}</h3>
                  <p className="text-xs font-mono text-sky-800 mt-0.5 font-semibold">{sel.email} · Role: {sel.role}</p>
                </div>
                <span className="rounded-lg bg-emerald-100 text-emerald-800 border border-emerald-300 px-3 py-1 text-xs font-mono font-bold">
                  {sel.current_readiness}
                </span>
              </div>

              {/* Readiness Pipeline Progress bar */}
              <div>
                <div className="text-[11px] font-mono text-slate-500 font-bold mb-2">12-STAGE READINESS PIPELINE:</div>
                <div className="flex items-center gap-1 overflow-x-auto pb-2">
                  {CHAIN.map((stage, idx) => (
                    <div
                      key={stage}
                      className={`flex-1 min-w-[28px] h-2.5 rounded-full transition-all ${
                        idx <= currentIdx
                          ? 'bg-gradient-to-r from-sky-500 to-indigo-600 shadow-xs'
                          : 'bg-slate-200'
                      }`}
                      title={`${idx + 1}. ${stage}`}
                    />
                  ))}
                </div>
                <div className="flex justify-between text-[10px] font-mono text-slate-500 mt-1 font-semibold">
                  <span>NOMINATED</span>
                  <span>MISSION_READY</span>
                  <span>CLOSED_OUT</span>
                </div>
              </div>

              {currentIdx < CHAIN.length - 1 && (
                <button onClick={advance} className="btn-aurora text-xs py-2 px-5 font-mono">
                  ⚡ Advance Readiness → {CHAIN[currentIdx + 1]}
                </button>
              )}

              {/* Movement History */}
              <div className="border-t border-slate-200 pt-4">
                <div className="card-title mb-3">READINESS TRANSITION AUDIT TRAIL</div>
                <div className="max-h-64 overflow-y-auto space-y-2 font-mono text-xs pr-1">
                  {moves.map((m, i) => (
                    <div key={i} className="p-3 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between">
                      <div>
                        <span className="text-slate-500">{m.from_state ?? 'INITIAL'}</span>
                        <span className="text-sky-700 font-bold mx-2">→</span>
                        <span className="text-emerald-700 font-bold">{m.to_state}</span>
                      </div>
                      <span className="text-[11px] text-slate-500 italic">{m.reason || 'Standard progression'}</span>
                    </div>
                  ))}
                  {moves.length === 0 && <div className="text-slate-500 italic text-xs">No movement history logged.</div>}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
