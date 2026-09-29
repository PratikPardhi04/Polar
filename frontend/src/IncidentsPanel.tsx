import { useEffect, useState } from 'react'
import { API } from './lib/auth'

type Incident = {
  id: string
  incident_type: string
  mission_id: string | null
  last_location: string
  detail: string
  status: string
  sos_flag: boolean
}

type Detail = {
  incident: Incident
  person: { full_name: string; readiness: string } | null
  mission: { id: string; objective: string; status: string } | null
  team: { full_name: string }[]
  vehicle: { registration_number: string; asset_status: string } | null
  weather: { station: string; condition: string; temp_c: number; wind_kph: number } | null
  last_comms_at: string | null
  comms_count: number
}

/** Mission Control active-incident panel: open incidents with rich context & live WebSocket status. */
export default function IncidentsPanel({ token }: { token: string }) {
  const [list, setList] = useState<Incident[]>([])
  const [openId, setOpenId] = useState<string | null>(null)
  const [detail, setDetail] = useState<Detail | null>(null)
  const [live, setLive] = useState(false)

  function refresh() {
    fetch(`${API}/api/v1/incidents?status=OPEN`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : []))
      .then(setList)
      .catch(() => setList([]))
  }

  useEffect(() => {
    refresh()
    let ws: WebSocket | null = null
    try {
      ws = new WebSocket(`${API.replace(/^http/, 'ws')}/api/v1/ws/alerts?token=${token}`)
      ws.onopen = () => setLive(true)
      ws.onmessage = () => refresh()
      ws.onclose = () => setLive(false)
    } catch {
      ws = null
    }
    return () => ws?.close()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  async function expand(id: string) {
    if (openId === id) {
      setOpenId(null)
      return
    }
    setOpenId(id)
    const r = await fetch(`${API}/api/v1/incidents/${id}`, { headers: { Authorization: `Bearer ${token}` } })
    if (r.ok) setDetail(await r.json())
  }

  async function advance(id: string, to: string) {
    const r = await fetch(`${API}/api/v1/incidents/${id}/status`, {
      method: 'PATCH',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ to_status: to }),
    })
    if (r.ok) {
      refresh()
      expand(id)
    }
  }

  if (list.length === 0) {
    return (
      <div className="card text-center py-6 border-slate-200">
        <div className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-emerald-100 border border-emerald-200 text-emerald-700 font-bold mb-2">
          ✓
        </div>
        <p className="text-xs font-mono text-slate-700 font-bold">All Sectors Clear — No Open Critical Incidents</p>
        <p className="text-[11px] font-mono text-slate-500 mt-1">
          {live ? '● WebSocket Live Push Active' : '○ Standby Polling Mode'}
        </p>
      </div>
    )
  }

  return (
    <div className="card border-rose-200">
      <div className="flex items-center justify-between mb-3 border-b border-slate-200 pb-2">
        <div className="flex items-center gap-2">
          <span className={`w-2.5 h-2.5 rounded-full ${live ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`}></span>
          <h3 className="text-sm font-bold text-slate-800">Active Operational Incidents ({list.length})</h3>
        </div>
        <span className="text-[10px] font-mono text-slate-500 font-bold">
          {live ? 'WEBSOCKET PUSH ONLINE' : 'POLLING'}
        </span>
      </div>

      <ul className="space-y-3">
        {list.map((i) => (
          <li
            key={i.id}
            className={`rounded-xl border p-3.5 transition-all ${
              i.sos_flag
                ? 'border-rose-300 bg-rose-50/80 shadow-xs'
                : 'border-slate-200 bg-white hover:border-slate-300'
            }`}
          >
            <button onClick={() => expand(i.id)} className="flex w-full items-center justify-between text-left">
              <div>
                <span className="font-mono text-xs font-bold text-slate-900 uppercase">{i.incident_type}</span>
                <span className="ml-2 text-xs font-mono text-sky-700 font-bold">Mission: {i.mission_id ?? 'UNASSIGNED'}</span>
                <span className="ml-2 text-xs text-slate-500">📍 {i.last_location || 'Unknown Coordinates'}</span>
              </div>
              {i.sos_flag && (
                <span className="rounded px-2 py-0.5 text-[10px] font-mono font-bold bg-rose-600 text-white shadow-xs animate-pulse">
                  SOS EMERGENCY
                </span>
              )}
            </button>

            {openId === i.id && detail && detail.incident.id === i.id && (
              <div className="mt-3 border-t border-slate-200 pt-3 text-xs space-y-2">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px] font-mono bg-slate-50 p-3 rounded-lg border border-slate-200">
                  <div>
                    <span className="text-slate-500">Personnel:</span>{' '}
                    <span className="text-slate-900 font-bold">{detail.person ? `${detail.person.full_name} [${detail.person.readiness}]` : '—'}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">Mission State:</span>{' '}
                    <span className="text-sky-700 font-bold">{detail.mission ? `${detail.mission.id} [${detail.mission.status}]` : '—'}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">Assigned Team:</span>{' '}
                    <span className="text-slate-800">{detail.team.map((t) => t.full_name).join(', ') || '—'}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">Vehicle Unit:</span>{' '}
                    <span className="text-emerald-700 font-bold">{detail.vehicle ? `${detail.vehicle.registration_number} (${detail.vehicle.asset_status})` : '—'}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">Weather Context:</span>{' '}
                    <span className="text-amber-800 font-bold">
                      {detail.weather ? `${detail.weather.station} · ${detail.weather.condition} · ${detail.weather.temp_c}°C · wind ${detail.weather.wind_kph} km/h` : 'No snapshot'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500">Comms Log:</span>{' '}
                    <span className="text-slate-800">{detail.comms_count} ping(s){detail.last_comms_at ? `, last at ${detail.last_comms_at}` : ''}</span>
                  </div>
                </div>

                <p className="text-xs text-slate-700 italic bg-slate-100/70 p-2.5 rounded border border-slate-200">
                  "{detail.incident.detail}"
                </p>

                <div className="mt-2 flex flex-wrap items-center gap-1.5 pt-1">
                  <span className="text-[10px] font-mono text-slate-500 font-bold mr-1">Advance Lifecycle:</span>
                  {['ASSESSING', 'RESPONDING', 'RESOLVED', 'CLOSED'].map((s) => (
                    <button
                      key={s}
                      onClick={() => advance(i.id, s)}
                      className="rounded bg-white border border-slate-300 px-2 py-1 text-[10px] font-mono text-sky-700 hover:bg-sky-50 font-bold transition-all shadow-xs"
                    >
                      → {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
