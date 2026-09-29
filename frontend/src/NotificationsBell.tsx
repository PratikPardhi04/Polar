import { useEffect, useState } from 'react'
import { API } from './lib/auth'

const API_BASE = API

type Notification = {
  id: string
  notif_type: string
  severity: string
  target_role: string
  entity_type: string
  entity_id: string
  message: string
  status: string
}

const SEV_COLOR: Record<string, string> = {
  CRITICAL: 'bg-rose-100 text-rose-800 border-rose-300',
  WARNING: 'bg-amber-100 text-amber-800 border-amber-300',
  INFO: 'bg-sky-100 text-sky-800 border-sky-300',
}

/** Notification Center: bell with unread count badge, light dropdown list, mark-as-read/acknowledge. */
export default function NotificationsBell({ token }: { token: string }) {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<Notification[]>([])

  function refresh() {
    fetch(`${API_BASE}/api/v1/notifications`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : []))
      .then(setItems)
      .catch(() => setItems([]))
  }

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 30000)
    return () => clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  async function act(id: string, verb: 'read' | 'acknowledge') {
    await fetch(`${API_BASE}/api/v1/notifications/${id}/${verb}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    })
    refresh()
  }

  const unread = items.filter((i) => i.status === 'UNREAD').length

  return (
    <div className="relative">
      <button
        onClick={() => {
          setOpen(!open)
          refresh()
        }}
        className="relative rounded-xl border border-slate-200 bg-white p-2 text-slate-600 shadow-xs transition-all hover:bg-slate-50 hover:text-sky-600 focus:outline-none"
        title="Notification Center"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>

        {unread > 0 && (
          <span className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-rose-600 text-[10px] font-bold text-white shadow-xs animate-pulse">
            {unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-2 max-h-[460px] w-80 sm:w-96 overflow-y-auto rounded-2xl border border-slate-200 bg-white p-4 shadow-xl backdrop-blur-md animate-scale-in">
          <div className="mb-3 flex items-center justify-between border-b border-slate-100 pb-2">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-slate-800">Command Alerts</span>
              {unread > 0 && (
                <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-semibold text-rose-800 border border-rose-200">
                  {unread} unread
                </span>
              )}
            </div>
            <button
              onClick={refresh}
              className="text-xs font-mono text-sky-700 hover:text-sky-800 font-semibold"
            >
              🔄 Refresh
            </button>
          </div>

          {items.length === 0 && (
            <div className="py-8 text-center text-xs text-slate-500 font-mono">
              ✓ All operational logs clear. No active alerts.
            </div>
          )}

          <ul className="space-y-2.5">
            {items.slice(0, 30).map((n) => (
              <li
                key={n.id}
                className="rounded-xl border border-slate-100 bg-slate-50/80 p-3 transition-all hover:bg-slate-100/80"
              >
                <div className="flex items-center justify-between gap-2">
                  <span
                    className={`rounded px-1.5 py-0.5 text-[9px] font-mono font-bold uppercase border ${
                      SEV_COLOR[n.severity] ?? 'bg-slate-200 text-slate-700 border-slate-300'
                    }`}
                  >
                    {n.severity}
                  </span>
                  <span className="text-xs font-semibold text-slate-800">{n.notif_type}</span>
                  <span className="text-[10px] font-mono text-slate-500">{n.target_role}</span>
                </div>

                <p className="mt-1.5 text-xs text-slate-700 leading-relaxed">{n.message}</p>

                {n.status === 'UNREAD' && (
                  <div className="mt-2.5 flex items-center gap-2 pt-2 border-t border-slate-200/60">
                    <button
                      onClick={() => act(n.id, 'read')}
                      className="text-[11px] font-mono text-sky-700 font-bold hover:text-sky-800"
                    >
                      ✓ Mark Read
                    </button>
                    <button
                      onClick={() => act(n.id, 'acknowledge')}
                      className="text-[11px] font-mono text-emerald-700 font-bold hover:text-emerald-800"
                    >
                      ⚡ Acknowledge
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
