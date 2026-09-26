import { ref } from 'vue'
import { seriesColor, themeKey } from './chartColors'

/**
 * Un colore fisso per ogni AP, uguale in tutti i grafici e le etichette: la posizione in ordine alfabetico
 * sceglie la serie del tema. App aggiorna l'elenco dei nomi a ogni lettura.
 */
export const apNames = ref<string[]>([])

export function setApNames(names: string[]) {
  const sorted = [...names].sort((a, b) => a.localeCompare(b))
  if (sorted.join('|') !== apNames.value.join('|')) apNames.value = sorted
}

export function apColor(name: string): string {
  themeKey()                    // ricalcolato al cambio di tema
  const i = apNames.value.indexOf(name)
  return seriesColor(i >= 0 ? i : apNames.value.length)
}
