import { useState } from 'react'
import { AI_URL, API } from '../lib/auth'

type PlanLine = {
  item_id: string
  name: string
  category: string
  on_hand: number
  unit: string
  avg_daily_use: number
  rate_basis: string
  days_left: number | null
  status: string
  suggested_qty: number
  action: string
}

type Plan = {
  kind: string
  horizon_days: number
  generated_at: string
  crew_size: number
  crew_note: string
  summary: { items_covered: number; 'ORDER NOW': number; WATCH: number; OK: number; STABLE: number; total_suggested_qty: number }
  risks: string[]
  lines: PlanLine[]
  plan_draft_id: string
  approval_note: string
}

type DecideResult = {
  status: string
  follow_up_draft_id: string | null
}

const KINDS = [
  { id: 'FOOD', title: 'Food Consumption Plan', desc: 'Meals, staples and perishables burn rate vs stock' },
  { id: 'SUPPLIES', title: 'Supplies Usage Plan', desc: 'Fuel, medical, tools, spares — everything but food' },
  { id: 'FULL', title: 'Full Expedition Plan', desc: 'Every tracked category in one horizon' },
]

const STATUS_STYLE: Record<string, string> = {
  'ORDER NOW': 'bg-red-600',
  WATCH: 'bg-amber-500',
  OK: 'bg-emerald-600',
  STABLE: 'bg-slate-400',
}

/** Generate Plan: the AI checks live inventory + forecast and composes a
 *  horizon consumption plan, saved as a DRAFT. A human APPROVEs it — the AI
 *  never orders anything itself. */
export default function GeneratePlan({ token }: { token: string }) {
  const [kind, setKind] = useState('FULL')
  const [horizon, setHorizon] = useState(14)
  const [busy, setBusy] = useState(false)
  const [plan, setPlan] = useState<Plan | null>(null)
  const [err, setErr] = useState('')
  const [decision, setDecision] = useState('')
  const [planB, setPlanB] = useState<string | null>(null)

  async function generate() {
    setBusy(true)
    setErr('')
    setDecision('')
    setPlanB(null)
    try {
      const r = await fetch(`${AI_URL}/ai/plan/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind, horizon_days: horizon, backend_token: token }),
      })
      if (!r.ok) throw new Error(`AI service ${r.status} — is it running? (uvicorn main:app --app-dir ai --port 8001)`)
      setPlan(await r.json())
    } catch (e) {
      setErr(String(e))
      setPlan(null)
    } finally {
      setBusy(false)
    }
  }

  async function decide(draftId: string, approve: boolean) {
    const r = await fetch(`${API}/api/v1/plan-drafts/${draftId}/decide`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision: approve ? 'APPROVE' : 'REJECT', note: `decided from Generate Plan (${plan?.kind})` }),
    })
    if (!r.ok) {
      setDecision(`Decision failed (${r.status}) — check your role`)
      return
    }
    const body = (await r.json()) as DecideResult
    setDecision(`Plan ${approve ? 'APPROVED' : 'REJECTED'} (audited)`)
    setPlanB(!approve && body.follow_up_draft_id ? body.follow_up_draft_id : null)
  }

  return (
    <div>
      <h1 className="text-2xl font-bold">Generate Plan</h1>
      <p className="text-sm text-slate-500">AI reads live stock + burn rates, projects a horizon, drafts the plan. You approve.</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {KINDS.map((k) => (
          <button
            key={k.id}
            onClick={() => setKind(k.id)}
            className={`rounded-xl p-4 text-left ring-1 transition ${kind === k.id ? 'bg-sky-700 text-white ring-sky-700' : 'bg-white ring-slate-200 hover:ring-sky-400'}`}
          >
            <div className="font-bold">{k.title}</div>
            <div className={`mt-1 text-xs ${kind === k.id ? 'text-sky-100' : 'text-slate-500'}`}>{k.desc}</div>
          </button>
        ))}
      </div>
      <div className="mt-3 flex items-center gap-2">
        <label className="text-sm text-slate-600">Horizon (days)</label>
        <input value={horizon} onChange={(e) => setHorizon(Number(e.target.value))} type="number" min={1} max={180} className="input max-w-28" />
        <button onClick={generate} disabled={busy} className="btn-primary">{busy ? 'Composing…' : 'Generate plan'}</button>
      </div>
      {err && <p className="mt-3 text-sm text-red-600">{err}</p>}
      {plan && (
        <div className="mt-4 space-y-4">
          <div className="card">
            <div className="flex flex-wrap items-center gap-3">
              <span className="font-bold">{plan.kind} plan · {plan.horizon_days}d horizon</span>
              <span className="text-xs text-slate-500">{plan.summary['ORDER NOW']} order-now · {plan.summary.WATCH} watch · {plan.summary.OK + plan.summary.STABLE} healthy</span>
              <span className="ml-auto text-xs text-slate-500">draft {plan.plan_draft_id.slice(0, 8)}… · crew: {plan.crew_size} ({plan.crew_note})</span>
            </div>
            <ul className="mt-2 space-y-1 text-sm">
              {plan.risks.map((r, i) => <li key={i} className="text-red-700">⚠ {r}</li>)}
            </ul>
            <div className="mt-2 flex gap-2">
              <button onClick={() => plan && decide(plan.plan_draft_id, true)} className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-bold text-white">APPROVE plan</button>
              <button onClick={() => plan && decide(plan.plan_draft_id, false)} className="btn-secondary text-sm">Reject</button>
            </div>
            {decision && <p className="mt-1 text-xs">{decision}</p>}
            {planB && (
              <div className="mt-2 rounded-lg bg-sky-50 p-2 ring-1 ring-sky-300">
                <p className="text-xs font-bold text-sky-800">Plan B auto-drafted (rationed −20%) — {planB.slice(0, 8)}…</p>
                <button onClick={() => decide(planB, true)} className="mt-1 rounded-lg bg-emerald-600 px-2 py-1 text-xs font-bold text-white">APPROVE Plan B</button>
              </div>
            )}
            <p className="mt-1 text-[11px] text-slate-400">{plan.approval_note}</p>
          </div>
          <div className="card overflow-x-auto">
            <table className="table text-sm">
              <thead><tr><th>item</th><th>on hand</th><th>burn/day</th><th>days left</th><th>status</th><th>suggested</th><th>action</th></tr></thead>
              <tbody>
                {plan.lines.map((l) => (
                  <tr key={l.item_id}>
                    <td className="font-semibold">{l.name} <span className="font-normal text-slate-400">({l.category})</span></td>
                    <td>{l.on_hand} {l.unit}</td>
                    <td>{l.avg_daily_use}<div className="text-[10px] text-slate-400">{l.rate_basis.includes('norm') ? 'polar norm' : 'observed'}</div></td>
                    <td>{l.days_left ?? '—'}</td>
                    <td><span className={`rounded px-1.5 py-0.5 text-[11px] font-bold text-white ${STATUS_STYLE[l.status] ?? 'bg-slate-500'}`}>{l.status}</span></td>
                    <td>{l.suggested_qty} {l.unit}</td>
                    <td className="max-w-xs text-xs text-slate-500">{l.action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
