import { theme } from './theme'

/** Colori dei grafici presi dal tema attivo (variabili di tokens.css): i componenti non ne contengono. */
const css = () => getComputedStyle(document.documentElement)

/** "--bad" → valore della variabile; un colore già esplicito resta com'è */
export function cssColor(c: string): string {
  return c.startsWith('--') ? css().getPropertyValue(c).trim() : c
}

export function seriesColors(): string[] {
  return css().getPropertyValue('--series').split(',').map(s => s.trim()).filter(Boolean)
}

export const seriesColor = (i: number) => {
  const list = seriesColors()
  return list[i % list.length] ?? '#888888'
}

/** stesso colore con trasparenza (per le aree sotto le linee) */
export const soft = (hex: string) => (/^#[0-9a-f]{6}$/i.test(hex) ? hex + '22' : hex)

/** da osservare nei grafici: al cambio di tema vanno ridisegnati */
export const themeKey = () => theme.value
