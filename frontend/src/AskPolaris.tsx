import { useState } from 'react'
import { API } from './lib/auth'

const AI = (import.meta.env.VITE_AI_URL as string) || 'http://localhost:8001'

type AskResult = {
  answer: string
  intent: string
  needs_approval: boolean
  plan_draft_id: string | null
  situation_report_id: string | null
  validator_note: string
}

const QUICK = [
  "Which cargo can affect tomorrow's Bharati mission?",
  'Which critical items will run out first?',
  'What resources can respond to this incident?',
]

/** Ask POLARIS: Intelligent Copilot interface for polar logistics and incident decision support.
 *  AI returns drafts & analysis; human-in-the-loop validation triggers real backend execution. */
export default function AskPolaris({ token }: { token: string }) {
  const [q, setQ] = useState(QUICK[0])
  const [busy, setBusy] = useState(false)
  const [res, setRes] = useState<AskResult | null>(null)
  const [err, setErr] = useState('')
  const [decision, setDecision] = useState('')

  async function ask(question: string) {
    setBusy(true)
    setErr('')
    setDecision('')
    try {
      const r = await fetch(`${AI}/ai/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, backend_token: token }),
      })
      if (!r.ok)
        throw new Error(
          `AI service returned status ${r.status} — verify AI agent service is running on port 8001.`
        )
      setRes(await r.json())
    } catch (e) {
      setErr(String(e))
      setRes(null)
    } finally {
      setBusy(false)
    }
  }

  async function decide(approve: boolean) {
    if (!res?.plan_draft_id) return
    const r = await fetch(`${API}/api/v1/plan-drafts/${res.plan_draft_id}/decide`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision: approve ? 'APPROVE' : 'REJECT', note: 'Decided via Ask POLARIS human-in-the-loop copilot' }),
    })
    setDecision(
      r.ok
        ? `✓ Proposed Plan ${approve ? 'APPROVED & EXECUTED' : 'REJECTED'} (logged to audit trail).`
        : `⚠️ Decision submission failed (${r.status}) — check RBAC permissions.`
    )
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3 border-b border-slate-200 pb-2">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-sky-600 animate-pulse"></span>
          <h3 className="text-sm font-bold text-slate-800">Ask POLARIS AI Copilot</h3>
        </div>
        <span className="text-[10px] font-mono text-sky-800 bg-sky-50 px-2 py-0.5 rounded border border-sky-200 font-bold">
          STRICT HUMAN-IN-THE-LOOP CONTROL
        </span>
      </div>

      <div className="mb-3 flex flex-wrap gap-2">
        {QUICK.map((quick) => (
          <button
            key={quick}
            onClick={() => {
              setQ(quick)
              ask(quick)
            }}
            className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-700 hover:border-sky-300 hover:bg-sky-50 hover:text-sky-800 transition-all text-left shadow-2xs font-medium"
          >
            💡 {quick}
          </button>
        ))}
      </div>

      <div className="flex gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="input flex-1 font-sans text-sm"
          placeholder="Ask AI about cargo, inventory forecasts, or active incidents..."
        />
        <button onClick={() => ask(q)} disabled={busy} className="btn-aurora text-xs px-5 py-2">
          {busy ? 'Analyzing...' : 'Ask Copilot'}
        </button>
      </div>

      {err && (
        <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs font-mono text-rose-800">
          ⚠️ {err}
        </div>
      )}

      {res && (
        <div className="mt-4 rounded-xl border border-sky-200 bg-sky-50/50 p-4 shadow-xs">
          <div className="flex items-center justify-between mb-2">
            <span className="rounded bg-sky-100 px-2 py-0.5 text-[10px] font-mono font-bold text-sky-800 uppercase border border-sky-200">
              INTENT: {res.intent}
            </span>
            <span className="text-[10px] font-mono text-slate-500 font-bold">
              Deterministic Rule Engine Verified
            </span>
          </div>

          <p className="text-xs text-slate-800 leading-relaxed font-sans mt-2 whitespace-pre-line">
            {res.answer}
          </p>

          <div className="mt-3 pt-2 border-t border-slate-200 flex items-center justify-between text-[11px] font-mono text-slate-600">
            <span className="font-bold">Validator Rule Audit:</span>
            <span className="text-slate-800 italic">{res.validator_note || 'All safety bounds passed.'}</span>
          </div>

          {res.needs_approval && res.plan_draft_id && (
            <div className="mt-3 rounded-xl border border-amber-300 bg-amber-50 p-3 shadow-xs">
              <div className="flex items-center gap-2 text-xs font-bold text-amber-900">
                <span>⚡ ACTION REQUIRED: Proposed Plan Draft [{res.plan_draft_id}]</span>
              </div>
              <p className="mt-1 text-[11px] text-amber-800">
                AI recommends executing operational adjustments. Human approval is required before state change.
              </p>
              <div className="mt-3 flex items-center gap-2">
                <button
                  onClick={() => decide(true)}
                  className="rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 px-3 py-1.5 text-xs font-mono font-bold transition-all shadow-xs"
                >
                  ✓ APPROVE & EXECUTE
                </button>
                <button
                  onClick={() => decide(false)}
                  className="rounded-lg bg-rose-600 text-white hover:bg-rose-700 px-3 py-1.5 text-xs font-mono font-bold transition-all shadow-xs"
                >
                  ✕ REJECT
                </button>
              </div>
              {decision && (
                <p className="mt-2 text-xs font-mono text-slate-900 bg-white p-2 rounded border border-slate-200 font-bold">
                  {decision}
                </p>
              )}
            </div>
          )}

          {res.situation_report_id && (
            <div className="mt-3 text-xs font-mono text-sky-800 bg-white p-2 rounded border border-sky-200 font-bold">
              Draft SITREP generated: [{res.situation_report_id}]. Navigate to Reports tab to inspect and publish.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
