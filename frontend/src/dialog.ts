import { ref } from 'vue'

/**
 * Finestre di conferma e di inserimento del pannello, al posto di window.confirm/prompt: quelle del browser
 * compaiono in cima alla pagina con il nome del sito e non seguono il tema. Una sola finestra alla volta,
 * disegnata da AppDialog in App.vue.
 */
export interface DialogState {
  message: string
  input: boolean          // true = chiede un testo
  value: string
  danger: boolean         // azione irreversibile: pulsante rosso
  resolve: (v: string | null) => void
}

export const dialog = ref<DialogState | null>(null)

function open(message: string, input: boolean, value = '', danger = false): Promise<string | null> {
  dialog.value?.resolve(null)             // una finestra ancora aperta vale come annullata
  return new Promise(resolve => { dialog.value = { message, input, value, danger, resolve } })
}

/** "sei sicuro?": true se si conferma */
export async function ask(message: string, danger = false): Promise<boolean> {
  return (await open(message, false, '', danger)) !== null
}

/** chiede un testo; null se si annulla */
export function askText(message: string, value = ''): Promise<string | null> {
  return open(message, true, value)
}

export function closeDialog(value: string | null) {
  const d = dialog.value
  dialog.value = null
  d?.resolve(value)
}
