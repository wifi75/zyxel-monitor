export interface Radio { band: string; channel: number | null; clients: number }
export interface Ap {
  ap: string; host: string; method: 'snmp' | 'ssh'; online: boolean
  model: string | null; firmware: string | null; uptime_s: number | null
  clients: number | null; radios: Radio[]; error: string | null
  last_seen: number | null; updated: number
}
export interface Client {
  mac: string; ap: string; ip: string | null; hostname: string | null; alias: string | null
  ssid: string | null; band: string | null; rssi_dbm: number | null
  tx_rate: number | null; rx_rate: number | null; capability: string | null
  connected_at: number | null; device_type: string
}
export interface Event {
  id: number; ts: number; kind: 'connect' | 'disconnect' | 'roam' | 'ap_down' | 'ap_up'
  mac: string | null; name: string | null; ap: string | null; info: string | null
}
export interface TrafficPoint { ts: number; down_bps: number | null; up_bps: number | null; clients: number | null }
export interface Traffic { step: number; series: Record<string, TrafficPoint[]> }
export interface Usage { hours: number; per_ap: Record<string, { down: number; up: number }> }
export interface Sites { available: boolean; items: { site: string; queries: number }[] }
export interface Gateway { name: string; online: boolean; status: string; delay: string; loss: string; monitor: string }
export interface Internet {
  available: boolean; gateways: Gateway[]; period: { down: number; up: number }; series: TrafficPoint[]
  dns: null | { total: number; blocked: number; blocked_pct: number; since: number;
    top_blocked: { domain: string; queries: number; list: string }[] }
}
export interface Health { version: string; author: string; name: string }

const TOKEN_KEY = 'zm_token'
export const auth = {
  get token() { return localStorage.getItem(TOKEN_KEY) },
  set(t: string) { localStorage.setItem(TOKEN_KEY, t) },
  clear() { localStorage.removeItem(TOKEN_KEY) },
}

export class Unauthorized extends Error {}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (auth.token) headers.Authorization = `Bearer ${auth.token}`
  const res = await fetch(`/api${path}`, { ...init, headers })
  if (res.status === 401) { auth.clear(); throw new Unauthorized() }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const detail = Array.isArray(body.detail) ? body.detail[0]?.msg : body.detail
    throw new Error(detail || `Errore ${res.status}`)
  }
  return res.json()
}

export const api = {
  health: () => req<Health>('/health'),
  login: (username: string, password: string) =>
    req<{ token: string; default_password: boolean }>('/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  me: () => req<{ username: string; default_password: boolean }>('/me'),
  changePassword: (old_password: string, new_password: string) =>
    req('/password', { method: 'POST', body: JSON.stringify({ old_password, new_password }) }),
  aps: () => req<Ap[]>('/aps'),
  clients: () => req<Client[]>('/clients'),
  events: (limit = 200, ap?: string) =>
    req<Event[]>(`/events?limit=${limit}${ap ? `&ap=${encodeURIComponent(ap)}` : ''}`),
  sites: (hours: number, ap?: string, ip?: string) =>
    req<Sites>(`/sites?hours=${hours}&limit=10${ap ? `&ap=${encodeURIComponent(ap)}` : ''}${ip ? `&ip=${encodeURIComponent(ip)}` : ''}`),
  internet: (hours: number) => req<Internet>(`/internet?hours=${hours}`),
  usage: (hours: number) => req<Usage>(`/usage?hours=${hours}`),
  traffic: (hours: number) => req<Traffic>(`/traffic?hours=${hours}`),
  setAlias: (mac: string, name: string) =>
    req(`/clients/${encodeURIComponent(mac)}/alias`, { method: 'PUT', body: JSON.stringify({ name }) }),
}
