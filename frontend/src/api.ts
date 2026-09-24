export interface Radio {
  band: string; channel: number | null; clients: number
  tx_power?: number | null; utilization?: number | null
}
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
  id: number; ts: number
  kind: 'connect' | 'disconnect' | 'roam' | 'ap_down' | 'ap_up' | 'new_device' | 'wan_down' | 'wan_up'
  mac: string | null; name: string | null; ap: string | null; info: string | null
}
export interface TrafficPoint { ts: number; down_bps: number | null; up_bps: number | null; clients: number | null }
export interface Traffic { step: number; series: Record<string, TrafficPoint[]> }
export interface Usage { hours: number; per_ap: Record<string, { down: number; up: number }> }
export interface Sites { available: boolean; items: { site: string; queries: number }[] }
export interface Gateway { name: string; online: boolean; status: string; delay: string; loss: string; monitor: string }
export interface LinePoint { ts: number; delay_ms: number | null; loss_pct: number | null }
export interface Outage { gateway: string; start: number; end: number | null; duration: number }
export interface Internet {
  available: boolean; gateways: Gateway[]; period: { down: number; up: number }; series: TrafficPoint[]
  quality: LinePoint[]; availability: number | null; outages: Outage[]
  dns: null | { total: number; blocked: number; blocked_pct: number; since: number;
    top_blocked: { domain: string; queries: number; list: string }[] }
}
export interface Health { version: string; author: string; name: string; build?: string }

/** campi segreti: l'API dice solo se sono impostati (has_*), vuoti nel modulo = invariati */
export type Secret = 'snmp_community' | 'snmp_auth_pass' | 'snmp_priv_pass' | 'ssh_password'
export interface ApConfig {
  id: number; name: string; host: string; method: 'snmp' | 'ssh'; enabled: boolean
  snmp_version: '1' | '2c' | '3'; snmp_user: string; snmp_auth_proto: string; snmp_priv_proto: string
  ssh_port: number; ssh_user: string
  has_snmp_community: boolean; has_snmp_auth_pass: boolean; has_snmp_priv_pass: boolean; has_ssh_password: boolean
}
export interface ApForm extends Omit<ApConfig, 'id' | `has_${Secret}`>, Record<Secret, string> {
  id: number | null; copy_from: number | null; apply_to_all: boolean
}
export function apForm(a: ApConfig | null): ApForm {
  return {
    id: a?.id ?? null, name: a?.name ?? '', host: a?.host ?? '', method: a?.method ?? 'snmp', enabled: a?.enabled ?? true,
    snmp_version: a?.snmp_version ?? '2c', snmp_user: a?.snmp_user ?? '', snmp_auth_proto: a?.snmp_auth_proto ?? 'SHA',
    snmp_priv_proto: a?.snmp_priv_proto ?? 'AES', ssh_port: a?.ssh_port ?? 22, ssh_user: a?.ssh_user ?? 'admin',
    snmp_community: '', snmp_auth_pass: '', snmp_priv_pass: '', ssh_password: '', copy_from: null, apply_to_all: false,
  }
}
export interface ApTest {
  online: boolean; model: string | null; firmware: string | null; uptime_s: number | null
  clients: number; traffic: boolean; error: string | null; hint: string | null; ms: number
}
export interface Detect {
  suggested: 'snmp' | 'ssh' | null; snmp_ok: boolean; ssh_open: boolean; model: string | null
  used_default_community: boolean; message: string
}
export interface GeneralSettings {
  opnsense_url: string; opnsense_key: string; has_opnsense_secret: boolean; opnsense_verify_tls: boolean
  opnsense_wan_if: string; local_domain: string; poll_interval: number; retention_days: number
}
export interface GeneralForm extends GeneralSettings { opnsense_secret: string }

export interface Device {
  mac: string; first_seen: number; last_seen: number; last_ap: string | null; last_ip: string | null
  hostname: string | null; alias: string | null; known: boolean; online: boolean; rssi_dbm: number | null
  device_type: string
}
export interface SignalHistory { step: number; points: { ts: number; avg: number | null; min: number | null; ap: string | null }[] }
export interface SignalByAp {
  weak_dbm: number
  aps: { ap: string; avg: number; weak_pct: number; devices: number }[]
  worst: { mac: string; name: string; ap: string | null; avg: number; min: number }[]
}
export interface Roaming {
  threshold: number
  pairs: { from: string; to: string; count: number }[]
  devices: { mac: string; name: string; count: number; aps: string[]; bouncing: boolean }[]
}
export interface DeviceUsage {
  available: boolean; reason?: 'opnsense' | 'netflow' | 'error'; message?: string
  items?: { mac: string | null; ip: string; name: string; device_type: string; bytes: number }[]
  by_type?: { type: string; bytes: number }[]
  debug?: { path: string; rows: number; addresses: number; sample_addresses: string[]; sample: string } | null
}
export interface NebulaStatus { configured: boolean; has_key: boolean; org_id: string; site_id: string }
export interface NebulaDiscover {
  ok: boolean; pro?: boolean; message: string | null
  organizations?: { orgId: string; name: string; mode: string; error: string | null;
    sites: { siteId: string; name: string; deviceCount: number }[] }[]
}
export interface NebulaDevice {
  devId: string; name: string | null; model: string | null; mac: string; type: string | null; online: boolean
  currentVersion: string | null; latestVersion: string | null; firmwareStatus: string | null; lastUpgradeTime: string | null
}
export interface NebulaSsid {
  id: number; name: string; enabled: boolean; security: string; band: string[]; visibility: boolean; vlan: number
  guestNetwork: boolean; enabledBands: string[]; has_wpa_key: boolean
}

export interface WidgetPos { i: string; x: number; y: number; w: number; h: number }
export type ViewKind = 'overview' | 'ap'
export type SavedLayout = Partial<Record<ViewKind, WidgetPos[]>>

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

  // analisi
  devices: () => req<Device[]>('/devices'),
  setKnown: (mac: string, known: boolean) =>
    req(`/devices/${encodeURIComponent(mac)}/known`, { method: 'PUT', body: JSON.stringify({ known }) }),
  setAllKnown: () => req('/devices/known-all', { method: 'POST' }),
  forgetDevice: (mac: string) => req(`/devices/${encodeURIComponent(mac)}`, { method: 'DELETE' }),
  signal: (mac: string, hours: number) => req<SignalHistory>(`/signal?mac=${encodeURIComponent(mac)}&hours=${hours}`),
  signalByAp: (hours: number, ap?: string) =>
    req<SignalByAp>(`/signal/aps?hours=${hours}${ap ? `&ap=${encodeURIComponent(ap)}` : ''}`),
  roaming: (hours: number, ap?: string) =>
    req<Roaming>(`/roaming?hours=${hours}${ap ? `&ap=${encodeURIComponent(ap)}` : ''}`),
  usageDevices: (hours: number) => req<DeviceUsage>(`/usage/devices?hours=${hours}`),
  layout: () => req<SavedLayout>('/layout'),
  saveLayout: (l: SavedLayout) => req('/layout', { method: 'PUT', body: JSON.stringify(l) }),
  resetLayout: () => req('/layout', { method: 'DELETE' }),
  rebootAp: (id: number) => req(`/settings/aps/${id}/reboot`, { method: 'POST' }),
  rawOutput: (id: number) => req<{ ts: number | null; text: string }>(`/settings/aps/${id}/raw`),

  // Nebula (licenza Pro)
  nebulaStatus: () => req<NebulaStatus>('/nebula/status'),
  nebulaDiscover: (api_key: string) =>
    req<NebulaDiscover>('/nebula/discover', { method: 'POST', body: JSON.stringify({ api_key }) }),
  nebulaConnect: (api_key: string, org_id: string, site_id: string) =>
    req<NebulaStatus>('/nebula/connect', { method: 'PUT', body: JSON.stringify({ api_key, org_id, site_id }) }),
  nebulaDisconnect: () => req<NebulaStatus>('/nebula/connect', { method: 'DELETE' }),
  nebulaDevices: () => req<{ devices: NebulaDevice[]; updates: number }>('/nebula/devices'),
  nebulaReboot: (devId: string) => req(`/nebula/devices/${encodeURIComponent(devId)}/reboot`, { method: 'POST' }),
  nebulaSsids: () => req<NebulaSsid[]>('/nebula/ssids'),
  nebulaUpdateSsid: (id: number, patch: { name?: string; enabled?: boolean; bands?: string[] }) =>
    req(`/nebula/ssids/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),

  // pannello impostazioni
  apConfigs: () => req<ApConfig[]>('/settings/aps'),
  createAp: (f: ApForm) => req<ApConfig & { copied: number }>('/settings/aps', { method: 'POST', body: JSON.stringify(f) }),
  updateAp: (id: number, f: ApForm) =>
    req<ApConfig & { copied: number }>(`/settings/aps/${id}`, { method: 'PUT', body: JSON.stringify(f) }),
  deleteAp: (id: number) => req(`/settings/aps/${id}`, { method: 'DELETE' }),
  testAp: (f: ApForm) => req<ApTest>('/settings/aps/test', { method: 'POST', body: JSON.stringify(f) }),
  detectAp: (f: ApForm) => req<Detect>('/settings/aps/detect', { method: 'POST', body: JSON.stringify(f) }),
  general: () => req<GeneralSettings>('/settings/general'),
  saveGeneral: (f: GeneralForm) => req<GeneralSettings>('/settings/general', { method: 'PUT', body: JSON.stringify(f) }),
  testOpnsense: (f: GeneralForm) =>
    req<{ ok: boolean; message: string }>('/settings/opnsense/test', { method: 'POST', body: JSON.stringify(f) }),
}
