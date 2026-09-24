<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, type Backup, type PolicyField, type PolicyOverview, type PolicyResult } from '../api'
import { copyText, time } from '../format'
import Icon from './Icon.vue'
import SiteSettings from './SiteSettings.vue'
import { t } from '../i18n'

/** Configurazione centralizzata: il profilo del sito vale per tutti, ogni AP può personalizzare. */
const emit = defineEmits<{ changed: [] }>()

const BANDS = ['2.4GHz', '5GHz'] as const
type Band = typeof BANDS[number]
const POWERS = [30, 27, 24, 21, 20, 18, 17, 15, 12, 10, 8, 6, 3]
const CHANNELS: Record<Band, number[]> = {
  '2.4GHz': [1, 6, 11, 2, 3, 4, 5, 7, 8, 9, 10, 12, 13],
  '5GHz': [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140],
}
const WIDTHS: Record<Band, string[]> = { '2.4GHz': ['20', '20/40'], '5GHz': ['20', '20/40', '20/40/80'] }
const FIELDS: { key: PolicyField; label: string }[] = [
  { key: 'tx_power', label: 'Potenza' }, { key: 'channel', label: 'Canale' }, { key: 'width', label: 'Larghezza' },
]
const powerLabel = (p: number) => (p >= 30 ? t('Massima consentita') : `${p} dBm`)
const channelLabel = (c: string | number) => (c === 'auto' ? t('Automatico') : Number(c) >= 100 ? t('Canale {n} (DFS, fino a 30 dBm)', { n: c }) : t('Canale {n}', { n: c }))
const widthLabel = (w: string) => `${w} MHz`
/** testo del valore del sito, per l'opzione "Come il sito" */
function siteText(b: Band, f: PolicyField): string {
  const v = data.value?.site[b]?.[f]
  if (v == null) return t('non gestito')
  return f === 'tx_power' ? powerLabel(Number(v)) : f === 'channel' ? channelLabel(v) : widthLabel(String(v))
}
const val = (e: Event) => (e.target as HTMLSelectElement).value

const data = ref<PolicyOverview | null>(null)
const results = ref<PolicyResult[]>([])
const busy = ref('')
const error = ref('')
const backups = ref<Backup[]>([])
const shown = ref<Backup & { text: string } | null>(null)
const copied = ref(false)

async function load() {
  try {
    const [d, b] = await Promise.all([api.policy(), api.backups()])
    data.value = d; backups.value = b
  } catch (e) { error.value = (e as Error).message }
}
onMounted(load)
// lo stato reale arriva con la lettura successiva: si ricarica dopo qualche secondo
const refreshSoon = () => { load(); window.setTimeout(load, 70_000) }

async function run(kind: string, fn: () => Promise<{ results: PolicyResult[] }>) {
  busy.value = kind; error.value = ''
  try { results.value = (await fn()).results; await load(); emit('changed'); refreshSoon() }
  catch (e) { error.value = (e as Error).message } finally { busy.value = '' }
}

const bandLabel = (b: string) => b.replace('GHz', ' GHz')
const bandClass = (b: string) => (b.startsWith('2') ? 'b24' : 'b5')

/** "" = sito: non gestito; "inherit" = AP: come il sito; "none" = AP: non gestito */
function toValue(f: PolicyField, v: string): number | string | null {
  if (v === '' || v === 'inherit') return null
  if (v === 'none') return 'none'
  return f === 'tx_power' ? Number(v) : v
}
function setSite(band: Band, f: PolicyField, v: string) {
  run(`site-${band}-${f}`, () => api.setSitePolicy(band, f, toValue(f, v)))
}
function setAp(apId: number, band: Band, f: PolicyField, v: string) {
  run(`ap-${apId}-${band}-${f}`, () => api.setApPolicy(apId, band, f, toValue(f, v)))
}
/** valore da mostrare nella select di un AP */
function apSelect(o: Record<PolicyField, number | string | null>, f: PolicyField): string {
  const v = o[f]
  if (v == null) return 'inherit'
  if (v === -1 || v === 'none') return 'none'
  return String(v)
}
const applyAll = () => run('apply', () => api.applyPolicy())
const backupAll = () => run('backup', () => api.backupAll())

async function showBackup(b: Backup) {
  if (shown.value?.id === b.id) { shown.value = null; return }
  shown.value = await api.backup(b.id); copied.value = false
}
function download() {
  if (!shown.value) return
  const blob = new Blob([shown.value.text], { type: 'text/plain' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `${shown.value.ap}-${new Date(shown.value.ts * 1000).toISOString().slice(0, 16).replace(':', '')}.cfg`
  a.click()
  URL.revokeObjectURL(a.href)
}
async function copyBackup() { copied.value = await copyText(shown.value?.text ?? '') }

const STATUS: Record<string, { label: string; tone: string }> = {
  ok: { label: 'allineato', tone: 'var(--green)' },
  pending: { label: 'in applicazione', tone: 'var(--amber)' },
  capped: { label: 'al massimo di legge', tone: 'var(--orange)' },
  unknown: { label: 'non letto', tone: 'var(--muted)' },
  unmanaged: { label: 'non gestito', tone: 'var(--muted)' },
}
const configurable = computed(() => data.value?.aps.filter(a => a.configurable && a.enabled) ?? [])
const others = computed(() => data.value?.aps.filter(a => !a.configurable || !a.enabled) ?? [])
</script>

<template>
  <main class="cfg">
    <section class="card cfg-hero">
      <div class="apm-hero-icon"><Icon name="sliders" :size="22" /></div>
      <div class="grow">
        <h2>{{ t('Configurazione centralizzata') }}</h2>
        <p class="muted small">
          {{ t('Il') }} <strong>{{ t('profilo del sito') }}</strong> {{ t('vale per tutti gli access point; ogni AP può avere un valore suo.') }}
          {{ t('Le modifiche si applicano subito via SSH e il sistema le') }} <strong>{{ t('mantiene') }}</strong>{{ t(': se un AP torna indietro (riavvio o sincronizzazione di Nebula) viene riallineato da solo.') }}
        </p>
      </div>
      <button class="primary" :disabled="!!busy || !configurable.length" @click="applyAll">{{ busy === 'apply' ? t('Applico…') : t('Applica ora a tutti') }}</button>
    </section>

    <p v-if="error" class="note ko">{{ error }}</p>
    <div v-if="results.length" class="card cfg-results">
      <div v-for="r in results" :key="r.ap" class="cfg-result" :class="r.ok ? 'ok' : 'ko'">
        <span class="status" :class="r.ok ? 'on' : 'off'" /><strong>{{ r.ap }}</strong><span class="muted small">{{ r.message }}</span>
      </div>
    </div>

    <!-- profilo del sito -->
    <section class="card">
      <h2 class="mb">{{ t('Profilo del sito') }} <span class="muted small">{{ t('(vale per tutti gli AP)') }}</span></h2>
      <div class="cfg-bands">
        <div v-for="b in BANDS" :key="b" class="cfg-band radio" :class="bandClass(b)">
          <b>{{ bandLabel(b) }}</b>
          <div class="cfg-fields">
            <label>{{ t('Potenza') }}
              <select :value="data?.site[b]?.tx_power ?? ''" :disabled="!!busy" @change="setSite(b, 'tx_power', val($event))">
                <option value="">{{ t('Non gestita') }}</option>
                <option v-for="p in POWERS" :key="p" :value="p">{{ powerLabel(p) }}</option>
              </select>
            </label>
            <label>{{ t('Canale') }}
              <select :value="data?.site[b]?.channel ?? ''" :disabled="!!busy" @change="setSite(b, 'channel', val($event))">
                <option value="">{{ t('Non gestito') }}</option>
                <option value="auto">{{ t("Automatico (sceglie l'AP)") }}</option>
                <option v-for="c in CHANNELS[b]" :key="c" :value="String(c)">{{ channelLabel(c) }}</option>
              </select>
            </label>
            <label>{{ t('Larghezza') }}
              <select :value="data?.site[b]?.width ?? ''" :disabled="!!busy" @change="setSite(b, 'width', val($event))">
                <option value="">{{ t('Non gestita') }}</option>
                <option v-for="w in WIDTHS[b]" :key="w" :value="w">{{ widthLabel(w) }}</option>
              </select>
            </label>
          </div>
          <span class="small muted">
            {{ t('Limite di legge in Italia: {v};', { v: b === '2.4GHz' ? '20 dBm' : t('23 dBm sui canali 36-48, 30 dBm sui canali 100-140 (DFS)') }) }}
            {{ t("l'AP non supera mai il massimo consentito. Meno potenza = celle più piccole, meno “rimbalzi” fra AP vicini.") }}
          </span>
        </div>
      </div>
    </section>

    <SiteSettings @results="r => { results = r; refreshSoon() }" />

    <!-- per AP -->
    <section class="card">
      <h2 class="mb">{{ t('Per access point') }}</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th /><th>Access point</th><th v-for="b in BANDS" :key="b">{{ bandLabel(b) }}</th></tr></thead>
          <tbody>
            <tr v-for="a in configurable" :key="a.id">
              <td><Icon name="wifi" :size="16" /></td>
              <td><strong>{{ a.name }}</strong></td>
              <td v-for="b in BANDS" :key="b" class="cfg-cell">
                <div v-for="f in FIELDS" :key="f.key" class="cfg-line">
                  <span class="muted small">{{ t(f.label) }}</span>
                  <select :value="apSelect(a.bands[b].override, f.key)" :disabled="!!busy" @change="setAp(a.id, b, f.key, val($event))">
                    <option value="inherit">{{ t('Come il sito ({v})', { v: siteText(b, f.key) }) }}</option>
                    <option value="none">{{ t('Non gestito') }}</option>
                    <template v-if="f.key === 'tx_power'"><option v-for="p in POWERS" :key="p" :value="String(p)">{{ powerLabel(p) }}</option></template>
                    <template v-else-if="f.key === 'channel'">
                      <option value="auto">{{ t('Automatico') }}</option>
                      <option v-for="c in CHANNELS[b]" :key="c" :value="String(c)">{{ channelLabel(c) }}</option>
                    </template>
                    <template v-else><option v-for="w in WIDTHS[b]" :key="w" :value="w">{{ widthLabel(w) }}</option></template>
                  </select>
                </div>
                <div class="cfg-state">
                  <span class="chip" :style="{ '--tone': STATUS[a.bands[b].status].tone }">{{ t(STATUS[a.bands[b].status].label) }}</span>
                  <span class="muted small">{{ t('potenza reale {v} dBm', { v: a.bands[b].actual ?? '—' }) }}</span>
                </div>
              </td>
            </tr>
            <tr v-for="a in others" :key="a.id" class="disabled">
              <td><Icon name="wifi" :size="16" /></td>
              <td><strong>{{ a.name }}</strong></td>
              <td :colspan="BANDS.length" class="muted small">
                {{ !a.enabled ? t('Disattivato') : t('Letto via SNMP: per configurarlo serve l’accesso SSH (Gestione AP → Connessione)') }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- backup -->
    <section class="card">
      <div class="section-head">
        <h2>{{ t('Backup delle configurazioni') }}</h2>
        <button :disabled="!!busy || !configurable.length" @click="backupAll">{{ busy === 'backup' ? t('Salvo…') : t('Salva backup di tutti') }}</button>
      </div>
      <p class="muted small mb">
        {{ t('Copia completa della configurazione di ogni AP.') }} <strong>{{ t('Da fare prima di ogni modifica importante e prima di scollegare Nebula') }}</strong>{{ t(': è ciò che permette di ricostruire la rete se un AP si resetta.') }}
      </p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>{{ t('Quando') }}</th><th>Access point</th><th>{{ t('Dimensione') }}</th><th /></tr></thead>
          <tbody>
            <template v-for="b in backups" :key="b.id">
              <tr>
                <td class="small">{{ time(b.ts) }}</td>
                <td><strong>{{ b.ap }}</strong></td>
                <td class="small">{{ (b.size / 1024).toFixed(1) }} KB</td>
                <td class="row-actions"><button class="ghost small" @click="showBackup(b)">{{ shown?.id === b.id ? t('Chiudi') : t('Vedi') }}</button></td>
              </tr>
              <tr v-if="shown?.id === b.id" class="edit-row">
                <td colspan="4">
                  <div class="actions"><span class="grow" />
                    <button class="ghost small" @click="copyBackup">{{ copied ? t('Copiato ✓') : t('Copia') }}</button>
                    <button class="ghost small" @click="download">{{ t('Scarica') }}</button>
                  </div>
                  <pre class="raw">{{ shown.text }}</pre>
                </td>
              </tr>
            </template>
            <tr v-if="!backups.length"><td colspan="4" class="muted">{{ t('Nessun backup: salvane uno adesso.') }}</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  </main>
</template>
