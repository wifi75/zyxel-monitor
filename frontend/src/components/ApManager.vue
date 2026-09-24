<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { api, apForm, type Ap, type ApConfig, type ApTest } from '../api'
import { duration } from '../format'
import ApEditor from './ApEditor.vue'
import Icon from './Icon.vue'

/** Pagina di gestione degli access point: elenco a sinistra, scheda dell'AP scelto a destra. */
const props = defineProps<{ status: Ap[] }>()
const emit = defineEmits<{ changed: [] }>()

const list = ref<ApConfig[]>([])
const selected = ref<number | 'new' | null>(null)
const tab = ref<'summary' | 'connection' | 'tools'>('summary')
const error = ref('')
const notice = ref('')
const busy = ref('')
const test = ref<ApTest | null>(null)
const raw = ref<{ ts: number | null; text: string } | null>(null)
const copied = ref(false)

async function load() {
  try {
    list.value = await api.apConfigs()
    if (selected.value === null && list.value.length) selected.value = list.value[0].id
  } catch (e) { error.value = (e as Error).message }
}
onMounted(load)

const current = computed(() => typeof selected.value === 'number' ? list.value.find(a => a.id === selected.value) ?? null : null)
const live = computed(() => current.value ? props.status.find(s => s.ap === current.value!.name) ?? null : null)
const statusOf = (a: ApConfig) => props.status.find(s => s.ap === a.name) ?? null

watch(selected, () => { test.value = null; raw.value = null; notice.value = ''; error.value = '' })

function select(id: number | 'new') {
  selected.value = id
  tab.value = id === 'new' ? 'connection' : 'summary'
}

const protocol = (a: ApConfig) => a.method === 'ssh' ? 'SSH' : `SNMP v${a.snmp_version}`
const bandLabel = (b: string) => b.replace('GHz', ' GHz')
const bandClass = (b: string) => (b.startsWith('2') ? 'b24' : b.startsWith('5') ? 'b5' : b.startsWith('6') ? 'b6' : '')

async function run(kind: string, fn: () => Promise<void>) {
  busy.value = kind; error.value = ''; notice.value = ''
  try { await fn() } catch (e) { error.value = (e as Error).message } finally { busy.value = '' }
}

async function saved(copiedN: number) {
  const wasNew = selected.value === 'new'
  await load()
  if (wasNew) selected.value = list.value[list.value.length - 1]?.id ?? null
  tab.value = 'summary'
  notice.value = copiedN ? `Salvato. Credenziali copiate anche su ${copiedN} AP.` : 'Salvato: la lettura riparte subito.'
  emit('changed')
}

const doTest = () => run('test', async () => {
  const a = current.value!
  test.value = await api.testAp({ ...apForm(a), id: a.id })
})

const doReboot = () => {
  const a = current.value!
  if (!window.confirm(`Riavviare ${a.name}? Resta offline per 2-3 minuti e i suoi client si spostano sugli altri AP.`)) return
  run('reboot', async () => { await api.rebootAp(a.id); notice.value = `Riavvio di ${a.name} inviato: torna online in 2-3 minuti.` })
}

const doRaw = () => run('raw', async () => { raw.value = await api.rawOutput(current.value!.id); copied.value = false })
async function copyRaw() {
  await navigator.clipboard?.writeText(raw.value?.text ?? '').catch(() => {})
  copied.value = true
}

const doToggle = () => run('toggle', async () => {
  const a = current.value!
  await api.updateAp(a.id, { ...apForm(a), enabled: !a.enabled })
  await load(); emit('changed')
})

const doDelete = () => {
  const a = current.value!
  if (!window.confirm(`Eliminare ${a.name}? Scompare dalla dashboard; lo storico resta fino alla scadenza.`)) return
  run('delete', async () => {
    await api.deleteAp(a.id)
    selected.value = null
    await load(); emit('changed')
  })
}
</script>

<template>
  <main class="apm">
    <!-- elenco -->
    <aside class="card apm-list">
      <div class="section-head">
        <h2>Access point</h2>
        <button class="primary small" @click="select('new')">+ Aggiungi</button>
      </div>
      <button v-for="a in list" :key="a.id" class="apm-item" :class="{ active: selected === a.id, disabled: !a.enabled }" @click="select(a.id)">
        <span class="status" :class="!a.enabled ? 'idle' : statusOf(a)?.online ? 'on' : 'off'" />
        <span class="grow">
          <strong>{{ a.name }}</strong>
          <span class="muted small">{{ statusOf(a)?.model || '—' }} · <span class="mono">{{ a.host }}</span></span>
        </span>
        <span class="tag" :class="a.method">{{ a.method.toUpperCase() }}</span>
      </button>
      <p v-if="!list.length" class="muted small">Nessun access point: aggiungine uno.</p>
    </aside>

    <!-- scheda -->
    <section class="card apm-detail">
      <template v-if="selected === 'new'">
        <div class="apm-hero">
          <div class="apm-hero-icon"><Icon name="wifi" :size="22" /></div>
          <div class="grow"><h2>Nuovo access point</h2><p class="muted small">Indirizzo e credenziali: “Rileva protocollo” sceglie da solo tra SNMP e SSH.</p></div>
        </div>
        <ApEditor :ap="null" :all="list" @saved="saved" @cancel="select(list[0]?.id ?? 'new')" />
      </template>

      <template v-else-if="current">
        <div class="apm-hero" :class="{ off: current.enabled && !live?.online }">
          <div class="apm-hero-icon"><Icon name="wifi" :size="22" /></div>
          <div class="grow">
            <h2>{{ current.name }}</h2>
            <p class="muted small">{{ live?.model || 'modello non letto' }} · <span class="mono">{{ current.host }}</span> · {{ protocol(current) }}</p>
          </div>
          <span class="badge" :class="!current.enabled ? '' : live?.online ? 'ok' : 'ko'">
            {{ !current.enabled ? 'disattivato' : live?.online ? 'online' : 'offline' }}
          </span>
        </div>

        <nav class="seg apm-tabs">
          <button :class="{ active: tab === 'summary' }" @click="tab = 'summary'">Riepilogo</button>
          <button :class="{ active: tab === 'connection' }" @click="tab = 'connection'">Connessione</button>
          <button :class="{ active: tab === 'tools' }" @click="tab = 'tools'">Strumenti</button>
        </nav>

        <!-- riepilogo -->
        <div v-if="tab === 'summary'" class="apm-body">
          <div class="apm-facts">
            <div class="tile tone-blue"><Icon name="clock" :size="16" /><span>Acceso da</span><strong>{{ duration(live?.uptime_s) }}</strong></div>
            <div class="tile tone-violet"><Icon name="users" :size="16" /><span>Client</span><strong>{{ live?.clients ?? '—' }}</strong></div>
            <div class="tile tone-teal"><Icon name="sliders" :size="16" /><span>Firmware</span><strong class="mono small-num">{{ live?.firmware || '—' }}</strong></div>
          </div>
          <h3 class="small sub">Radio</h3>
          <div class="apm-radios">
            <div v-for="r in live?.radios ?? []" :key="r.band" class="apm-radio radio" :class="bandClass(r.band)">
              <b>{{ bandLabel(r.band) }}</b>
              <dl>
                <div><dt>Canale</dt><dd>{{ r.channel ?? '—' }}</dd></div>
                <div><dt>Potenza</dt><dd>{{ r.tx_power != null ? `${r.tx_power} dBm` : '—' }}</dd></div>
                <div><dt>Canale occupato</dt><dd>{{ r.utilization != null ? `${r.utilization}%` : '—' }}</dd></div>
                <div><dt>Client</dt><dd>{{ r.clients }}</dd></div>
              </dl>
            </div>
            <p v-if="!live?.radios.length" class="muted small">Nessun dato radio: l'AP non è ancora stato letto.</p>
          </div>
          <p v-if="live?.error" class="note ko">{{ live.error }}</p>
        </div>

        <!-- connessione -->
        <div v-else-if="tab === 'connection'" class="apm-body">
          <ApEditor :key="current.id" :ap="current" :all="list" @saved="saved" @cancel="tab = 'summary'" />
        </div>

        <!-- strumenti -->
        <div v-else class="apm-body apm-tools">
          <div class="apm-tool">
            <div class="grow"><strong>Prova connessione</strong><p class="muted small">Una lettura immediata con le credenziali salvate.</p></div>
            <button :disabled="!!busy || !current.enabled" @click="doTest">{{ busy === 'test' ? 'Provo…' : 'Prova' }}</button>
          </div>
          <div v-if="test" class="note" :class="test.online ? 'ok' : 'ko'">
            <template v-if="test.online"><strong>Connesso</strong> in {{ test.ms }} ms · {{ test.model || '—' }} · {{ test.clients }} client</template>
            <template v-else><strong>Non risponde:</strong> {{ test.error }}<p v-if="test.hint" class="muted">{{ test.hint }}</p></template>
          </div>

          <div class="apm-tool">
            <div class="grow"><strong>Riavvia</strong><p class="muted small">Via SSH, non tocca la configurazione: resta offline 2-3 minuti.</p></div>
            <button class="danger" :disabled="!!busy || current.method !== 'ssh' || !current.enabled" :title="current.method !== 'ssh' ? 'Disponibile solo per gli AP letti via SSH' : ''" @click="doReboot">
              {{ busy === 'reboot' ? 'Invio…' : 'Riavvia' }}
            </button>
          </div>

          <div v-if="current.method === 'ssh'" class="apm-tool">
            <div class="grow"><strong>Output CLI</strong><p class="muted small">Il testo grezzo dell'ultima lettura, utile se un dato manca.</p></div>
            <button :disabled="!!busy" @click="doRaw">Mostra</button>
          </div>
          <template v-if="raw">
            <div class="actions"><span class="muted small grow">{{ raw.ts ? `letto alle ${new Date(raw.ts * 1000).toLocaleTimeString('it-IT')}` : '' }}</span>
              <button class="ghost small" @click="copyRaw">{{ copied ? 'Copiato' : 'Copia' }}</button>
              <button class="ghost small" @click="raw = null">Chiudi</button></div>
            <pre class="raw">{{ raw.text || 'Nessuna lettura riuscita finora.' }}</pre>
          </template>

          <div class="apm-tool">
            <div class="grow"><strong>{{ current.enabled ? 'Disattiva' : 'Attiva' }}</strong><p class="muted small">Un AP disattivato non viene letto e sparisce dalla dashboard.</p></div>
            <button :disabled="!!busy" @click="doToggle">{{ current.enabled ? 'Disattiva' : 'Attiva' }}</button>
          </div>
          <div class="apm-tool danger-zone">
            <div class="grow"><strong>Elimina</strong><p class="muted small">Toglie l'AP dall'elenco; lo storico resta fino alla scadenza.</p></div>
            <button class="danger" :disabled="!!busy" @click="doDelete">Elimina</button>
          </div>
        </div>
      </template>

      <p v-else class="muted">Scegli un access point dall'elenco.</p>
      <p v-if="notice" class="note ok">{{ notice }}</p>
      <p v-if="error" class="note ko">{{ error }}</p>
    </section>
  </main>
</template>
