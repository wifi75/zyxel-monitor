export function bps(v: number | null | undefined): string {
  if (v == null) return '—'
  const units = ['bit/s', 'kbit/s', 'Mbit/s', 'Gbit/s']
  let i = 0
  while (v >= 1000 && i < units.length - 1) { v /= 1000; i++ }
  return `${v.toFixed(v < 10 && i > 0 ? 1 : 0)} ${units[i]}`
}

export function bytes(v: number | null | undefined): string {
  if (v == null) return '—'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++ }
  return `${v.toFixed(i >= 3 ? 2 : 0)} ${units[i]}`
}

export function duration(s: number | null | undefined): string {
  if (s == null || s < 0) return '—'
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60)
  if (d) return `${d}g ${h}h`
  if (h) return `${h}h ${m}m`
  return `${m}m`
}

export function since(ts: number | null | undefined): string {
  return ts ? duration(Date.now() / 1000 - ts) : '—'
}

export function time(ts: number): string {
  return new Date(ts * 1000).toLocaleString('it-IT', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

/** Qualità del segnale: soglie usuali per il Wi-Fi. */
export function signal(dbm: number | null): { label: string; level: 'good' | 'ok' | 'weak' | 'bad' } {
  if (dbm == null) return { label: '—', level: 'bad' }
  if (dbm >= -60) return { label: 'Ottimo', level: 'good' }
  if (dbm >= -67) return { label: 'Buono', level: 'ok' }
  if (dbm >= -75) return { label: 'Debole', level: 'weak' }
  return { label: 'Scarso', level: 'bad' }
}

export function isPrivateMac(mac: string): boolean {
  return (parseInt(mac.slice(0, 2), 16) & 0x02) === 0x02
}
