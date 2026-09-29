import { useEffect, useState } from 'react'
import { api } from '../lib/auth'

type Mission = {
  id: string
  expedition_id: string
  objective: string
  leader_id: string | null
  vehicle_id: string | null
  equipment_ids: string[]
  route: string
  check_in_interval_minutes: number
  emergency_kit: boolean
  emergency_plan: string
  status: string
}

type Check = { name: string; passed: boolean; detail: string }

const NEXT: Record<string, string[]> = {
  DRAFT: ['PLANNED', 'CANCELLED'],
  PLANNED: ['APPROVED', 'CANCELLED'],
  APPROVED: ['DEPLOYED', 'CANCELLED'],
  DEPLOYED: ['ACTIVE', 'ABORTED'],
  ACTIVE: ['RETURNED', 'ABORTED'],
  ABORTED: ['RETURNED'],
  RETURNED: ['CLOSED'],
  CLOSED: [],
  CANCELLED: [],
}

export default function Missions({ token }: { token: string }) {
  const [list, setList] = useState<Mission[]>([])
  const [sel, setSel] = useState<Mission | null>(null)
  const [checks, setChecks] = useState<Check[] | null>(null)
  const [overrideReason, setOverrideReason] = useState('')
  const [checkins, setCheckins] = useState<{ id: string; due_at: string; status: string; note: string }[]>([])
  const [comms, setComms] = useState<{ author: string; message: string; created_at: string }[]>([])
  const [members, setMembers] = useState<{ personnel_id: string; role: string }[]>([])
  const [note, setNote] = useState('')
  const [close, setClose] = useState({ summary: '', outcome: 'SUCCESS', vehicle: 'RETURNED' })
  const [eqCond, setEqCond] = useState<Record<string, string>>({})
  const [report, setReport] = useState<{ html: string; pdf_url: string } | null>(null)
  const [err, setErr] = useState('')

  async function load() {
    try {
      const data = await api<Mission[]>('/api/v1/field-missions', token)
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

  async function select(m: Mission) {
    setSel(m)
    setChecks(null)
    setReport(null)
    setErr('')
    try {
      const [cis, cms, mems] = await Promise.all([
        api<{ id: string; due_at: string; status: string; note: string }[]>(`/api/v1/field-missions/${m.id}/check-ins`, token),
        api<{ author: string; message: string; created_at: string }[]>(`/api/v1/field-missions/${m.id}/comms`, token),
        api<{ personnel_id: string; role: string }[]>(`/api/v1/field-missions/${m.id}/members`, token),
      ])
      setCheckins(cis)
      setComms(cms)
      setMembers(mems)
      const cond: Record<string, string> = {}
      m.equipment_ids.forEach((id) => (cond[id] = 'RETURNED'))
      setEqCond(cond)
      try {
        setReport(await api<{ html: string; pdf_url: string }>(`/api/v1/field-missions/${m.id}/report`, token))
      } catch {
        setReport(null)
      }
    } catch (e) {
      setErr(String(e))
    }
  }

  async function move(to: string) {
    if (!sel) return
    try {
      const updated = await api<Mission>(`/api/v1/field-missions/${sel.id}/status`, token, {
        method: 'PATCH',
        body: JSON.stringify({ to_status: to, override_reason: overrideReason }),
      })
      setSel(updated)
      setList((l) => l.map((m) => (m.id === updated.id ? updated : m)))
      setOverrideReason('')
    } catch (e) {
      setErr(`${String(e)} — for DEPLOYED with failing checks, enter an override reason (Field Leader role).`)
    }
  }

  async function runGoNoGo() {
    if (!sel) return
    const g = await api<{ all_passed: boolean; checks: Check[] }>(`/api/v1/field-missions/${sel.id}/go-no-go`, token, { method: 'POST' })
    setChecks(g.checks)
  }

  async function checkIn() {
    if (!sel) return
    await api(`/api/v1/field-missions/${sel.id}/check-in`, token, { method: 'POST', body: JSON.stringify({ note, location: '' }) })
    setNote('')
    select(sel)
  }

  async function postComms(message: string) {
    if (!sel || !message.trim()) return
    await api(`/api/v1/field-missions/${sel.id}/comms`, token, { method: 'POST', body: JSON.stringify({ message }) })
    select(sel)
  }

  async function closeMission() {
    if (!sel) return
    try {
      await api(`/api/v1/field-missions/${sel.id}/close`, token, {
        method: 'POST',
        body: JSON.stringify({ closing_summary: close.summary, outcome: close.outcome, vehicle_condition: close.vehicle, equipment: eqCond }),
      })
      const updated = await api<Mission>(`/api/v1/field-missions/${sel.id}`, token)
      setSel(updated)
      select(updated)
    } catch (e) {
      setErr(String(e))
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 flex items-center gap-3">
            <span>🚩</span> Field Missions & Traverse Operations
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Enforced state machine lifecycle with Go/No-Go safety gates, comms radio log, and automated PDF report generation.
          </p>
        </div>
      </div>

      {err && <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 font-mono">{err}</div>}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left Column: Mission Directory */}
        <div className="card lg:col-span-1">
          <div className="card-title mb-3 flex items-center justify-between">
            <span>FIELD MISSIONS ({list.length})</span>
            <span className="text-[10px] font-mono text-sky-700 font-bold">STATE ENFORCED</span>
          </div>

          <ul className="space-y-2 max-h-[520px] overflow-y-auto pr-1">
            {list.map((m) => (
              <li key={m.id}>
                <button
                  onClick={() => select(m)}
                  className={`w-full text-left p-3 rounded-xl border transition-all ${
                    sel?.id === m.id
                      ? 'border-sky-300 bg-sky-50 shadow-xs font-semibold'
                      : 'border-slate-200 bg-white hover:bg-slate-50 hover:border-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold text-slate-900">{m.id}</span>
                    <span className="rounded px-2 py-0.5 text-[10px] font-mono font-bold bg-sky-100 text-sky-800 border border-sky-200">
                      {m.status}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-slate-700 font-sans truncate">{m.objective}</div>
                  <div className="mt-1.5 text-[11px] font-mono text-slate-500 flex items-center gap-2">
                    <span>⏱ {m.check_in_interval_minutes}m ping</span>
                    <span>·</span>
                    <span>{m.emergency_kit ? '🚨 Kit Ready' : 'Standard'}</span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </div>

        {/* Right Column: Mission Detail */}
        <div className="lg:col-span-2 space-y-6">
          {!sel && <div className="card text-center py-12 text-slate-500 font-mono text-xs">Select a mission to inspect details.</div>}

          {sel && (
            <>
              {/* Status & Go/No-Go Card */}
              <div className="card">
                <div className="flex items-center justify-between border-b border-slate-200 pb-3">
                  <div>
                    <h3 className="text-base font-bold font-mono text-sky-800">{sel.id}</h3>
                    <p className="text-xs text-slate-800 mt-0.5 font-sans font-semibold">{sel.objective}</p>
                  </div>
                  <span className="rounded-lg bg-emerald-100 text-emerald-800 border border-emerald-300 px-3 py-1 text-xs font-mono font-bold">
                    {sel.status}
                  </span>
                </div>

                <div className="mt-4">
                  <div className="text-[11px] font-mono text-slate-500 font-bold mb-2">ADVANCE MISSION LIFECYCLE:</div>
                  <div className="flex flex-wrap gap-2">
                    {(NEXT[sel.status] ?? []).map((s) => (
                      <button
                        key={s}
                        onClick={() => move(s)}
                        className="btn-aurora text-xs py-1.5 px-3 font-mono"
                      >
                        → {s}
                      </button>
                    ))}
                  </div>

                  <input
                    value={overrideReason}
                    onChange={(e) => setOverrideReason(e.target.value)}
                    placeholder="Override reason (Required for DEPLOYED state if safety checks fail)"
                    className="input mt-3 text-xs font-mono"
                  />
                </div>

                <div className="mt-5 border-t border-slate-200 pt-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="card-title">SAFETY & GO/NO-GO PROTOCOL CHECK</span>
                    <button onClick={runGoNoGo} className="btn-secondary text-xs font-mono py-1 px-3">
                      ⚡ Execute Safety Gate Check
                    </button>
                  </div>

                  {checks && (
                    <ul className="mt-3 space-y-1.5 font-mono text-xs bg-slate-50 p-3 rounded-xl border border-slate-200">
                      {checks.map((c) => (
                        <li key={c.name} className={`flex items-center gap-2 ${c.passed ? 'text-emerald-700 font-bold' : 'text-rose-700 font-bold'}`}>
                          <span>{c.passed ? '✓' : '✕'}</span>
                          <span className="uppercase">{c.name}:</span>
                          <span className="text-slate-800 font-normal">{c.detail}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>

              {/* Check-ins & Comms Radio */}
              <div className="card">
                <div className="flex items-center justify-between mb-3 border-b border-slate-200 pb-2">
                  <span className="card-title">SCHEDULED CHECK-INS ({checkins.length}) · TEAM ({members.length})</span>
                  <span className="text-[10px] font-mono text-sky-700 font-bold">INTERVAL: {sel.check_in_interval_minutes} MIN</span>
                </div>

                <ul className="max-h-36 space-y-1.5 overflow-auto text-xs font-mono pr-1 mb-4">
                  {checkins.map((c) => (
                    <li key={c.id} className="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-200">
                      <span className="text-slate-500">{c.due_at.slice(0, 16).replace('T', ' ')}</span>
                      <span className={`font-bold ${c.status === 'RECEIVED' ? 'text-emerald-700' : 'text-rose-700'}`}>{c.status}</span>
                      <span className="text-slate-800 truncate max-w-xs">{c.note || 'Regular scheduled check-in'}</span>
                    </li>
                  ))}
                </ul>

                <div className="flex gap-2">
                  <input
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="Enter manual check-in radio note..."
                    className="input flex-1 text-xs"
                  />
                  <button onClick={checkIn} className="btn-aurora text-xs px-4">
                    Record Check-In
                  </button>
                </div>

                <div className="card-title mt-5 mb-2">RADIO COMMS CHANNEL LOG</div>
                <div className="max-h-32 overflow-y-auto space-y-1 font-mono text-xs bg-slate-900 text-slate-100 p-3 rounded-xl border border-slate-700 mb-2">
                  {comms.map((c, i) => (
                    <div key={i} className="text-slate-200">
                      <span className="text-cyan-400 font-bold">{c.author}:</span> {c.message}
                    </div>
                  ))}
                  {comms.length === 0 && <div className="text-slate-400 italic">No radio logs recorded.</div>}
                </div>
                <CommsBox onPost={postComms} />
              </div>

              {/* Closeout Panel */}
              <div className="card">
                <div className="card-title mb-3">MISSION DEBRIEF & CLOSEOUT</div>
                <input
                  value={close.summary}
                  onChange={(e) => setClose({ ...close, summary: e.target.value })}
                  placeholder="Closing summary narrative (required)"
                  className="input text-xs mb-3"
                />

                <div className="flex flex-wrap gap-3">
                  <select
                    value={close.outcome}
                    onChange={(e) => setClose({ ...close, outcome: e.target.value })}
                    className="input text-xs font-mono !w-auto"
                  >
                    {['SUCCESS', 'PARTIAL', 'ABORTED'].map((o) => (
                      <option key={o} value={o}>{o}</option>
                    ))}
                  </select>

                  {sel.vehicle_id && (
                    <select
                      value={close.vehicle}
                      onChange={(e) => setClose({ ...close, vehicle: e.target.value })}
                      className="input text-xs font-mono !w-auto"
                    >
                      {['RETURNED', 'LOST', 'DAMAGED'].map((o) => (
                        <option key={o} value={o}>Vehicle: {o}</option>
                      ))}
                    </select>
                  )}

                  {sel.equipment_ids.map((id) => (
                    <select
                      key={id}
                      value={eqCond[id] ?? 'RETURNED'}
                      onChange={(e) => setEqCond({ ...eqCond, [id]: e.target.value })}
                      className="input text-xs font-mono !w-auto"
                    >
                      {['RETURNED', 'LOST', 'DAMAGED'].map((o) => (
                        <option key={o} value={o}>Equip {id.slice(0, 8)}… {o}</option>
                      ))}
                    </select>
                  ))}

                  <button onClick={closeMission} className="btn-danger text-xs px-4">
                    Close Mission & Log Audit
                  </button>
                </div>

                {report && (
                  <div className="mt-4 rounded-xl border border-sky-200 bg-sky-50 p-4">
                    <a
                      href={`${(import.meta.env.VITE_API_URL as string) || 'http://localhost:8000'}${report.pdf_url}`}
                      target="_blank"
                      rel="noreferrer"
                      className="font-mono text-xs font-bold text-sky-800 hover:underline flex items-center gap-1.5"
                    >
                      📄 Download Official Expedition Mission PDF Report →
                    </a>
                    <div
                      className="prose mt-3 max-h-64 overflow-auto rounded-lg border border-slate-200 bg-white p-3 text-xs"
                      dangerouslySetInnerHTML={{ __html: report.html }}
                    />
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function CommsBox({ onPost }: { onPost: (m: string) => void }) {
  const [v, setV] = useState('')
  return (
    <div className="flex gap-2">
      <input
        value={v}
        onChange={(e) => setV(e.target.value)}
        placeholder="Post VHF radio comms transcript..."
        className="input text-xs flex-1"
      />
      <button onClick={() => { onPost(v); setV('') }} className="btn-secondary text-xs px-4">
        Post Radio
      </button>
    </div>
  )
}
