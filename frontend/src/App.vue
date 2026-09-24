<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  api, auth, Unauthorized, type Ap, type Client, type Event, type Health, type Internet, type Sites, type Traffic, type TrafficPoint, type Usage,
} from './api'
import BarList from './components/BarList.vue'
import ClientsTable from './components/ClientsTable.vue'
import EventsTable from './components/EventsTable.vue'
import LoginView from './components/LoginView.vue'
import PieChart from './components/PieChart.vue'
import SettingsView from './components/SettingsView.vue'
import TrafficChart from './components/TrafficChart.vue'
import { bps, bytes, duration } from './format'

const REFRESH_MS = 30_000

const health = ref<Health | null>(null)
const logged = ref(!!auth.token)
const defaultPassword = ref(false)
/** '' = panoramica generale, '#events' = eventi, '#settings' = impostazioni, altrimenti nome dell'AP */
const view = ref('')

const aps = ref<Ap[]>([])
const clients = ref<Client[]>([])
const events = ref<Event[]>([])
const traffic = ref<Traffic | null>(null)
const usage = ref<Usage | null>(null)
const sites = ref<Sites | null>(null)
const internet = ref<Internet | null>(null)
const hours = ref(6)
const metric = ref<'down_bps' | 'up_bps' | 'clients'>('down_bps')
const loadError = ref('')
const lastUpdate = ref<Date | null>(null)

let timer: number | undefined

async function load() {
  try {
    const [a, c, e, t, u] = await Promise.all([
      api.aps(), api.clients(), api.events(300), api.traffic(hours.value), api.usage(hours.value),
    ])
    aps.value = a; clients.value = c; events.value = e; traffic.value = t; usage.value = u
    await loadSites()
    internet.value = await api.internet(hours.value).catch(() => internet.value)
    loadError.value = ''
    lastUpdate.value = new Date()
  } catch (err) {
    if (err instanceof Unauthorized) logged.value = false
    else loadError.value = (err as Error).message
  }
}

async function afterLogin() {
  logged.value = true
  try { defaultPassword.value = (await api.me()).default_password } catch { /* gestito da load */ }
  await load()
}

function logout() { auth.clear(); logged.value = false }

/** dopo una modifica nel pannello: subito, e di nuovo quando la lettura ripartita è finita */
function reloadSoon() {
  load()
  window.setTimeout(load, 8000)
}

async function loadSites() {
  const ap = aps.value.some(a => a.ap === view.value) ? view.value : undefined
  sites.value = await api.sites(hours.value, ap).catch(() => sites.value)
}

watch(hours, load)
watch(view, loadSites)

onMounted(async () => {
  health.value = await api.health().catch(() => null)
  if (logged.value) await afterLogin()
  timer = window.setInterval(() => logged.value && load(), REFRESH_MS)
})
onBeforeUnmount(() => clearInterval(timer))

// ---- vista corrente: tutto o un solo AP ----
const currentAp = computed(() => aps.value.find(a => a.ap === view.value) ?? null)
const scopedClients = computed(() =>
  currentAp.value ? clients.value.filter(c => c.ap === currentAp.value!.ap) : clients.value)
const scopedEvents = computed(() =>
  currentAp.value ? events.value.filter(e => e.ap === currentAp.value!.ap) : events.value)
const scopedSeries = computed(() => {
  const s = traffic.value?.series ?? {}
  return currentAp.value ? (s[currentAp.value.ap] ? { [currentAp.value.ap]: s[currentAp.value.ap] } : {}) : s
})
const hasTraffic = computed(() =>
  Object.values(scopedSeries.value).some(pts => pts.some(p => p.down_bps != null)))

// ---- KPI ----
const onlineAps = computed(() => aps.value.filter(a => a.online).length)
const weakClients = computed(() => scopedClients.value.filter(c => c.rssi_dbm != null && c.rssi_dbm < -75).length)
function lastPoint(k: 'down_bps' | 'up_bps'): number | null {
  let sum = 0, found = false
  for (const pts of Object.values(scopedSeries.value)) {
    const p = [...pts].reverse().find(x => x[k] != null)
    if (p) { sum += p[k]!; found = true }
  }
  return found ? sum : null
}
const currentDown = computed(() => lastPoint('down_bps'))
const currentUp = computed(() => lastPoint('up_bps'))
const periodBytes = computed(() => {
  const per = usage.value?.per_ap ?? {}
  const keys = currentAp.value ? [currentAp.value.ap] : Object.keys(per)
  return keys.reduce((s, k) => s + (per[k] ? per[k].down + per[k].up : 0), 0)
})

// ---- torte ----
function countBy(list: Client[], key: (c: Client) => string) {
  const m = new Map<string, number>()
  for (const c of list) m.set(key(c), (m.get(key(c)) ?? 0) + 1)
  return [...m].map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value)
}
const byType = computed(() => countBy(scopedClients.value, c => c.device_type))
const byBand = computed(() => countBy(scopedClients.value, c => c.band || '?'))
const byAp = computed(() => countBy(clients.value, c => c.ap))
const gbByAp = computed(() =>
  Object.entries(usage.value?.per_ap ?? {})
    .map(([label, v]) => ({ label, value: v.down + v.up }))
    .filter(i => i.value > 0)
    .sort((a, b) => b.value - a.value))

const gateway = computed(() => internet.value?.gateways[0] ?? null)
const internetSeries = computed(() => {
  const out: Record<string, TrafficPoint[]> = {}
  if (internet.value?.available) out.Internet = internet.value.series
  return out
})
const internetNow = computed(() => {
  const p = [...(internet.value?.series ?? [])].reverse().find(x => x.down_bps != null)
  return p ?? null
})
const blockedItems = computed(() =>
  (internet.value?.dns?.top_blocked ?? []).map(i => ({ label: i.domain, value: i.queries, title: i.list })))

const siteItems = computed(() => (sites.value?.items ?? []).map(i => ({ label: i.site, value: i.queries })))

const periodLabel = computed(() => ({ 1: 'ultima ora', 6: 'ultime 6 ore', 24: 'ultime 24 ore', 168: 'ultimi 7 giorni' } as Record<number, string>)[hours.value])

async function rename(c: Client) {
  const name = window.prompt(`Nome per ${c.mac}`, c.alias || c.hostname || '')
  if (name === null) return
  await api.setAlias(c.mac, name)
  await load()
}

// ---- cambio password ----
const showPwd = ref(false)
const pwdOld = ref(''), pwdNew = ref(''), pwdMsg = ref('')
async function changePassword() {
  pwdMsg.value = ''
  try {
    await api.changePassword(pwdOld.value, pwdNew.value)
    defaultPassword.value = false
    showPwd.value = false
    pwdOld.value = pwdNew.value = ''
  } catch (e) { pwdMsg.value = (e as Error).message }
}
</script>

<template>
  <LoginView v-if="!logged" @done="afterLogin" />

  <div v-else class="shell">
    <header class="topbar">
      <div class="brand"><span class="dot" />Zyxel Monitor</div>
      <nav class="tabs">
        <button :class="{ active: view === '' }" @click="view = ''">Panoramica <span class="pill">{{ clients.length }}</span></button>
        <button v-for="a in aps" :key="a.ap" :class="{ active: view === a.ap }" @click="view = a.ap">
          <span class="status" :class="a.online ? 'on' : 'off'" /> {{ a.ap }} <span class="pill">{{ a.clients ?? 0 }}</span>
        </button>
        <button :class="{ active: view === '#events' }" @click="view = '#events'">Eventi</button>
      </nav>
      <div class="top-actions">
        <select v-model.number="hours" title="Periodo">
          <option :value="1">1 ora</option><option :value="6">6 ore</option>
          <option :value="24">24 ore</option><option :value="168">7 giorni</option>
        </select>
        <span class="muted small" v-if="lastUpdate">agg. {{ lastUpdate.toLocaleTimeString('it-IT') }}</span>
        <button class="ghost" :class="{ active: view === '#settings' }" @click="view = '#settings'">Impostazioni</button>
        <button class="ghost" @click="showPwd = !showPwd">Password</button>
        <button class="ghost" @click="logout">Esci</button>
      </div>
    </header>

    <div v-if="defaultPassword" class="banner warn">
      Stai usando la password predefinita. <a href="#" @click.prevent="showPwd = true">Cambiala adesso</a>.
    </div>
    <div v-if="loadError" class="banner err">Errore di caricamento: {{ loadError }}</div>

    <form v-if="showPwd" class="card pwd" @submit.prevent="changePassword">
      <label>Password attuale<input v-model="pwdOld" type="password" required /></label>
      <label>Nuova password (min. 10 caratteri)<input v-model="pwdNew" type="password" minlength="10" required /></label>
      <button class="primary">Salva</button>
      <span v-if="pwdMsg" class="error">{{ pwdMsg }}</span>
    </form>

    <!-- IMPOSTAZIONI -->
    <SettingsView v-if="view === '#settings'" :status="aps" @changed="reloadSoon" />

    <!-- EVENTI (tutti) -->
    <main v-else-if="view === '#events'">
      <section class="card"><h2 class="mb">Storico collegamenti</h2><EventsTable :events="events" show-ap /></section>
    </main>

    <!-- PANORAMICA GENERALE o DETTAGLIO AP -->
    <main v-else>
      <section v-if="currentAp" class="card ap-head" :class="{ off: !currentAp.online }">
        <div>
          <h2>{{ currentAp.ap }}</h2>
          <p class="muted small">
            {{ currentAp.model || '—' }} · {{ currentAp.host }} · firmware {{ currentAp.firmware || '—' }} ·
            lettura {{ currentAp.method.toUpperCase() }}
          </p>
          <p v-if="currentAp.error" class="error small">{{ currentAp.error }}</p>
        </div>
        <div class="radios">
          <span v-for="r in currentAp.radios" :key="r.band" class="radio">
            {{ r.band }}<template v-if="r.channel"> · canale {{ r.channel }}</template> · {{ r.clients }} client
          </span>
        </div>
      </section>

      <section class="kpis">
        <div class="kpi" v-if="!currentAp"><span>Access point online</span><strong>{{ onlineAps }}<small> / {{ aps.length }}</small></strong></div>
        <div class="kpi" v-else><span>Uptime</span><strong>{{ duration(currentAp.uptime_s) }}</strong></div>
        <div class="kpi"><span>Client connessi</span><strong>{{ scopedClients.length }}</strong></div>
        <div class="kpi"><span>Download Wi-Fi</span><strong>{{ bps(currentDown) }}</strong></div>
        <div class="kpi"><span>Upload Wi-Fi</span><strong>{{ bps(currentUp) }}</strong></div>
        <div class="kpi"><span>Traffico {{ periodLabel }}</span><strong>{{ periodBytes ? bytes(periodBytes) : '—' }}</strong></div>
        <div class="kpi"><span>Segnale debole</span><strong :class="{ warn: weakClients }">{{ weakClients }}</strong></div>
      </section>

      <section v-if="!currentAp" class="ap-grid">
        <article v-for="a in aps" :key="a.ap" class="card ap clickable" :class="{ off: !a.online }" @click="view = a.ap">
          <header>
            <span class="status" :class="a.online ? 'on' : 'off'" />
            <h3>{{ a.ap }}</h3>
            <span class="tag">{{ a.method.toUpperCase() }}</span>
          </header>
          <p class="muted small">{{ a.model || '—' }} · {{ a.host }}</p>
          <div class="ap-stats">
            <div><span>Client</span><strong>{{ a.clients ?? '—' }}</strong></div>
            <div><span>Uptime</span><strong>{{ duration(a.uptime_s) }}</strong></div>
            <div><span>Traffico</span><strong>{{ usage?.per_ap[a.ap] ? bytes(usage.per_ap[a.ap].down + usage.per_ap[a.ap].up) : '—' }}</strong></div>
          </div>
          <div class="radios">
            <span v-for="r in a.radios" :key="r.band" class="radio">
              {{ r.band }}<template v-if="r.channel"> · ch {{ r.channel }}</template> · {{ r.clients }}
            </span>
          </div>
          <p v-if="a.error" class="error small">{{ a.error }}</p>
        </article>
        <p v-if="!aps.length" class="muted">In attesa della prima lettura degli access point…</p>
      </section>

      <section v-if="!currentAp && internet?.available" class="card internet">
        <div class="section-head">
          <h2>Internet <span class="muted small">{{ gateway?.name }}</span></h2>
          <span v-if="gateway" class="badge" :class="gateway.online ? 'ok' : 'ko'">{{ gateway.online ? 'Online' : gateway.status }}</span>
        </div>
        <div class="kpis inner">
          <div class="kpi"><span>Latenza</span><strong>{{ gateway?.delay || '—' }}</strong></div>
          <div class="kpi"><span>Pacchetti persi</span><strong>{{ gateway?.loss || '—' }}</strong></div>
          <div class="kpi"><span>Download ora</span><strong>{{ bps(internetNow?.down_bps) }}</strong></div>
          <div class="kpi"><span>Upload ora</span><strong>{{ bps(internetNow?.up_bps) }}</strong></div>
          <div class="kpi"><span>Scaricati {{ periodLabel }}</span><strong>{{ bytes(internet.period.down) }}</strong></div>
          <div class="kpi"><span>Inviati {{ periodLabel }}</span><strong>{{ bytes(internet.period.up) }}</strong></div>
        </div>
        <TrafficChart v-if="internet.series.some(p => p.down_bps != null)" :series="internetSeries" :metric="metric === 'up_bps' ? 'up_bps' : 'down_bps'" />
        <p v-else class="muted small">Il grafico della linea si popola dopo qualche minuto.</p>
      </section>

      <section class="pies">
        <div class="card">
          <h2>Siti più visitati <span class="muted small">({{ periodLabel }}, richieste DNS)</span></h2>
          <BarList v-if="siteItems.length" :items="siteItems" />
          <p v-else-if="sites?.available" class="muted">Nessuna richiesta nel periodo per questi dispositivi.</p>
          <div v-else class="empty">
            <p>Gli access point non vedono i siti visitati: questo dato arriva dal <strong>DNS della rete</strong>.</p>
            <p class="muted small">Collega OPNsense in <a href="#" @click.prevent="view = '#settings'">Impostazioni</a>: i dati arrivano entro un minuto.</p>
          </div>
        </div>
        <div class="card">
          <h2>Dispositivi per tipologia</h2>
          <PieChart v-if="byType.length" :items="byType" />
          <p v-else class="muted">Nessun client.</p>
        </div>
        <div class="card" v-if="!currentAp">
          <h2>Traffico per access point <span class="muted small">({{ periodLabel }})</span></h2>
          <PieChart v-if="gbByAp.length" :items="gbByAp" :format="bytes" />
          <p v-else class="muted">Dati in raccolta: servono alcuni minuti. Gli AP letti via SSH non forniscono il traffico.</p>
        </div>
        <div class="card" v-if="!currentAp && internet?.dns">
          <h2>Pubblicità e tracker bloccati</h2>
          <div class="blocked-head">
            <strong>{{ internet.dns.blocked_pct.toLocaleString('it-IT', { maximumFractionDigits: 1 }) }}%</strong>
            <span class="muted small">
              delle richieste DNS: {{ internet.dns.blocked.toLocaleString('it-IT') }} su
              {{ internet.dns.total.toLocaleString('it-IT') }} dal {{ new Date(internet.dns.since * 1000).toLocaleDateString('it-IT') }}
            </span>
          </div>
          <BarList v-if="blockedItems.length" :items="blockedItems" />
          <p v-else class="muted">Nessun dominio bloccato finora.</p>
        </div>
        <div class="card" v-if="!currentAp">
          <h2>Client per access point</h2>
          <PieChart v-if="byAp.length" :items="byAp" />
        </div>
        <div class="card" v-if="currentAp">
          <h2>Client per banda</h2>
          <PieChart v-if="byBand.length" :items="byBand" />
          <p v-else class="muted">Nessun client.</p>
        </div>
      </section>

      <section class="card">
        <div class="section-head">
          <h2>Andamento <span class="muted small">({{ periodLabel }})</span></h2>
          <div class="seg">
            <button :class="{ active: metric === 'down_bps' }" @click="metric = 'down_bps'">Download</button>
            <button :class="{ active: metric === 'up_bps' }" @click="metric = 'up_bps'">Upload</button>
            <button :class="{ active: metric === 'clients' }" @click="metric = 'clients'">Client</button>
          </div>
        </div>
        <TrafficChart v-if="Object.keys(scopedSeries).length" :series="scopedSeries" :metric="metric" />
        <p v-else class="muted">I grafici si popolano dopo qualche minuto di raccolta.</p>
        <p v-if="metric !== 'clients' && !hasTraffic && currentAp?.method === 'ssh'" class="muted small">
          Questo AP è letto via SSH: il traffico non è disponibile, guarda il grafico "Client".
        </p>
      </section>

      <section class="card">
        <h2 class="mb">{{ currentAp ? `Client connessi a ${currentAp.ap}` : 'Tutti i client connessi' }}</h2>
        <p class="muted small mb">Clicca un dispositivo per vedere i siti che contatta.</p>
        <ClientsTable :clients="scopedClients" :show-ap="!currentAp" :hours="hours" @rename="rename" />
      </section>

      <section v-if="currentAp" class="card">
        <h2 class="mb">Chi si è collegato a {{ currentAp.ap }}</h2>
        <EventsTable :events="scopedEvents" />
      </section>
    </main>
  </div>

  <footer class="footer" v-if="health">v{{ health.version }} — Ideato e sviluppato da {{ health.author }}</footer>
</template>
