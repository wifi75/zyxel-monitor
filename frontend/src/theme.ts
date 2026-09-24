import { ref } from 'vue'

/** tema chiaro (denso operativo) o scuro (console): scelta salvata nel browser, altrimenti quella del sistema */
export type Theme = 'light' | 'dark'
const KEY = 'zm-theme'

function initial(): Theme {
  try {
    const saved = localStorage.getItem(KEY)
    if (saved === 'light' || saved === 'dark') return saved
  } catch { /* storage non disponibile */ }
  return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export const theme = ref<Theme>(initial())
document.documentElement.dataset.theme = theme.value

export function setTheme(v: Theme) {
  theme.value = v
  document.documentElement.dataset.theme = v
  try { localStorage.setItem(KEY, v) } catch { /* ignora */ }
}
