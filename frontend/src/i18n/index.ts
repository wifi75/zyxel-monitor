import { ref } from 'vue'

/**
 * Doppia lingua italiano/inglese. Il testo italiano è la chiave: t('Panoramica') restituisce
 * "Overview" in inglese e il testo stesso in italiano (o se manca la traduzione).
 * Lingua iniziale: quella scelta dall'utente, altrimenti italiano solo se il browser è in italiano.
 */
export type Lang = 'it' | 'en'
const KEY = 'zm_lang'

function detect(): Lang {
  try {
    const saved = localStorage.getItem(KEY)
    if (saved === 'it' || saved === 'en') return saved
  } catch { /* storage non disponibile */ }
  const langs = navigator.languages?.length ? navigator.languages : [navigator.language]
  return (langs[0] || '').toLowerCase().startsWith('it') ? 'it' : 'en'
}

export const lang = ref<Lang>(detect())
document.documentElement.lang = lang.value

const EN: Record<string, string> = {}
export function addEn(dict: Record<string, string>) { Object.assign(EN, dict) }

/** traduce; i segnaposto {nome} vengono sostituiti con params */
export function t(it: string, params?: Record<string, string | number>): string {
  let s = lang.value === 'en' ? (EN[it] ?? it) : it
  if (params) for (const [k, v] of Object.entries(params)) s = s.split(`{${k}}`).join(String(v))
  return s
}

export function setLang(l: Lang) {
  lang.value = l
  document.documentElement.lang = l
  try { localStorage.setItem(KEY, l) } catch { /* ignorato */ }
}

/** locale per date e numeri */
export const locale = () => (lang.value === 'en' ? 'en-GB' : 'it-IT')
