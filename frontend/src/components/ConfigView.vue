<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, type Backup, type PolicyOverview, type PolicyResult } from '../api'
import { copyText, time } from '../format'
import Icon from './Icon.vue'

/** Configurazione centralizzata: il profilo del sito vale per tutti, ogni AP può personalizzare. */
const emit = defineEmits<{ changed: [] }>()

const BANDS = ['2.4GHz', '5GHz'] as const
type Band = typeof BANDS[number]
const POWERS = [30, 27, 24, 21, 20, 18, 17, 15, 12, 10, 8, 6, 3]

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

function setSite(band: Band, value: string) {
  run(`site-${band}`, () => api.setSitePolicy(band, value === '' ? null : Number(value)))
}
function setAp(apId: number, band: Band, value: string) {
  const inherit = value === 'inherit'
  run(`ap-${apId}-${band}`, () => api.setApPolicy(apId, band, inherit || value === 'none' ? null : Number(value), inherit))
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
        <h2>Configurazione centralizzata</h2>
        <p class="muted small">
          Il <strong>profilo del sito</strong> vale per tutti gli access point; ogni AP può avere un valore suo.
          Le modifiche si applicano subito via SSH e il sistema le <strong>mantiene</strong>: se un AP torna indietro
          (riavvio o sincronizzazione di Nebula) viene riallineato da solo.
        </p>
      </div>
      <button class="primary" :disabled="!!busy || !configurable.length" @click="applyAll">{{ busy === 'apply' ? 'Applico…' : 'Applica ora a tutti' }}</button>
    </section>

    <p v-if="error" class="note ko">{{ error }}</p>
    <div v-if="results.length" class="card cfg-results">
      <div v-for="r in results" :key="r.ap" class="cfg-result" :class="r.ok ? 'ok' : 'ko'">
        <span class="status" :class="r.ok ? 'on' : 'off'" /><strong>{{ r.ap }}</strong><span class="muted small">{{ r.message }}</span>
      </div>
    </div>

    <!-- profilo del sito -->
    <section class="card">
      <h2 class="mb">Profilo del sito <span class="muted small">(vale per tutti gli AP)</span></h2>
      <div class="cfg-bands">
        <div v-for="b in BANDS" :key="b" class="cfg-band radio" :class="bandClass(b)">
          <b>{{ bandLabel(b) }}</b>
          <label>Potenza di trasmissione
            <select :value="data?.site[b] ?? ''" :disabled="!!busy" @change="setSite(b, ($event.target as HTMLSelectElement).value)">
              <option value="">Non gestita (decide l'AP / Nebula)</option>
              <option v-for="p in POWERS" :key="p" :value="p">{{ p === 30 ? 'Massima consentita' : `${p} dBm` }}</option>
            </select>
          </label>
          <span class="small muted">
            Limite di legge in Italia: {{ b === '2.4GHz' ? '20 dBm' : '23 dBm sui canali 36-48, 30 dBm sui canali 100-140 (DFS)' }};
            l'AP non supera mai il massimo consentito. Meno potenza = celle più piccole, meno “rimbalzi” fra AP vicini.
          </span>
        </div>
      </div>
    </section>

    <!-- per AP -->
    <section class="card">
      <h2 class="mb">Per access point</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th /><th>Access point</th><th v-for="b in BANDS" :key="b">{{ bandLabel(b) }}</th></tr></thead>
          <tbody>
            <tr v-for="a in configurable" :key="a.id">
              <td><Icon name="wifi" :size="16" /></td>
              <td><strong>{{ a.name }}</strong></td>
              <td v-for="b in BANDS" :key="b" class="cfg-cell">
                <select :value="a.bands[b].override === 'inherit' ? 'inherit' : a.bands[b].override ?? 'none'" :disabled="!!busy"
                        @change="setAp(a.id, b, ($event.target as HTMLSelectElement).value)">
                  <option value="inherit">Come il sito{{ data?.site[b] != null ? ` (${data.site[b] === 30 ? 'massima' : `${data.site[b]} dBm`})` : '' }}</option>
                  <option value="none">Non gestita</option>
                  <option v-for="p in POWERS" :key="p" :value="p">{{ p === 30 ? 'Massima consentita' : `${p} dBm` }}</option>
                </select>
                <div class="cfg-state">
                  <span class="chip" :style="{ '--tone': STATUS[a.bands[b].status].tone }">{{ STATUS[a.bands[b].status].label }}</span>
                  <span class="muted small">reale {{ a.bands[b].actual ?? '—' }} dBm</span>
                </div>
              </td>
            </tr>
            <tr v-for="a in others" :key="a.id" class="disabled">
              <td><Icon name="wifi" :size="16" /></td>
              <td><strong>{{ a.name }}</strong></td>
              <td :colspan="BANDS.length" class="muted small">
                {{ !a.enabled ? 'Disattivato' : 'Letto via SNMP: per configurarlo serve l’accesso SSH (Gestione AP → Connessione)' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- backup -->
    <section class="card">
      <div class="section-head">
        <h2>Backup delle configurazioni</h2>
        <button :disabled="!!busy || !configurable.length" @click="backupAll">{{ busy === 'backup' ? 'Salvo…' : 'Salva backup di tutti' }}</button>
      </div>
      <p class="muted small mb">
        Copia completa della configurazione di ogni AP. <strong>Da fare prima di ogni modifica importante
        e prima di scollegare Nebula</strong>: è ciò che permette di ricostruire la rete se un AP si resetta.
      </p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Quando</th><th>Access point</th><th>Dimensione</th><th /></tr></thead>
          <tbody>
            <template v-for="b in backups" :key="b.id">
              <tr>
                <td class="small">{{ time(b.ts) }}</td>
                <td><strong>{{ b.ap }}</strong></td>
                <td class="small">{{ (b.size / 1024).toFixed(1) }} KB</td>
                <td class="row-actions"><button class="ghost small" @click="showBackup(b)">{{ shown?.id === b.id ? 'Chiudi' : 'Vedi' }}</button></td>
              </tr>
              <tr v-if="shown?.id === b.id" class="edit-row">
                <td colspan="4">
                  <div class="actions"><span class="grow" />
                    <button class="ghost small" @click="copyBackup">{{ copied ? 'Copiato ✓' : 'Copia' }}</button>
                    <button class="ghost small" @click="download">Scarica</button>
                  </div>
                  <pre class="raw">{{ shown.text }}</pre>
                </td>
              </tr>
            </template>
            <tr v-if="!backups.length"><td colspan="4" class="muted">Nessun backup: salvane uno adesso.</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  </main>
</template>
