import { useEffect, useState } from 'react'
import { API } from './lib/auth'

type Report = {
  id: string
  expedition_id: string
  report_date: string
  sections: Record<string, unknown>
  status: string
  published_by: string | null
}

/** Situation Reports tab: DRAFT and PUBLISHED reports with human-in-the-loop Publish workflow. */
export default function SituationReports({ token }: { token: string }) {
  const [filter, setFilter] = useState('')
  const [list, setList] = useState<Report[]>([])
  const [openId, setOpenId] = useState<string | null>(null)
  const [msg, setMsg] = useState('')

  function refresh() {
    fetch(`${API}/api/v1/situation-reports${filter ? `?status=${filter}` : ''}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : []))
      .then(setList)
      .catch(() => setList([]))
  }

  useEffect(() => {
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, filter])

  async function publish(id: string) {
    const r = await fetch(`${API}/api/v1/situation-reports/${id}/publish`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    })
    setMsg(r.ok ? '✓ Published and logged in immutable audit trail.' : `⚠️ Publish failed (${r.status}) — Requires Station/Expedition Leader role.`)
    refresh()
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3 border-b border-slate-200 pb-2">
        <h3 className="text-sm font-bold text-slate-800">Daily Situation Reports (SITREPs)</h3>
        <button onClick={refresh} className="text-xs font-mono font-bold text-sky-700 hover:text-sky-800">
          🔄 Refresh List
        </button>
      </div>

      <div className="mb-4 flex items-center gap-2">
        {['', 'DRAFT', 'PUBLISHED'].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded-lg px-3 py-1.5 text-xs font-mono transition-all ${
              filter === f
                ? 'bg-sky-600 text-white font-bold shadow-xs'
                : 'bg-slate-100 text-slate-600 border border-slate-200 hover:bg-slate-200'
            }`}
          >
            {f || 'ALL REPORTS'}
          </button>
        ))}
      </div>

      {msg && (
        <div className="mb-3 rounded-lg border border-sky-200 bg-sky-50 p-2.5 text-xs font-mono text-sky-800">
          {msg}
        </div>
      )}

      {list.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-xs text-slate-500 font-mono">
          No reports found. You can request AI synthesis via Ask POLARIS ("generate daily situation report").
        </div>
      )}

      <ul className="space-y-3">
        {list.map((r) => (
          <li key={r.id} className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-xs transition-all hover:border-sky-300">
            <button
              onClick={() => setOpenId(openId === r.id ? null : r.id)}
              className="flex w-full items-center justify-between text-left"
            >
              <div>
                <span className="font-mono text-xs font-bold text-slate-900">{r.expedition_id}</span>
                <span className="ml-2 text-xs text-slate-500">Date: {r.report_date}</span>
              </div>
              <span
                className={`rounded px-2 py-0.5 text-[10px] font-mono font-bold uppercase border ${
                  r.status === 'PUBLISHED'
                    ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
                    : 'bg-amber-100 text-amber-800 border-amber-300'
                }`}
              >
                {r.status}
              </span>
            </button>

            {openId === r.id && (
              <div className="mt-3 border-t border-slate-100 pt-3 text-xs">
                {Object.entries(r.sections).map(([k, v]) => (
                  <details key={k} className="mt-2 group">
                    <summary className="cursor-pointer font-mono font-bold text-sky-700 group-hover:text-sky-800">
                      {k}
                    </summary>
                    <pre className="mt-1 max-h-48 overflow-auto rounded-lg bg-slate-900 p-3 font-mono text-[11px] text-emerald-400 border border-slate-700">
                      {JSON.stringify(v, null, 2)}
                    </pre>
                  </details>
                ))}

                {r.status === 'DRAFT' && (
                  <button
                    onClick={() => publish(r.id)}
                    className="mt-3 btn-aurora text-xs font-mono py-1.5 px-3 flex items-center gap-1.5"
                  >
                    ⚡ Publish Report (Human-in-the-Loop Approval)
                  </button>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
