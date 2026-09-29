export function normalizeBase(raw: string): string {
  let v = (raw || '').trim().replace(/\/+$/, '')
  if (v && !/^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//.test(v)) v = `https://${v}`
  return v
}

export const API = normalizeBase((import.meta.env.VITE_API_URL as string) || 'http://localhost:8000')
export const AI_URL = normalizeBase((import.meta.env.VITE_AI_URL as string) || 'http://localhost:8001')

export function getToken(): string | null {
  return localStorage.getItem('polaris_token')
}

export function setToken(t: string) {
  localStorage.setItem('polaris_token', t)
}

export function clearToken() {
  localStorage.removeItem('polaris_token')
}

export function getRole(token: string | null): string {
  try {
    return (JSON.parse(atob((token ?? '').split('.')[1])) as { role?: string }).role ?? ''
  } catch {
    return ''
  }
}

export async function login(email: string, password: string): Promise<string> {
  // Canonical login path (backend serves POST /auth/login only).
  const r = await fetch(`${API}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!r.ok) {
    const data = await r.json().catch(() => ({}))
    throw new Error((data as { detail?: string }).detail || `Server error (${r.status})`)
  }
  const data = await r.json()
  if (!data.access_token) throw new Error('Login failed: no token returned')
  return data.access_token as string
}

export async function api<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!r.ok) throw new Error(`API ${r.status} on ${path}`)
  return (await r.json()) as T
}
