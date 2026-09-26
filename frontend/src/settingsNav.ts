import { ref, watch } from 'vue'

/** Sezione aperta nella pagina Impostazioni: condivisa, così il menu principale può aprirne una (es. l'account). */
export type Section = 'account' | 'opnsense' | 'alerts' | 'users' | 'backup' | 'nebula'
const KEY = 'zm-settings-section'
const ALL: Section[] = ['account', 'opnsense', 'alerts', 'users', 'backup', 'nebula']

function initial(): Section {
  try {
    const v = localStorage.getItem(KEY) as Section | null
    if (v && ALL.includes(v)) return v
  } catch { /* storage non disponibile */ }
  return 'opnsense'
}

export const settingsSection = ref<Section>(initial())
watch(settingsSection, v => { try { localStorage.setItem(KEY, v) } catch { /* ignora */ } })
