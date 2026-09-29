import { useEffect, useState } from 'react'
import { API } from './lib/auth'

type AuditRow = {
  id: string
  created_at: string | null
  actor_email: string | null
  action: string
  entity_type: string
  entity_id: string
  old_value: string | null
  new_value: string | null
  reason: string | null
}

/** Audit & Compliance: read-only view over AuditEvent (+ sessions, notifications,
 *  conflicts). Filter by entity, actor, action, date range; free-text search; CSV export. */
export default function AuditCompliance({ token }: { token: string }) {
  const [tab, setTab] = useState<'events' | 'sessions' | 'notifications' | 'conflicts'>('events')
  const [rows, setRows] = useState<AuditRow[]>([])
  const [other, setOther] = useState<Record<string, unknown>[]>([])
  const [f, setF] = useState({ entity_type: '', entity_id: '', actor: '', action: '', since: '', until: '', search: '' })

  function query(extra = '') {
    const qs = new URLSearchParams()
    Object.entries({ ...f, limit: '100', ...Object.fromEntries(new URLSearchParams(extra)) }).forEach(([k, v]) => {
      if (v) qs.set(k, String(v))
    })
    return qs.toString()
  }

  function refresh() {
    const h = { Authorization: `Bearer ${token}` }
    if (tab === 'events') {
      fetch(`${API}/api/v1/audit/events?${query()}`, { headers: h })
        .then((r) => (r.ok ? r.json() : []))
        .then(setRows)
        .catch(() => setRows([]))
    } else if (tab === 'sessions') {
      fetch(`${API}/api/v1/audit/sessions`, { headers: h })
        .then((r) => (r.ok ? r.json() : []))
        .then(setOther)
        .catch(() => setOther([]))
    } else if (tab === 'notifications') {
      fetch(`${API}/api/v1/notifications`, { headers: h })
        .then((r) => (r.ok ? r.json() : []))
        .then(setOther)
        .catch(() => setOther([]))
    } else {
      fetch(`${API}/api/v1/sync/conflicts?status=ALL`, { headers: h })
        .then((r) => (r.ok ? r.json() : []))
        .then(setOther)
        .catch(() => setOther([]))
    }
  }

  useEffect(() => {
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, tab])

  async function exportCsv() {
    const r = await fetch(`${API}/api/v1/audit/events/export?${query()}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    const blob = await r.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'polaris_audit_export.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  const filterInput = 'input !w-auto text-xs font-mono py-1 px-2.5 bg-white border-slate-300'

  return (
    <div className="card">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3 border-b border-slate-200 pb-2">
        <div className="flex items-center gap-1.5">
          {(['events', 'sessions', 'notifications', 'conflicts'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded-lg px-3 py-1 text-xs font-mono transition-all ${
                tab === t
                  ? 'bg-sky-600 text-white font-bold shadow-xs'
                  : 'bg-slate-100 text-slate-600 border border-slate-200 hover:bg-slate-200'
              }`}
            >
              {t.toUpperCase()}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <button onClick={refresh} className="text-xs font-mono font-bold text-sky-700 hover:text-sky-800">
            🔄 Refresh
          </button>
          {tab === 'events' && (
            <button
              onClick={exportCsv}
              className="rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white px-3 py-1 text-xs font-mono font-bold transition-all flex items-center gap-1 shadow-xs"
            >
              📥 Export CSV
            </button>
          )}
        </div>
      </div>

      {tab === 'events' && (
        <div className="mb-3 flex flex-wrap items-center gap-2 bg-slate-50 p-2.5 rounded-xl border border-slate-200">
          <input
            value={f.search}
            onChange={(e) => setF({ ...f, search: e.target.value })}
            placeholder="🔍 Search (e.g. BX-0042)"
            className={`${filterInput} w-44`}
          />
          <input
            value={f.entity_type}
            onChange={(e) => setF({ ...f, entity_type: e.target.value })}
            placeholder="Entity Type"
            className={filterInput}
          />
          <input
            value={f.entity_id}
            onChange={(e) => setF({ ...f, entity_id: e.target.value })}
            placeholder="Entity ID"
            className={filterInput}
          />
          <input
            value={f.actor}
            onChange={(e) => setF({ ...f, actor: e.target.value })}
            placeholder="Actor Email"
            className={filterInput}
          />
          <input
            value={f.action}
            onChange={(e) => setF({ ...f, action: e.target.value })}
            placeholder="Action"
            className={filterInput}
          />
          <button onClick={refresh} className="btn-aurora text-xs py-1 px-3">
            Apply Filters
          </button>
        </div>
      )}

      <div className="max-h-96 overflow-auto rounded-xl border border-slate-200 bg-white">
        {tab === 'events' && (
          <table className="table text-[11px] font-mono">
            <thead>
              <tr>
                <th>TIMESTAMP</th>
                <th>ACTOR</th>
                <th>ACTION</th>
                <th>ENTITY</th>
                <th>STATE TRANSITION / REASON</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td className="text-slate-500 font-mono whitespace-nowrap">
                    {(r.created_at ?? '').slice(0, 19).replace('T', ' ')}
                  </td>
                  <td className="text-sky-700 font-mono font-bold">{r.actor_email ?? 'system'}</td>
                  <td>
                    <span className="rounded bg-sky-100 px-1.5 py-0.5 text-[10px] text-sky-800 border border-sky-200 font-bold">
                      {r.action}
                    </span>
                  </td>
                  <td className="text-slate-800">
                    {r.entity_type}:<span className="text-slate-500">{r.entity_id.slice(0, 18)}</span>
                  </td>
                  <td className="text-slate-600 max-w-xs truncate">
                    {[r.old_value, r.new_value].filter(Boolean).join(' → ') || r.reason || '—'}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={5} className="text-center py-6 text-slate-500 font-sans">
                    No matching audit trail records found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
        {tab !== 'events' && (
          <pre className="max-h-96 overflow-auto p-4 text-[11px] font-mono text-emerald-700 bg-slate-900 text-emerald-400">
            {JSON.stringify(other.slice(0, 50), null, 2)}
          </pre>
        )}
      </div>
    </div>
  )
}
