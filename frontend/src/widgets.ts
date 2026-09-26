import type { ViewKind, WidgetPos } from './api'

/** Widget della dashboard: dimensioni in celle di una griglia a 12 colonne (riga = 40 px). */
export interface WidgetDef {
  id: string; title: string; views: ViewKind[]
  w: number; h: number; minW?: number; minH?: number
}

export const COLS = 12

export const WIDGETS: WidgetDef[] = [
  { id: 'kpis', title: 'Indicatori', views: ['overview', 'ap'], w: 12, h: 2, minW: 3, minH: 2 },
  { id: 'aps', title: 'Access point', views: ['overview'], w: 12, h: 5, minW: 3, minH: 3 },
  { id: 'internet', title: 'Internet', views: ['overview'], w: 12, h: 9, minW: 4, minH: 5 },
  { id: 'sites', title: 'Siti più visitati', views: ['overview', 'ap'], w: 3, h: 8 },
  { id: 'types', title: 'Dispositivi per tipologia', views: ['overview', 'ap'], w: 3, h: 5 },
  { id: 'traffic_ap', title: 'Traffico per access point', views: ['overview'], w: 3, h: 5 },
  { id: 'blocked', title: 'Pubblicità e tracker bloccati', views: ['overview'], w: 3, h: 8 },
  { id: 'clients_ap', title: 'Client per access point', views: ['overview'], w: 3, h: 5 },
  { id: 'band', title: 'Client per banda', views: ['overview', 'ap'], w: 3, h: 3, minH: 2 },
  { id: 'topology', title: 'Mappa della rete', views: ['overview'], w: 6, h: 7, minW: 4, minH: 5 },
  { id: 'channels', title: 'Piano dei canali', views: ['overview'], w: 6, h: 7, minW: 4, minH: 4 },
  { id: 'firmware', title: 'Firmware', views: ['overview'], w: 4, h: 6, minW: 3, minH: 4 },
  { id: 'new_devices', title: 'Dispositivi nuovi', views: ['overview'], w: 4, h: 6 },
  { id: 'signal', title: 'Qualità del segnale', views: ['overview', 'ap'], w: 4, h: 6 },
  { id: 'roaming', title: 'Roaming', views: ['overview', 'ap'], w: 4, h: 6 },
  { id: 'usage_devices', title: 'Consumo per dispositivo', views: ['overview'], w: 6, h: 7 },
  { id: 'trend', title: 'Andamento', views: ['overview', 'ap'], w: 12, h: 7, minW: 4, minH: 4 },
  { id: 'clients', title: 'Client connessi', views: ['overview', 'ap'], w: 12, h: 10, minW: 4, minH: 4 },
  { id: 'ap_events', title: 'Storico collegamenti', views: ['ap'], w: 12, h: 7, minW: 4, minH: 3 },
]

export const widgetsFor = (view: ViewKind) => WIDGETS.filter(w => w.views.includes(view))
export const defOf = (id: string) => WIDGETS.find(w => w.id === id)

/** disposizione iniziale: i widget in fila, a capo quando la riga è piena */
export function defaultLayout(view: ViewKind): WidgetPos[] {
  const out: WidgetPos[] = []
  let x = 0, y = 0, rowH = 0
  for (const d of widgetsFor(view)) {
    if (x + d.w > COLS) { x = 0; y += rowH; rowH = 0 }
    out.push({ i: d.id, x, y, w: d.w, h: d.h })
    x += d.w
    rowH = Math.max(rowH, d.h)
  }
  return out
}

/** ripulisce una disposizione salvata: via i widget che non esistono più, misure dentro la griglia */
export function normalize(view: ViewKind, saved: WidgetPos[] | undefined): WidgetPos[] {
  if (!saved?.length) return defaultLayout(view)
  const allowed = new Set(widgetsFor(view).map(w => w.id))
  const seen = new Set<string>()
  return saved.filter(p => allowed.has(p.i) && !seen.has(p.i) && seen.add(p.i)).map(p => {
    const w = Math.min(COLS, Math.max(1, p.w))
    return { i: p.i, w, h: Math.max(1, p.h), x: Math.min(Math.max(0, p.x), COLS - w), y: Math.max(0, p.y) }
  })
}

/** posizione per un widget aggiunto: in fondo, a tutta larghezza disponibile */
export function appendWidget(layout: WidgetPos[], id: string): WidgetPos {
  const d = defOf(id)!
  const bottom = layout.reduce((m, p) => Math.max(m, p.y + p.h), 0)
  return { i: id, x: 0, y: bottom, w: d.w, h: d.h }
}
