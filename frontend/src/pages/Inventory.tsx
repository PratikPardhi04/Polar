import { useEffect, useState } from 'react'
import { api } from '../lib/auth'

type Item = { id: string; name: string; category: string; quantity: number; unit: string; location: string; minimum_stock: number; status: string }
type Txn = { txn_type: string; quantity: number; note: string; created_at?: string }
type Forecast = { item_id: string; name: string; available: number; avg_daily_use: number; days_until_stockout: number | null; reorder_point: number; suggested_reorder_qty: number; at_risk: boolean }

export default function Inventory({ token }: { token: string }) {
  const [items, setItems] = useState<Item[]>([])
  const [lowOnly, setLowOnly] = useState(false)
  const [form, setForm] = useState({ item_id: '', txn_type: 'ISSUE', quantity: '10', note: '' })
  const [hist, setHist] = useState<Txn[]>([])
  const [fc, setFc] = useState<Forecast[]>([])
  const [err, setErr] = useState('')

  async function load() {
    try {
      setItems(await api<Item[]>(`/api/v1/inventory${lowOnly ? '?low_stock=true' : ''}`, token))
      const f = await api<{ items: Forecast[] }>('/api/v1/ai/inventory-forecast', token)
      setFc(f.items || [])
    } catch (e) {
      setErr(String(e))
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, lowOnly])

  async function transact() {
    if (!form.item_id) {
      setErr('Select an item to record transaction.')
      return
    }
    setErr('')
    try {
      await api('/api/v1/inventory/transactions', token, {
        method: 'POST',
        body: JSON.stringify({ item_id: form.item_id, txn_type: form.txn_type, quantity: Number(form.quantity), note: form.note }),
      })
      setForm({ ...form, note: '' })
      load()
    } catch (e) {
      setErr(String(e))
    }
  }

  async function history(id: string) {
    try {
      setHist(await api<Txn[]>(`/api/v1/inventory/${id}/history`, token))
      setForm((prev) => ({ ...prev, item_id: id }))
    } catch {
      setHist([])
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 flex items-center gap-3">
            <span>📊</span> Station Inventory & AI Forecast
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Real-time stock ledger with burn-rate forecasting for Bharati station overwintering supplies.
          </p>
        </div>

        <label className="flex items-center gap-2 cursor-pointer bg-white border border-slate-300 px-3 py-1.5 rounded-xl text-xs font-mono text-slate-700 shadow-xs hover:bg-slate-50 transition-all font-semibold">
          <input
            type="checkbox"
            checked={lowOnly}
            onChange={(e) => setLowOnly(e.target.checked)}
            className="accent-sky-600 rounded"
          />
          Low Stock Alert Only (CRITICAL / WATCH)
        </label>
      </div>

      {err && <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 font-mono">{err}</div>}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left Column: Items Table & History */}
        <div className="card space-y-4">
          <div className="card-title flex items-center justify-between">
            <span>STATION INVENTORY LEDGER ({items.length})</span>
            <span className="text-[10px] font-mono text-slate-500 font-bold">CLICK ROW FOR HISTORY</span>
          </div>

          <div className="max-h-96 overflow-auto rounded-xl border border-slate-200 bg-white">
            <table className="table text-xs font-mono">
              <thead>
                <tr>
                  <th>ITEM NAME</th>
                  <th>QTY ON HAND</th>
                  <th>MIN STOCK</th>
                  <th>STATUS</th>
                </tr>
              </thead>
              <tbody>
                {items.map((i) => (
                  <tr key={i.id} onClick={() => history(i.id)} className="cursor-pointer">
                    <td className="font-sans font-semibold text-slate-800">
                      {i.name} <span className="text-[10px] font-mono text-slate-500 font-normal">({i.category})</span>
                    </td>
                    <td className="font-mono text-sky-700 font-bold">
                      {i.quantity} {i.unit}
                    </td>
                    <td className="font-mono text-slate-600">{i.minimum_stock}</td>
                    <td>
                      <span
                        className={`rounded px-2 py-0.5 text-[10px] font-mono font-bold uppercase border ${
                          i.status === 'CRITICAL'
                            ? 'bg-rose-100 text-rose-800 border-rose-300'
                            : i.status === 'WATCH'
                            ? 'bg-amber-100 text-amber-800 border-amber-300'
                            : 'bg-emerald-100 text-emerald-800 border-emerald-300'
                        }`}
                      >
                        {i.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {hist.length > 0 && (
            <div className="mt-3 border-t border-slate-200 pt-3">
              <div className="text-[11px] font-mono text-sky-800 font-bold mb-2">TRANSACTION HISTORY LOG</div>
              <ul className="max-h-36 space-y-1.5 overflow-auto text-xs font-mono pr-1">
                {hist.map((h, idx) => (
                  <li key={idx} className="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-200">
                    <span className="text-slate-800 font-bold">{h.txn_type} {h.quantity} units</span>
                    <span className="text-slate-500 truncate max-w-xs">{h.note || 'Regular ledger adjustment'}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Right Column: Transaction Form & AI Forecast */}
        <div className="space-y-6">
          <div className="card border-sky-200">
            <div className="card-title mb-3 flex items-center gap-2">
              <span>⚡</span> RECORD INVENTORY TRANSACTION
            </div>
            
            <select
              value={form.item_id}
              onChange={(e) => setForm({ ...form, item_id: e.target.value })}
              className="input text-xs font-mono"
            >
              <option value="">Select Item for Stock Update…</option>
              {items.map((i) => (
                <option key={i.id} value={i.id}>{i.name} (Current: {i.quantity} {i.unit})</option>
              ))}
            </select>

            <div className="mt-3 grid grid-cols-2 gap-3">
              <select
                value={form.txn_type}
                onChange={(e) => setForm({ ...form, txn_type: e.target.value })}
                className="input text-xs font-mono"
              >
                {['RECEIVE', 'ISSUE', 'RETURN', 'CONSUME', 'TRANSFER', 'ADJUST'].map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
              <input
                value={form.quantity}
                onChange={(e) => setForm({ ...form, quantity: e.target.value })}
                type="number"
                placeholder="Quantity"
                className="input text-xs font-mono"
              />
            </div>

            <input
              value={form.note}
              onChange={(e) => setForm({ ...form, note: e.target.value })}
              placeholder="Transaction note / justification"
              className="input mt-3 text-xs"
            />

            <button onClick={transact} className="btn-aurora text-xs py-2 px-5 mt-3 w-full">
              Record Ledger Entry (Audited)
            </button>
          </div>

          <div className="card">
            <div className="card-title mb-3 flex items-center justify-between">
              <span>🤖 AI STOCKOUT FORECAST MODEL</span>
              <span className="text-[10px] font-mono text-sky-700 font-bold">DAILY BURN-RATE ENGINE</span>
            </div>

            <ul className="max-h-72 space-y-2 overflow-auto pr-1 text-xs">
              {fc.filter((f) => f.at_risk).map((f) => (
                <li key={f.item_id} className="p-3 rounded-xl border border-rose-200 bg-rose-50">
                  <div className="flex items-center justify-between font-bold text-rose-800">
                    <span>⚠️ {f.name}</span>
                    <span className="font-mono text-[11px] bg-rose-100 px-2 py-0.5 rounded border border-rose-300 font-bold">
                      {f.days_until_stockout ?? 0} DAYS LEFT
                    </span>
                  </div>
                  <div className="mt-1 text-[11px] text-slate-700 font-mono">
                    Avg daily use: {f.avg_daily_use} units/day · Suggested Reorder Qty: <span className="text-sky-700 font-bold">{f.suggested_reorder_qty}</span>
                  </div>
                </li>
              ))}
              {fc.filter((f) => !f.at_risk).slice(0, 6).map((f) => (
                <li key={f.item_id} className="p-2.5 rounded-lg border border-slate-200 bg-slate-50 flex items-center justify-between text-slate-600 font-mono text-[11px]">
                  <span className="font-semibold text-slate-800">{f.name}</span>
                  <span>Stock OK ({f.avg_daily_use} / day)</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
