import { ref, watch } from 'vue'
import { theme } from './theme'

/** Colori delle sfumature dei riquadri (KPI, card degli AP, sezioni): tavolozze pronte, scelta salvata nel browser.
 *  I colori sono quelli del tema chiaro; nel tema scuro si schiariscono da soli per restare leggibili. */
export interface Palette {
  id: string; name: string
  /** blu, verde acqua, verde, viola, rosa, ambra, arancio */
  tones?: [string, string, string, string, string, string, string]
}
const VARS = ['--blue', '--teal', '--green', '--violet', '--pink', '--amber', '--orange']

export const PALETTES: Palette[] = [
  { id: 'default', name: 'Predefinita' },
  { id: 'vivid', name: 'Vivace', tones: ['#3b82f6', '#14b8a6', '#10b981', '#8b5cf6', '#ec4899', '#f59e0b', '#f97316'] },
  { id: 'ocean', name: 'Oceano', tones: ['#1d4ed8', '#0891b2', '#0d9488', '#4f46e5', '#0284c7', '#0e7490', '#2563eb'] },
  { id: 'sunset', name: 'Tramonto', tones: ['#c2410c', '#d97706', '#b45309', '#be185d', '#e11d48', '#ea580c', '#dc2626'] },
  { id: 'forest', name: 'Foresta', tones: ['#15803d', '#0f766e', '#4d7c0f', '#166534', '#65a30d', '#a16207', '#047857'] },
  { id: 'lavender', name: 'Lavanda', tones: ['#7c3aed', '#9333ea', '#6d28d9', '#a855f7', '#db2777', '#c026d3', '#8b5cf6'] },
  { id: 'pastel', name: 'Pastello', tones: ['#60a5fa', '#5eead4', '#86efac', '#c4b5fd', '#f9a8d4', '#fcd34d', '#fdba74'] },
  { id: 'graphite', name: 'Grafite', tones: ['#475569', '#52525b', '#57534e', '#4b5563', '#64748b', '#71717a', '#6b7280'] },
  ...generated(),
]

type Tones = NonNullable<Palette['tones']>
/** tavolozze ricavate da una tinta: "tinta unita" (sfumature dello stesso colore) e "armonia" (colori vicini) */
function generated(): Palette[] {
  const HUES: [number, string][] = [
    [0, 'Rosso'], [20, 'Corallo'], [35, 'Arancio'], [48, 'Oro'], [80, 'Lime'], [140, 'Smeraldo'],
    [175, 'Acqua'], [195, 'Cielo'], [215, 'Cobalto'], [245, 'Indaco'], [280, 'Ametista'], [320, 'Magenta'],
  ]
  const hsl = (h: number, s: number, l: number) => `hsl(${((h % 360) + 360) % 360} ${s}% ${l}%)`
  const mono = (h: number) => [0, 1, 2, 3, 4, 5, 6].map(i => hsl(h, 70 - i * 4, 32 + i * 5)) as Tones
  const harmony = (h: number) => [0, 25, 50, -25, -50, 75, -75].map(d => hsl(h + d, 65, 44)) as Tones
  return HUES.flatMap(([h, name]) => [
    { id: `mono-${h}`, name, tones: mono(h) },
    { id: `harm-${h}`, name: `${name} armonia`, tones: harmony(h) },
  ])
}

/** colore della sfumatura delle card degli AP online */
export const CARD_TONES = ['good', 'blue', 'teal', 'violet', 'pink', 'amber', 'orange'] as const
export type CardTone = typeof CARD_TONES[number] | 'custom'

export interface Look { palette: string; card: CardTone; shade: number; custom: string }
const KEY = 'zm-palette'
const DEFAULT: Look = { palette: 'default', card: 'good', shade: 1, custom: '#0f9d58' }

function initial(): Look {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || 'null')
    if (saved && typeof saved === 'object') return { ...DEFAULT, ...saved }
  } catch { /* storage non disponibile */ }
  return { ...DEFAULT }
}

export const look = ref<Look>(initial())

function apply() {
  const root = document.documentElement.style
  const p = PALETTES.find(x => x.id === look.value.palette)
  VARS.forEach((v, i) => {
    const c = p?.tones?.[i]
    if (!c) root.removeProperty(v)
    else root.setProperty(v, theme.value === 'dark' ? `color-mix(in srgb, ${c} 65%, #fff)` : c)
  })
  root.setProperty('--card-tone', look.value.card === 'custom' ? look.value.custom : `var(--${look.value.card})`)
  root.setProperty('--shade', String(look.value.shade))
}

watch([look, theme], () => {
  apply()
  try { localStorage.setItem(KEY, JSON.stringify(look.value)) } catch { /* ignora */ }
}, { deep: true, immediate: true })

export function resetLook() { look.value = { ...DEFAULT } }
