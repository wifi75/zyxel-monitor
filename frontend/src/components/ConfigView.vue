<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api, type Backup, type GuardState, type PlanAp, type PolicyField, type PolicyOverview, type PolicyResult, type SiteItem } from '../api'
import { copyText, time } from '../format'
import { t } from '../i18n'
import Icon from './Icon.vue'
import type { IconName } from '../icons'

/**
 * Configurazione a tabella di confronto: una riga per impostazione, colonna "Sito" (vale per tutti)
 * e una colonna per AP con il valore attuale. Le modifiche restano in attesa finché non si applicano.
 */
const emit = defineEmits<{ changed: [] }>()

type Band = '2.4GHz' | '5GHz'
const BANDS: Band[] = ['2.4GHz', '5GHz']
const POWERS = [30, 27, 24, 21, 20, 18, 17, 15, 12, 10, 8, 6, 3]
const CHANNELS: Record<Band, number[]> = {
  '2.4GHz': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
  '5GHz': [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140],
}
const WIDTHS: Record<Band, string[]> = { '2.4GHz': ['20', '20/40'], '5GHz': ['20', '20/40', '20/40/80', '20/40/80/160'] }
/** nome della CLI → nome usato da Nebula (la CLI indica le larghezze ammesse, Nebula solo la massima) */
const widthLabel = (w: string) => `${w.split('/').pop()} MHz`

const data = ref<PolicyOverview | null>(null)
const items = ref<SiteItem[]>([])
const backups = ref<Backup[]>([])
const paused = ref<string[]>([])        // AP con la gestione sospesa dopo un ripristino
const restoreMsg = ref('')
const results = ref<PolicyResult[]>([])
const busy = ref('')
const error = ref('')

async function load() {
  try {
    const [d, i, b, p] = await Promise.all([api.policy(), api.siteItems(), api.backups(), api.paused()])
    data.value = d; items.value = i; backups.value = b; paused.value = p.aps
  } catch (e) { error.value = (e as Error).message }
}
onMounted(load)

// ---------- protezioni: interruttore, anteprima, prova su un AP ----------
const guardState = ref<GuardState | null>(null)
let guardTimer = 0
async function loadGuard() {
  try { guardState.value = await api.guard() } catch { /* il resto della pagina funziona lo stesso */ }
  window.clearTimeout(guardTimer)
  if (guardState.value?.rollout.status === 'running') guardTimer = window.setTimeout(loadGuard, 5000)
  else if (guardState.value && ['done', 'rolled_back'].includes(guardState.value.rollout.status)) load()
}
onMounted(loadGuard)
onUnmounted(() => window.clearTimeout(guardTimer))
const managing = computed(() => !!guardState.value?.enabled)
const rollout = computed(() => guardState.value?.rollout)
const running = computed(() => rollout.value?.status === 'running')
const now = ref(Date.now())
const clock = window.setInterval(() => { now.value = Date.now() }, 1000)
onUnmounted(() => window.clearInterval(clock))
const countdown = computed(() => {
  const s = Math.max(0, Math.round((rollout.value?.check_at ?? 0) - now.value / 1000))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
})
async function toggleManaging() {
  const on = !managing.value
  if (on && !window.confirm(t('Accendere la gestione dal pannello? Da ora il pannello può modificare gli AP e riallinearli alle impostazioni del sito.'))) return
  guardState.value = await api.setGuard(on)
}

interface Plan { aps: PlanAp[]; keys: string[] | null; radio: boolean; revert: (() => Promise<unknown>)[] }
const plan = ref<Plan | null>(null)
const firstAp = ref<number | null>(null)
async function openPlan(keys: string[] | null, radio: boolean, revert: Plan['revert']) {
  const r = await api.preview(keys, radio)
  plan.value = { aps: r.aps, keys, radio, revert }
  firstAp.value = r.aps.find(a => a.commands.length)?.id ?? r.aps[0]?.id ?? null
}
async function cancelPlan() {
  const p = plan.value
  plan.value = null
  if (!p) return
  busy.value = 'apply'
  try { for (const undo of p.revert) await undo(); await api.cancelPreview() }
  catch (e) { error.value = (e as Error).message } finally { busy.value = ''; await load() }
}
async function startRollout() {
  const p = plan.value
  if (!p) return
  busy.value = 'apply'
  try {
    const r = await api.rollout(p.keys, p.radio, firstAp.value)
    if (!r.ok) error.value = t(r.message)
    plan.value = null
  } catch (e) { error.value = (e as Error).message } finally { busy.value = ''; await loadGuard() }
}
const refreshSoon = () => { load(); window.setTimeout(load, 70_000) }

const aps = computed(() => data.value?.aps.filter(a => a.enabled) ?? [])

// ---------- righe della tabella ----------
type Kind = 'select' | 'text' | 'int' | 'password' | 'list'
interface Opt { value: string; label: string }
interface Row {
  id: string; group: string; label: string; hint?: string; kind: Kind; options?: Opt[]; unit?: string
  site: string | null                                  // valore del sito (null = non gestito)
  current: (apId: number) => string | null             // valore attuale sull'AP, già in chiaro
  override?: (apId: number) => string | null           // personalizzazione dell'AP (null = come il sito)
  perAp: boolean
  item?: SiteItem; band?: Band; field?: PolicyField
}

const powerLabel = (p: string) => (Number(p) >= 30 ? t('Massima') : `${p} dBm`)
const channelLabel = (c: string) => (c === 'auto' ? t('Automatico') : `${c}${Number(c) >= 100 ? ' DFS' : ''}`)
const bandText = (b: Band) => b.replace('GHz', ' GHz')
/** larghezze ammesse dal modello dell'AP (Wi-Fi 5: fino a 80 MHz, Wi-Fi 6: fino a 160) */
const apWidths = (apId: number, b: Band) => aps.value.find(a => a.id === apId)?.caps?.widths?.[b] ?? WIDTHS[b]
/** la larghezza chiesta se il modello la supporta, altrimenti la più ampia che supporta (come fa il server) */
function fitWidth(w: string, b: Band, apId: number): string {
  const allowed = apWidths(apId, b)
  return allowed.includes(w) ? w : allowed[allowed.length - 1] ?? w
}
/** scelta del sito adattata al modello (es. WPA3 su un Wi-Fi 5 → WPA2), come fa il server */
function fitChoice(key: string, v: unknown, apId: number): unknown {
  const allowed = aps.value.find(a => a.id === apId)?.caps?.choices?.[key]
  return allowed && typeof v === 'string' && !allowed.includes(v) ? allowed[allowed.length - 1] : v
}
/** true se il valore del sito supera le capacità di questo AP (es. 160 MHz o WPA3 su un Wi-Fi 5) */
function beyondModel(r: Row, apId: number): boolean {
  if (r.item) return r.item.value != null && fitChoice(r.item.key, r.item.value, apId) !== r.item.value
  if (r.field !== 'width' || !r.band) return false
  const own = r.override?.(apId)
  const want = own && own !== 'none' ? own : own === 'none' ? null : r.site
  return !!want && fitWidth(want, r.band, apId) !== want
}
/** voci che si possono attivare anche se l'AP oggi non le ha (le crea il comando), come sul server */
const CREATABLE = new Set(['guest_name', 'guest_password', 'wifi_schedule', 'mac_block', 'ntp_server', 'wifi_password'])
/** l'AP non ha questa voce nella sua configurazione: modello o firmware non la prevedono */
function unavailable(r: Row, apId: number): boolean {
  if (!r.item || r.item.kind === 'password' || CREATABLE.has(r.item.key)) return false
  const name = aps.value.find(a => a.id === apId)?.name
  return !!name && name in (r.item.current ?? {}) && r.item.current[name] == null
}
/** opzioni della casella di un singolo AP: solo quelle che il modello supporta */
function apOptions(r: Row, apId: number): Opt[] {
  if (r.field !== 'width' || !r.band) return r.options ?? []
  const allowed = apWidths(apId, r.band)
  return (r.options ?? []).filter(o => allowed.includes(o.value))
}

function radioRow(b: Band, f: PolicyField): Row {
  const opts: Opt[] = f === 'tx_power' ? POWERS.map(p => ({ value: String(p), label: powerLabel(String(p)) }))
    : f === 'channel' ? [{ value: 'auto', label: t('Automatico') }, ...CHANNELS[b].map(c => ({ value: String(c), label: channelLabel(String(c)) + (b === '2.4GHz' && [1, 6, 11].includes(c) ? ' — ' + t('consigliato') : '') }))]
    : WIDTHS[b].map(w => ({ value: w, label: widthLabel(w) + (w.endsWith("160") ? " — " + t("solo modelli che lo supportano") : "") }))
  const label = { tx_power: t('Potenza'), channel: t('Canale'), width: t('Larghezza') }[f]
  const siteValue = data.value?.site[b]?.[f]
  return {
    id: `radio-${b}-${f}`, group: 'radio', label: `${label} ${bandText(b)}`, kind: 'select', options: opts, perAp: true,
    hint: f === 'tx_power' ? (b === '2.4GHz' ? t('max di legge 20 dBm') : t('max 23 dBm, 30 sui canali DFS')) : undefined,
    site: siteValue != null ? String(siteValue) : null,
    current: id => {
      const v = aps.value.find(a => a.id === id)?.bands[b]?.current?.[f]
      if (v == null || v === '') return null
      return f === 'tx_power' ? `${v} dBm` : f === 'channel' ? channelLabel(String(v)) : widthLabel(String(v))
    },
    override: id => {
      const o = aps.value.find(a => a.id === id)?.bands[b]?.override?.[f]
      return o == null ? null : o === -1 || o === 'none' ? 'none' : String(o)
    },
    band: b, field: f,
  }
}

const ITEM_GROUP: Record<string, string> = {
  rete: 'rete', ospiti: 'ospiti', radio: 'roaming', sistema: 'sistema', dot11kv: 'roaming', dot11r: 'roaming',
}
const CHOICE_LABEL: Record<string, string> = {
  disable: 'Spento', standard: 'Standard', force: 'Forzato', off: 'Spento', wpa2: 'WPA2', wpa3: 'WPA3', 'wpa2/wpa3': 'WPA2 + WPA3',
  'daily-04': 'Ogni giorno 4:00', 'sun-04': 'Domenica 4:00', 'sat-04': 'Sabato 4:00', '0': 'Disattivata',
}
/** etichette [spento, acceso] per le voci sì/no: parole concrete invece di "attivo/spento" */
const BOOL_TEXT: Record<string, [string, string]> = {
  ssid_hidden: ['visibile', 'nascosta'], led_off: ['accesi', 'spenti'], snmp_rw: ['spento', 'attivo'],
  load_balancing: ['spento', 'attivo'], dot11kv: ['spento', 'attivo'], dot11r: ['spento', 'attivo'],
  hostname_sync: ['no', 'sì'],
}
/** testo per il valore vuoto, che per alcune voci significa "spento" */
const EMPTY_TEXT: Record<string, string> = { wifi_schedule: 'sempre acceso', guest_name: 'spenta' }
function itemText(i: SiteItem, v: unknown): string | null {
  if (v == null) return null
  if (i.kind === 'password') return v ? t('impostata') : null      // non trovata = non letta, non "nessuna"
  if (typeof v === 'boolean') return t((BOOL_TEXT[i.key] ?? ['spento', 'attivo'])[v ? 1 : 0])
  if (Array.isArray(v)) return v.length ? t('{n} bloccati', { n: v.length }) : t('nessuno')
  if (i.kind === 'choice') return CHOICE_LABEL[String(v)] ? t(CHOICE_LABEL[String(v)]) : (i.unit ? `${v} ${i.unit}` : String(v))
  if (v === '') return t(EMPTY_TEXT[i.key] ?? 'spento')
  return i.unit ? `${v} ${i.unit}` : String(v)
}
function itemRow(i: SiteItem): Row {
  const kind: Kind = i.kind === 'bool' || i.kind === 'choice' ? 'select' : i.kind
  const options: Opt[] | undefined = i.kind === 'bool'
    ? [{ value: 'true', label: itemText(i, true)! }, { value: 'false', label: itemText(i, false)! }]
    : i.kind === 'choice' ? i.choices.map(c => ({ value: c, label: itemText(i, c) ?? c })) : undefined
  const site = i.value == null ? null : i.kind === 'password' ? (i.value ? '••••••••' : null)
    : Array.isArray(i.value) ? i.value.join('\n') : String(i.value)
  return {
    id: `item-${i.key}`, group: ITEM_GROUP[i.key] ?? ITEM_GROUP[i.section] ?? 'sistema', label: t(i.label), hint: t(i.help),
    kind, options, unit: i.unit, site, perAp: false, item: i,
    current: id => { const name = aps.value.find(a => a.id === id)?.name; return name ? itemText(i, i.current?.[name]) : null },
  }
}

const GROUPS: { key: string; title: string; icon: IconName; tone: string }[] = [
  { key: 'radio', title: 'Radio', icon: 'wifi', tone: 'var(--blue)' },
  { key: 'rete', title: 'Rete Wi-Fi', icon: 'lock', tone: 'var(--pink)' },
  { key: 'ospiti', title: 'Rete ospiti', icon: 'users', tone: 'var(--violet)' },
  { key: 'roaming', title: 'Roaming', icon: 'shuffle', tone: 'var(--teal)' },
  { key: 'sistema', title: 'Sistema', icon: 'wrench', tone: 'var(--amber)' },
]
const rows = computed<Row[]>(() => [
  ...BANDS.flatMap(b => (['tx_power', 'channel', 'width'] as PolicyField[]).map(f => radioRow(b, f))),
  ...items.value.filter(i => i.key !== 'hostname_sync').map(itemRow),
])
const grouped = computed(() => GROUPS.map(g => ({ ...g, rows: rows.value.filter(r => r.group === g.key) })).filter(g => g.rows.length))

// ---------- testo e stato delle caselle ----------
/** valore da confrontare fra gli AP: per la potenza quello impostato (la reale dipende dal modello) */
function compared(r: Row, apId: number): string | null {
  if (r.field === 'tx_power' && r.band) {
    const c = aps.value.find(a => a.id === apId)?.bands[r.band]?.current?.tx_config
    return c == null ? r.current(apId) : powerLabel(String(c))
  }
  return r.current(apId)
}
/** valore comune a tutti gli AP (null se sono diversi fra loro o non letti) */
function observed(r: Row): string | null {
  const vals = [...new Set(aps.value.filter(a => !unavailable(r, a.id)).map(a => compared(r, a.id)).filter(v => v != null))]
  return vals.length === 1 ? vals[0] : null
}
function siteLabel(r: Row): string {
  if (r.site == null) return t('non gestito')
  if (r.kind === 'select') return r.options?.find(o => o.value === r.site)?.label ?? r.site
  if (r.kind === 'list') {
    const n = r.site.split('\n').filter(Boolean).length
    return n ? t('{n} bloccati', { n }) : t('nessuno')
  }
  if (r.site === '') return t(EMPTY_TEXT[r.item?.key ?? ''] ?? 'spento')
  return r.unit ? `${r.site} ${r.unit}` : r.site
}

/** pallino: verde se la funzione è attiva, grigio se spenta, nessuno per i valori numerici/testo */
const ON_WORDS = new Set(['attivo', 'active', 'on', 'nascosta', 'spenti', 'sì'].map(w => w.toLowerCase()))
function dot(r: Row, text: string | null): '' | 'on' | 'off' {
  if (!text || !r.item) return ''
  const k = r.item.kind
  if (k !== 'bool' && !(k === 'choice' && r.item.key !== 'rssi_kickout' && r.item.key !== 'security_mode')) return ''
  const low = text.toLowerCase()
  if (ON_WORDS.has(low)) return 'on'
  return [t('spento'), t('Spento'), t('Disattivata'), t('visibile'), t('accesi'), t('no')].map(x => x.toLowerCase()).includes(low) ? 'off' : 'on'
}
/** confronto fra valore attuale e valore voluto; la potenza oltre il limite dell'AP conta come uguale */
function cellState(r: Row, apId: number): 'same' | 'diff' | 'none' {
  const now = r.current(apId)
  if (r.field) {
    const own = r.override?.(apId)
    const want = own && own !== 'none' ? own : own === 'none' ? null : r.site
    if (want == null) return 'none'
    if (r.field === 'tx_power') {
      const st = aps.value.find(x => x.id === apId)?.bands[r.band!]?.status ?? ''
      return st === 'ok' || st === 'capped' ? 'same' : 'diff'
    }
    const wantText = r.field === 'channel' ? channelLabel(want) : widthLabel(fitWidth(want, r.band!, apId))
    return now === wantText ? 'same' : 'diff'
  }
  if (r.site == null || !r.item) return 'none'
  if (r.kind === 'password') return 'same'
  const name = aps.value.find(a => a.id === apId)?.name
  const cur = name ? r.item.current?.[name] : undefined
  if (cur === undefined || cur === null) return 'same'          // non ancora letto
  return norm(cur) === norm(fitChoice(r.item.key, r.item.value, apId)) ? 'same' : 'diff'
}
/** valore confrontabile: liste ordinate, booleani e numeri come testo */
function norm(v: unknown): string {
  if (Array.isArray(v)) return [...v].map(x => String(x).toLowerCase()).sort().join(',')
  return String(v)
}
/** stato di una casella AP: in attesa, non gestita (arancione se gli AP non sono d'accordo) o confronto */
function apClass(r: Row, apId: number): string {
  if (pending.value[cellKey(r, apId)]) return 'pend'
  if (unavailable(r, apId)) return 'na'
  // solo monitoraggio: le regole del pannello non contano, si confrontano gli AP fra loro
  if (!managing.value) {
    const vals = new Set(aps.value.filter(a => !unavailable(r, a.id)).map(a => compared(r, a.id)).filter(v => v != null))
    return vals.size > 1 ? 'diff' : compared(r, apId) == null ? 'none' : 'same'
  }
  // valori non letti (null, es. password sui firmware vecchi) non contano come differenza
  if (r.site == null && !r.override?.(apId)) {
    return new Set(aps.value.map(a => r.current(a.id)).filter(v => v != null)).size > 1 ? 'diff' : 'none'
  }
  return cellState(r, apId)
}

// ---------- modifiche in attesa ----------
interface Pending { row: Row; apId: number | null; value: string | null }
const pending = ref<Record<string, Pending>>({})
const editing = ref<string | null>(null)
const draft = ref('')
const draft2 = ref('')                 // ripetizione della password
/** errore della password in modifica: lunghezza WPA o le due non coincidono */
const pwdError = computed(() => {
  if (!draft.value) return ''
  if (draft.value.length < 8 || draft.value.length > 63) return t('Da 8 a 63 caratteri')
  if (draft.value !== draft2.value) return t('Le due password non coincidono')
  return ''
})
const pendingCount = computed(() => Object.keys(pending.value).length)
const cellKey = (r: Row, apId: number | null) => `${r.id}|${apId ?? 'site'}`

function startEdit(r: Row, apId: number | null) {
  const k = cellKey(r, apId)
  editing.value = k
  draft2.value = ''
  const p = pending.value[k]
  draft.value = p ? (p.value ?? (apId === null ? 'unmanaged' : 'inherit'))
    : apId === null ? (r.kind === 'password' ? '' : r.site ?? (r.kind === 'select' ? 'unmanaged' : ''))
    : (r.override?.(apId) ?? 'inherit')
}
/** voci in cui un valore vuoto ha un significato ("spento"), non "non gestito" */
const EMPTY_MEANS_OFF = new Set(['guest_name', 'wifi_schedule'])
function commit(r: Row, apId: number | null, value: string) {
  const k = cellKey(r, apId)
  if (r.kind === 'password' && value === '') { editing.value = null; return }   // nessuna nuova password
  if (r.kind === 'password' && pwdError.value) return
  const keepEmpty = value === '' && (r.kind === 'list' || (r.item && EMPTY_MEANS_OFF.has(r.item.key)))
  const v = value === 'unmanaged' || (value === '' && !keepEmpty) ? null : value
  const original = apId === null ? r.site : (r.override?.(apId) ?? 'inherit')
  if ((v ?? '') === (original ?? '') && !(r.kind === 'password' && v)) delete pending.value[k]
  else pending.value[k] = { row: r, apId, value: v }
  editing.value = null
}
const cancelAll = () => { pending.value = {}; editing.value = null }

function pendingLabel(p: Pending): string {
  if (p.apId !== null && p.value === 'inherit') return t('come il sito')
  if (p.value == null || p.value === 'none') return t('non gestito')
  if (p.row.kind === 'password') return '••••••••'
  if (p.row.kind === 'select') return p.row.options?.find(o => o.value === p.value)?.label ?? p.value
  if (p.row.kind === 'list') {
    const n = p.value.split(/\s+/).filter(Boolean).length
    return n ? t('{n} bloccati', { n }) : t('nessuno')
  }
  if (p.value === '') return t('spento')
  return p.row.unit ? `${p.value} ${p.row.unit}` : p.value
}

const DANGER: Record<string, string> = {
  ssid_name: 'Cambiare il nome della rete scollega tutti i dispositivi.',
  wifi_password: 'Cambiare la password scollega tutti i dispositivi.',
  wifi_schedule: 'Fuori orario il Wi-Fi sarà spento per tutti.',
}

async function applyAll() {
  const list = Object.values(pending.value)
  const warnings = list.map(p => (p.row.item && p.value != null ? DANGER[p.row.item.key] ?? '' : '')).filter(Boolean)
  if (list.some(p => p.row.item?.key === 'security_mode' && p.value === 'wpa3')) warnings.push('Solo WPA3: i dispositivi più vecchi non si collegheranno più.')
  if (warnings.length && !window.confirm([...new Set(warnings)].map(w => t(w)).join('\n') + '\n\n' + t('Procedere?'))) return
  busy.value = 'apply'; error.value = ''; results.value = []
  // 1) si salvano le regole senza inviarle; 2) anteprima dei comandi per AP; 3) conferma → prova su un AP,
  //    verifica dei dispositivi collegati, poi tutti gli altri. Annullando si rimettono i valori di prima.
  let radio = false
  const itemKeys: string[] = []
  const revert: (() => Promise<unknown>)[] = []
  try {
    for (const p of list) {
      const r = p.row
      if (r.field && r.band) {
        const f = r.field, band = r.band
        const conv = (v: string | null) => (v == null || v === 'inherit' ? null : v === 'none' ? 'none' : f === 'tx_power' ? Number(v) : v)
        if (p.apId === null) {
          const old = data.value?.site[band]?.[f] ?? null
          revert.push(() => api.setSitePolicy(band, f, old, false))
          await api.setSitePolicy(band, f, conv(p.value), false)
        } else {
          const apId = p.apId
          const o = data.value?.aps.find(a => a.id === apId)?.bands[band]?.override[f] ?? null
          const old = o === -1 || o === 'none' ? 'none' : o
          revert.push(() => api.setApPolicy(apId, band, f, old, false))
          await api.setApPolicy(apId, band, f, conv(p.value), false)
        }
        radio = true
      } else {
        const i = r.item!
        const v = p.value == null ? null : i.kind === 'bool' ? p.value === 'true' : i.kind === 'int' ? Number(p.value)
          : i.kind === 'list' ? p.value.split(/[\s,;]+/).filter(Boolean) : p.value
        // la password vecchia non è nota al browser: annullando si toglie solo se prima non era gestita
        if (i.kind !== 'password') revert.push(() => api.setSiteItem(i.key, i.value, false))
        else if (!i.value) revert.push(() => api.setSiteItem(i.key, null, false))
        await api.setSiteItem(i.key, v, false)
        if (v != null) itemKeys.push(i.key)
      }
      delete pending.value[cellKey(r, p.apId)]
    }
    await openPlan(itemKeys, radio, revert)
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = ''; await load() }
}

/** riapplica a tutti gli AP la configurazione del sito, passando anche qui da anteprima e prova */
async function reapplyAll() {
  busy.value = 'reapply'; error.value = ''
  try { await openPlan(null, true, []) } catch (e) { error.value = (e as Error).message } finally { busy.value = '' }
}

// ---------- backup ----------
const showBackups = ref(false)
async function restoreBackup(b: Backup) {
  if (!window.confirm(t('Rimettere su {ap} la configurazione Wi-Fi del {when}? Le radio si ricaricano per qualche secondo e il pannello smette di gestire questo AP finché non premi Riprendi.', { ap: b.ap, when: time(b.ts) }))) return
  busy.value = 'restore'; restoreMsg.value = ''
  try {
    const r = await api.restoreBackup(b.id)
    restoreMsg.value = `${b.ap}: ${t(r.message)}`
    paused.value = (await api.paused()).aps
  } catch (e) { restoreMsg.value = String(e) } finally { busy.value = '' }
}
async function resume(ap: string) {
  paused.value = (await api.setPaused(ap, false)).aps
}
const allBackups = ref(false)
const visibleBackups = computed(() => (allBackups.value ? backups.value : backups.value.slice(0, 8)))
const shown = ref<Backup & { text: string } | null>(null)
const copied = ref(false)
async function backupAll() {
  busy.value = 'backup'
  try { results.value = (await api.backupAll()).results; await load() } catch (e) { error.value = (e as Error).message }
  finally { busy.value = '' }
}
async function showBackup(b: Backup) {
  if (shown.value?.id === b.id) { shown.value = null; return }
  shown.value = await api.backup(b.id); copied.value = false
}
function download() {
  if (!shown.value) return
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([shown.value.text], { type: 'text/plain' }))
  a.download = `${shown.value.ap}-${new Date(shown.value.ts * 1000).toISOString().slice(0, 16).replace(':', '')}.cfg`
  a.click(); URL.revokeObjectURL(a.href)
}
async function copyBackup() { copied.value = await copyText(shown.value?.text ?? '') }
</script>

<template>
  <main class="cfg">
    <div class="cfg-bar card">
      <span class="small muted grow">
        {{ t('Clicca una casella per cambiarla. La colonna Sito vale per tutti gli AP; potenza, canale e larghezza si possono personalizzare anche per un singolo AP.') }}
      </span>
      <span class="val same">{{ t('uguale al sito') }}</span>
      <span class="val diff">{{ t('diverso') }}</span>
      <span class="val none">{{ t('non gestito') }}</span>
      <span class="val pend">{{ t('da applicare') }}</span>
      <button class="ghost" :class="{ active: showBackups }" @click="showBackups = !showBackups"><Icon name="save" :size="15" /> {{ t('Backup') }}</button>
      <button class="ghost" :disabled="!!busy || !managing || running" :title="t('Riapplica subito a tutti gli AP la configurazione del sito')" @click="reapplyAll">
        {{ busy === 'reapply' ? t('Applico…') : '↻ ' + t('Riapplica') }}</button>
      <button v-if="pendingCount" class="ghost" :disabled="!!busy" @click="cancelAll">{{ t('Annulla') }}</button>
      <button class="primary" :disabled="!pendingCount || !!busy || !managing || running" @click="applyAll">
        {{ busy === 'apply' ? t('Applico…') : t('Applica modifiche ({n})', { n: pendingCount }) }}
      </button>
    </div>

    <!-- interruttore generale: spento = il pannello solo monitora -->
    <div class="guard-bar" :class="managing ? 'on' : 'off'">
      <button class="switch" role="switch" :aria-checked="managing" :aria-label="t('Gestione dal pannello')" @click="toggleManaging"><span /></button>
      <div class="grow">
        <strong>{{ managing ? t('Gestione dal pannello accesa') : t('Solo monitoraggio') }}</strong>
        <span class="muted small"> — {{ managing
          ? t('Ogni modifica si prova prima su un AP; se i dispositivi collegati calano si torna indietro da soli.')
          : t('Il pannello non modifica gli AP. Accendi la gestione per applicare le impostazioni.') }}</span>
      </div>
    </div>

    <!-- stato della prova controllata -->
    <div v-if="rollout && rollout.status !== 'idle'" class="note"
         :class="rollout.status === 'running' ? 'warn' : rollout.status === 'done' ? 'ok' : 'ko'">
      <template v-if="running">
        <strong>{{ t('Prova in corso') }}: {{ rollout.phase }}</strong>
        <template v-if="rollout.check_at"> — {{ t('verifica fra') }} {{ countdown }}</template>
        · {{ t('dispositivi collegati prima') }}: {{ rollout.clients_before }}
      </template>
      <template v-else>
        <strong>{{ t(rollout.message ?? '') }}</strong>
        <span v-if="rollout.clients_after != null"> · {{ t('dispositivi') }}: {{ rollout.clients_before }} → {{ rollout.clients_after }}</span>
      </template>
      <div v-if="rollout.lost?.length" class="small">{{ t('Non rientrati') }}: {{ rollout.lost.join(', ') }}</div>
    </div>

    <!-- anteprima dei comandi, scelta dell'AP di prova -->
    <section v-if="plan" class="card plan">
      <h2>{{ t('Anteprima: cosa verrà inviato') }}</h2>
      <div class="plan-rows">
        <div v-for="a in plan.aps" :key="a.id" class="plan-row">
          <label class="plan-pick">
            <input v-model="firstAp" type="radio" :value="a.id" :disabled="!a.commands.length" />
            <strong>{{ a.ap }}</strong>
          </label>
          <div class="grow">
            <span :class="{ muted: !a.commands.length }">{{ a.commands.length ? a.changes : t('Nessuna modifica') }}</span>
            <details v-if="a.commands.length">
              <summary class="small muted">{{ t('{n} comandi', { n: a.commands.length }) }}</summary>
              <pre class="raw">{{ a.commands.join('\n') }}</pre>
            </details>
          </div>
        </div>
      </div>
      <p class="small muted">{{ t("L'AP selezionato riceve la modifica per primo. Dopo 5 minuti si contano i dispositivi collegati: se non sono calati si passa agli altri AP, altrimenti si torna al backup fatto subito prima.") }}</p>
      <div class="actions"><span class="grow" />
        <button class="ghost" :disabled="!!busy" @click="cancelPlan">{{ t('Annulla') }}</button>
        <button class="primary" :disabled="!!busy || !plan.aps.some(a => a.commands.length)" @click="startRollout">
          {{ t('Prova e poi applica a tutti') }}</button>
      </div>
    </section>

    <p v-if="error" class="note ko">{{ error }}</p>
    <div v-if="results.length" class="card cfg-results">
      <div v-for="(r, n) in results" :key="n" class="cfg-result">
        <span class="status" :class="r.ok ? 'on' : 'off'" /><strong>{{ r.ap }}</strong><span class="muted small">{{ r.message }}</span>
      </div>
      <button class="ghost small cfg-close" :title="t('Chiudi')" @click="results = []">✕</button>
    </div>

    <!-- backup, apribili dalla barra -->
    <div v-if="paused.length" class="note warn">
      <strong>{{ t('In pausa') }}:</strong>
      <template v-for="ap in paused" :key="ap"> {{ ap }} <button class="ghost small" @click="resume(ap)">{{ t('Riprendi') }}</button></template>
      <span class="muted small"> — {{ t('il pannello non modifica questi AP finché non riprendi la gestione.') }}</span>
    </div>
    <p v-if="restoreMsg" class="note">{{ restoreMsg }}</p>
    <section v-if="showBackups" class="card">
      <div class="section-head">
        <h2>{{ t('Backup delle configurazioni') }}</h2>
        <button :disabled="!!busy" @click="backupAll">{{ busy === 'backup' ? t('Salvo…') : t('Salva backup di tutti') }}</button>
        <button class="ghost small cfg-close" :title="t('Chiudi')" @click="showBackups = false; shown = null">✕</button>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>{{ t('Quando') }}</th><th>Access point</th><th>{{ t('Dimensione') }}</th><th /></tr></thead>
          <tbody>
            <template v-for="b in visibleBackups" :key="b.id">
              <tr>
                <td class="small">{{ time(b.ts) }}</td><td><strong>{{ b.ap }}</strong></td>
                <td class="small">{{ (b.size / 1024).toFixed(1) }} KB</td>
                <td class="row-actions">
                  <button class="ghost small" @click="showBackup(b)">{{ shown?.id === b.id ? t('Chiudi') : t('Vedi') }}</button>
                  <button class="ghost small" :disabled="!!busy" @click="restoreBackup(b)">{{ t('Ripristina') }}</button>
                </td>
              </tr>
              <tr v-if="shown?.id === b.id" class="edit-row"><td colspan="4">
                <div class="actions"><span class="grow" />
                  <button class="ghost small" @click="copyBackup">{{ copied ? t('Copiato ✓') : t('Copia') }}</button>
                  <button class="ghost small" @click="download">{{ t('Scarica') }}</button></div>
                <pre class="raw">{{ shown.text }}</pre>
              </td></tr>
            </template>
            <tr v-if="!backups.length"><td colspan="4" class="muted">{{ t('Nessun backup: salvane uno adesso.') }}</td></tr>
          </tbody>
        </table>
      </div>
      <button v-if="backups.length > 8" class="ghost small" @click="allBackups = !allBackups">
        {{ allBackups ? t('Mostra solo gli ultimi') : t('Mostra tutti ({n})', { n: backups.length }) }}</button>
    </section>

    <!-- tabella di confronto -->
    <div class="card cmp-card">
      <div class="table-wrap">
        <table class="cmp">
          <thead><tr>
            <th>{{ t('Impostazione') }}</th><th class="site-col">{{ managing ? t('Sito (tutti)') : t('Adesso sugli AP') }}</th>
            <th v-for="a in aps" :key="a.id" class="ap-col">
              {{ a.name }}
              <small v-if="a.caps?.model" class="ap-model">{{ a.caps.model }}<template v-if="a.caps.wifi"> · Wi-Fi {{ a.caps.wifi }}</template></small>
            </th>
          </tr></thead>
          <tbody>
            <template v-for="g in grouped" :key="g.key">
              <tr class="cmp-group" :style="{ '--tone': g.tone }"><td :colspan="2 + aps.length"><Icon :name="g.icon" :size="14" /> {{ t(g.title) }}</td></tr>
              <tr v-for="r in g.rows" :key="r.id" class="cmp-row" :style="{ '--tone': g.tone }">
                <td class="cmp-set">
                  <span>{{ r.label }}</span>
                  <span v-if="r.hint" class="cmp-info" :title="r.hint">ⓘ</span>
                  <small v-if="r.field === 'tx_power'">{{ r.hint }}</small>
                </td>

                <td class="site-col">
                  <div v-if="editing === cellKey(r, null)" class="cmp-edit">
                    <select v-if="r.kind === 'select'" v-model="draft" @change="commit(r, null, draft)">
                      <option value="unmanaged">{{ t('Non gestito') }}</option>
                      <option v-for="o in r.options" :key="o.value" :value="o.value">{{ o.label }}</option>
                    </select>
                    <textarea v-else-if="r.kind === 'list'" v-model="draft" rows="3" placeholder="aa:bb:cc:dd:ee:ff" />
                    <input v-else v-model="draft" :type="r.kind === 'password' ? 'password' : r.kind === 'int' ? 'number' : 'text'"
                           :placeholder="r.kind === 'password' ? t('nuova password') : t('vuoto = non gestito')" @keyup.enter="commit(r, null, draft)" />
                    <template v-if="r.kind === 'password'">
                      <input v-model="draft2" type="password" :placeholder="t('ripeti la password')" @keyup.enter="commit(r, null, draft)" />
                      <small v-if="pwdError && draft2" class="error">{{ pwdError }}</small>
                    </template>
                    <div class="cmp-edit-btns">
                      <button class="ghost small" @click="editing = null">{{ t('Annulla') }}</button>
                      <button v-if="r.kind !== 'select'" class="primary small" :disabled="r.kind === 'password' && !!pwdError"
                              @click="commit(r, null, draft)">OK</button>
                    </div>
                  </div>
                  <span v-else-if="!managing" class="site-cell observed" :class="{ none: observed(r) == null }"
                        :title="t('Solo monitoraggio: valore che hanno adesso gli AP (impostato da Nebula)')">
                    <span class="grow">{{ observed(r) ?? t('valori diversi') }}</span>
                  </span>
                  <button v-else class="site-cell" :class="pending[cellKey(r, null)] ? 'pend' : r.site == null ? 'none' : 'set'"
                          :title="t('Clicca per cambiare')" @click="startEdit(r, null)">
                    <span v-if="!pending[cellKey(r, null)] && r.site != null && dot(r, siteLabel(r))" class="dot" :class="dot(r, siteLabel(r))" />
                    <span class="grow">{{ pending[cellKey(r, null)] ? pendingLabel(pending[cellKey(r, null)]) : r.site == null ? t("lascia all'AP") : siteLabel(r) }}</span>
                    <span class="pen">✎</span>
                  </button>
                </td>

                <td v-for="a in aps" :key="a.id" class="ap-col">
                  <div v-if="editing === cellKey(r, a.id)" class="cmp-edit">
                    <select v-model="draft" @change="commit(r, a.id, draft)">
                      <option value="inherit">{{ t('Come il sito') }}</option>
                      <option value="none">{{ t('Non gestito') }}</option>
                      <option v-for="o in apOptions(r, a.id)" :key="o.value" :value="o.value">{{ o.label }}</option>
                    </select>
                    <div class="cmp-edit-btns"><button class="ghost small" @click="editing = null">{{ t('Annulla') }}</button></div>
                  </div>
                  <component :is="r.perAp && a.configurable ? 'button' : 'span'" class="ap-cell" :class="[apClass(r, a.id), { click: r.perAp && a.configurable }]"
                             :title="r.perAp && a.configurable ? t('Clicca per personalizzare questo AP') : t('Vale per tutto il sito: si cambia nella colonna Sito')"
                             @click="r.perAp && a.configurable && startEdit(r, a.id)">
                    <template v-if="pending[cellKey(r, a.id)]">{{ pendingLabel(pending[cellKey(r, a.id)]) }}</template>
                    <template v-else>
                      <span v-if="dot(r, r.current(a.id))" class="dot" :class="dot(r, r.current(a.id))" />
                      <span v-if="r.current(a.id) == null && r.item?.kind === 'password'" class="muted" :title="t('Questo firmware non permette di leggere la password: è impostata, ma il pannello non può vederla.')">{{ t('non leggibile') }}</span>
                      <span v-else-if="unavailable(r, a.id)" class="muted" :title="t('Questo modello o firmware non ha questa impostazione: il pannello non la invia.')">{{ t('non disponibile') }}</span>
                      <template v-else>{{ r.current(a.id) ?? '—' }}</template>
                      <span v-if="apClass(r, a.id) === 'same'" class="mark ok">✓</span>
                      <span v-else-if="apClass(r, a.id) === 'diff'" class="mark warn">⚠</span>
                      <small v-if="beyondModel(r, a.id)" class="muted" :title="t('Il valore del sito non è supportato da questo modello: si usa il massimo che supporta.')">{{ t('max del modello') }}</small>
                      <span v-if="r.override?.(a.id) && r.override(a.id) !== 'none'" class="own" :title="t('personalizzato')">★</span>
                    </template>
                  </component>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>
  </main>
</template>
