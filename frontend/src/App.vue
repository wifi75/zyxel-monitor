<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  api, auth, Unauthorized, type Ap, type Client, type Device, type DeviceUsage, type Event, type Health,
  type Internet, type Roaming, type SignalByAp, type Sites, type Traffic, type Usage,
} from './api'
import ApManager from './components/ApManager.vue'
import BarList from './components/BarList.vue'
import ClientsTable from './components/ClientsTable.vue'
import Dashboard from './components/Dashboard.vue'
import DevicesView from './components/DevicesView.vue'
import EventsTable from './components/EventsTable.vue'
import Icon from './components/Icon.vue'
import InternetCard from './components/InternetCard.vue'
import LoginView from './components/LoginView.vue'
import PieChart from './components/PieChart.vue'
import SettingsView from './components/SettingsView.vue'
import TrafficChart from './components/TrafficChart.vue'
import { bps, bytes, copyText, duration, signal, time } from './format'
import type { IconName } from './icons'

const REFRESH_MS = 30_000

const health = ref<Health | null>(null)
const logged = ref(!!auth.token)
const defaultPassword = ref(false)
/** '' = panoramica, '#devices' = dispositivi, '#events' = eventi, '#settings' = impostazioni, altrimenti nome dell'AP */
const view = ref('')
/** modalità "Personalizza dashboard" */
const editing = ref(false)
const isDashboard = computed(() => !view.value.startsWith('#'))

const aps = ref<Ap[]>([])
const clients = ref<Client[]>([])
const events = ref<Event[]>([])
const devices = ref<Device[]>([])
const traffic = ref<Traffic | null>(null)
const usage = ref<Usage | null>(null)
const sites = ref<Sites | null>(null)
const internet = ref<Internet | null>(null)
const signalAps = ref<SignalByAp | null>(null)
const roaming = ref<Roaming | null>(null)
const deviceUsage = ref<DeviceUsage | null>(null)
const hours = ref(6)
const metric = ref<'down_bps' | 'up_bps' | 'clients'>('down_bps')
const loadError = ref('')
const lastUpdate = ref<Date | null>(null)

let timer: number | undefined

async function load() {
  try {
    const [a, c, e, t, u, d] = await Promise.all([
      api.aps(), api.clients(), api.events(300), api.traffic(hours.value), api.usage(hours.value), api.devices(),
    ])
    aps.value = a; clients.value = c; events.value = e; traffic.value = t; usage.value = u; devices.value = d
    await loadScoped()
    internet.value = await api.internet(hours.value).catch(() => internet.value)
    api.usageDevices(hours.value).then(r => { deviceUsage.value = r }).catch(() => {})
    loadError.value = ''
    lastUpdate.value = new Date()
  } catch (err) {
    if (err instanceof Unauthorized) logged.value = false
    else loadError.value = (err as Error).message
  }
}

/** dati che dipendono dall'AP selezionato */
async function loadScoped() {
  const ap = aps.value.some(a => a.ap === view.value) ? view.value : undefined
  const [s, g, r] = await Promise.all([
    api.sites(hours.value, ap).catch(() => sites.value),
    api.signalByAp(hours.value, ap).catch(() => signalAps.value),
    api.roaming(hours.value, ap).catch(() => roaming.value),
  ])
  sites.value = s; signalAps.value = g; roaming.value = r
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

watch(hours, load)
watch(view, () => { if (!isDashboard.value) editing.value = false; loadScoped() })

// ---- aggiornamento automatico: dopo un nuovo deploy la pagina aperta si ricarica da sola ----
const updating = ref(false)
const serverDown = ref(false)
let checkTimer: number | undefined

async function checkUpdate() {
  clearTimeout(checkTimer)
  try {
    const h = await api.health()
    serverDown.value = false
    if (!health.value?.build) health.value = h
    else if (h.build && h.build !== health.value.build && !updating.value) {
      updating.value = true
      window.setTimeout(() => window.location.reload(), 5000)
    }
  } catch {
    serverDown.value = true      // durante un redeploy il server sparisce per qualche decina di secondi
  }
  checkTimer = window.setTimeout(checkUpdate, serverDown.value ? 10_000 : 60_000)
}
const onVisible = () => { if (!document.hidden) checkUpdate() }
const reloadNow = () => window.location.reload()

onMounted(async () => {
  health.value = await api.health().catch(() => null)
  if (logged.value) await afterLogin()
  timer = window.setInterval(() => logged.value && load(), REFRESH_MS)
  checkTimer = window.setTimeout(checkUpdate, 60_000)
  document.addEventListener('visibilitychange', onVisible)
})
onBeforeUnmount(() => {
  clearInterval(timer)
  clearTimeout(checkTimer)
  document.removeEventListener('visibilitychange', onVisible)
})

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
const newDevices = computed(() => devices.value.filter(d => !d.known))
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

const kpis = computed(() => {
  const ap = currentAp.value
  const list: { label: string; value: string | number; of?: number; icon: IconName;
    tone: string; warn?: boolean; go?: string; title?: string }[] = [
    ap
      ? { label: 'Uptime', value: duration(ap.uptime_s), icon: 'clock', tone: 'blue',
          title: ap.method === 'ssh' && ap.uptime_s == null ? SSH_NA : undefined }
      : { label: 'Access point online', value: onlineAps.value, of: aps.value.length, icon: 'wifi', tone: 'blue',
          warn: onlineAps.value < aps.value.length },
    { label: 'Client connessi', value: scopedClients.value.length, icon: 'users', tone: 'violet' },
    { label: 'Download Wi-Fi', value: bps(currentDown.value), icon: 'down', tone: 'green' },
    { label: 'Upload Wi-Fi', value: bps(currentUp.value), icon: 'up', tone: 'teal' },
    { label: `Traffico ${periodLabel.value}`, value: periodBytes.value ? bytes(periodBytes.value) : '—', icon: 'chart', tone: 'amber' },
    { label: 'Segnale debole', value: weakClients.value, icon: 'alert', tone: 'orange', warn: weakClients.value > 0 },
  ]
  if (!ap) list.push({ label: 'Dispositivi nuovi', value: newDevices.value.length, icon: 'star', tone: 'pink',
                       warn: newDevices.value.length > 0, go: '#devices' })
  return list
})

const usageCopied = ref(false)
async function copyUsageDebug() {
  const d = deviceUsage.value?.debug
  if (!d) return
  usageCopied.value = await copyText(`${d.path}\n${d.sample}`)
}

/** classe colore per banda radio */
const bandClass = (band: string) => (band.startsWith('2') ? 'b24' : band.startsWith('5') ? 'b5' : band.startsWith('6') ? 'b6' : '')

// ---- torte e classifiche ----
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
const blockedItems = computed(() =>
  (internet.value?.dns?.top_blocked ?? []).map(i => ({ label: i.domain, value: i.queries, title: i.list })))
const siteItems = computed(() => (sites.value?.items ?? []).map(i => ({ label: i.site, value: i.queries })))
const roamItems = computed(() => (roaming.value?.pairs ?? []).map(p => ({ label: `${p.from} → ${p.to}`, value: p.count })))
const usageItems = computed(() => (deviceUsage.value?.items ?? []).map(i => ({ label: i.name, value: i.bytes, title: i.ip })))
const usageTypes = computed(() => (deviceUsage.value?.by_type ?? []).map(i => ({ label: i.type, value: i.bytes })))

const periodLabel = computed(() => ({ 1: 'ultima ora', 6: 'ultime 6 ore', 24: 'ultime 24 ore', 168: 'ultimi 7 giorni' } as Record<number, string>)[hours.value])

async function rename(c: { mac: string; alias: string | null; hostname: string | null }) {
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

const SSH_NA = "La CLI SSH di questo AP non fornisce ancora il dato: in Impostazioni → Output CLI trovi il testo da mandare per aggiungerlo"
</script>

<template>
  <div v-if="updating" class="update-bar">
    È disponibile una nuova versione: la pagina si aggiorna tra pochi secondi…
    <button class="ghost small" @click="reloadNow">Aggiorna ora</button>
  </div>
  <div v-else-if="serverDown" class="update-bar down">Server non raggiungibile (aggiornamento in corso?): riprovo tra pochi secondi…</div>

  <LoginView v-if="!logged" @done="afterLogin" />

  <div v-else class="shell">
    <header class="topbar">
      <div class="brand"><span class="dot" />Zyxel Monitor</div>
      <nav class="tabs">
        <button :class="{ active: view === '' }" @click="view = ''">Panoramica <span class="pill">{{ clients.length }}</span></button>
        <button v-for="a in aps" :key="a.ap" :class="{ active: view === a.ap }" @click="view = a.ap">
          <span class="status" :class="a.online ? 'on' : 'off'" /> {{ a.ap }} <span class="pill">{{ a.clients ?? 0 }}</span>
        </button>
        <button :class="{ active: view === '#aps' }" @click="view = '#aps'">Gestione AP</button>
        <button :class="{ active: view === '#devices' }" @click="view = '#devices'">
          Dispositivi <span v-if="newDevices.length" class="pill alert" title="Dispositivi nuovi da riconoscere">{{ newDevices.length }}</span>
        </button>
        <button :class="{ active: view === '#events' }" @click="view = '#events'">Eventi</button>
      </nav>
      <div class="top-actions">
        <select v-model.number="hours" title="Periodo">
          <option :value="1">1 ora</option><option :value="6">6 ore</option>
          <option :value="24">24 ore</option><option :value="168">7 giorni</option>
        </select>
        <span class="muted small updated" v-if="lastUpdate" title="Ultimo aggiornamento">{{ lastUpdate.toLocaleTimeString('it-IT') }}</span>
        <button v-if="isDashboard" class="icon-btn" :class="{ active: editing }" title="Personalizza dashboard" @click="editing = !editing"><Icon name="grid" /></button>
        <button class="icon-btn" :class="{ active: view === '#settings' }" title="Impostazioni" @click="view = '#settings'"><Icon name="sliders" /></button>
        <button class="icon-btn" :class="{ active: showPwd }" title="Cambia password" @click="showPwd = !showPwd"><Icon name="key" /></button>
        <button class="icon-btn" title="Esci" @click="logout"><Icon name="logout" /></button>
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

    <SettingsView v-if="view === '#settings'" :status="aps" @changed="reloadSoon" />

    <ApManager v-else-if="view === '#aps'" :status="aps" @changed="reloadSoon" />

    <DevicesView v-else-if="view === '#devices'" :devices="devices" @changed="load" @rename="rename" />

    <main v-else-if="view === '#events'">
      <section class="card"><h2 class="mb">Storico collegamenti</h2><EventsTable :events="events" show-ap /></section>
    </main>

    <!-- PANORAMICA o DETTAGLIO AP: griglia di widget spostabili e ridimensionabili -->
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
          <span v-for="r in currentAp.radios" :key="r.band" class="radio" :class="bandClass(r.band)">
            {{ r.band }}<template v-if="r.channel"> · canale {{ r.channel }}</template> · {{ r.clients }} client
          </span>
        </div>
      </section>

      <Dashboard v-model:editing="editing" :view="currentAp ? 'ap' : 'overview'">
        <template #widget="{ id }">
          <!-- indicatori -->
          <section v-if="id === 'kpis'" class="kpis fill">
            <div v-for="k in kpis" :key="k.label" class="kpi rich" :class="[`tone-${k.tone}`, { clickable: k.go }]"
                 :title="k.title" @click="k.go && (view = k.go)">
              <div class="kpi-icon"><Icon :name="k.icon" /></div>
              <div class="kpi-text">
                <span>{{ k.label }}</span>
                <strong :class="{ warn: k.warn }">{{ k.value }}<small v-if="k.of"> / {{ k.of }}</small></strong>
              </div>
            </div>
          </section>

          <!-- access point -->
          <section v-else-if="id === 'aps'" class="ap-grid">
            <article v-for="a in aps" :key="a.ap" class="ap clickable" :class="{ off: !a.online }" @click="view = a.ap">
              <header>
                <span class="status" :class="a.online ? 'on' : 'off'" />
                <div class="grow">
                  <h3>{{ a.ap }}</h3>
                  <p class="muted small">{{ a.model || 'modello non letto' }} · <span class="mono">{{ a.host }}</span></p>
                </div>
                <span class="tag" :class="a.method">{{ a.method.toUpperCase() }}</span>
              </header>
              <div class="ap-tiles">
                <div class="tile tone-violet">
                  <Icon name="users" :size="16" /><span>Client</span><strong>{{ a.clients ?? '—' }}</strong>
                </div>
                <div class="tile tone-blue" :title="a.method === 'ssh' && a.uptime_s == null ? SSH_NA : ''">
                  <Icon name="clock" :size="16" /><span>Acceso da</span>
                  <strong>{{ a.uptime_s == null && a.method === 'ssh' && a.online ? 'n.d.' : duration(a.uptime_s) }}</strong>
                </div>
                <div class="tile tone-amber" :title="a.method === 'ssh' && !usage?.per_ap[a.ap] ? SSH_NA : ''">
                  <Icon name="chart" :size="16" /><span :title="`Traffico ${periodLabel}`">Traffico</span>
                  <strong>{{ usage?.per_ap[a.ap] ? bytes(usage.per_ap[a.ap].down + usage.per_ap[a.ap].up) : a.method === 'ssh' && a.online ? 'n.d.' : '—' }}</strong>
                </div>
              </div>
              <div class="ap-bands">
                <span v-for="r in a.radios" :key="r.band" class="radio" :class="bandClass(r.band)"
                      :title="r.channel ? `canale ${r.channel}` : 'canale non fornito da questo AP'">
                  <b>{{ r.band.replace('GHz', ' GHz') }}</b>
                  <span :title="r.utilization != null ? `Potenza ${r.tx_power ?? '—'} dBm, canale occupato al ${r.utilization}%` : ''">
                    ch {{ r.channel ?? '—' }}<template v-if="r.tx_power != null"> · {{ r.tx_power }} dBm</template>
                  </span>
                  <span>{{ r.clients }} client</span>
                </span>
              </div>
              <p v-if="a.error" class="error small">{{ a.error }}</p>
            </article>
            <p v-if="!aps.length" class="muted">In attesa della prima lettura degli access point…</p>
          </section>

          <!-- Internet -->
          <InternetCard v-else-if="id === 'internet'" :internet="internet" :period-label="periodLabel" @settings="view = '#settings'" />

          <!-- siti -->
          <template v-else-if="id === 'sites'">
            <h2>Siti più visitati <span class="muted small">({{ periodLabel }}, richieste DNS)</span></h2>
            <BarList v-if="siteItems.length" :items="siteItems" />
            <p v-else-if="sites?.available" class="muted">Nessuna richiesta nel periodo per questi dispositivi.</p>
            <div v-else class="empty">
              <p>Gli access point non vedono i siti visitati: questo dato arriva dal <strong>DNS della rete</strong>.</p>
              <p class="muted small">Collega OPNsense in <a href="#" @click.prevent="view = '#settings'">Impostazioni</a>: i dati arrivano entro un minuto.</p>
            </div>
          </template>

          <template v-else-if="id === 'types'">
            <h2>Dispositivi per tipologia</h2>
            <PieChart v-if="byType.length" :items="byType" />
            <p v-else class="muted">Nessun client.</p>
          </template>

          <template v-else-if="id === 'traffic_ap'">
            <h2>Traffico per access point <span class="muted small">({{ periodLabel }})</span></h2>
            <PieChart v-if="gbByAp.length" :items="gbByAp" :format="bytes" />
            <p v-else class="muted">Dati in raccolta: servono alcuni minuti.</p>
          </template>

          <template v-else-if="id === 'blocked'">
            <h2>Pubblicità e tracker bloccati</h2>
            <template v-if="internet?.dns">
              <div class="blocked-head">
                <strong>{{ internet.dns.blocked_pct.toLocaleString('it-IT', { maximumFractionDigits: 1 }) }}%</strong>
                <span class="muted small">
                  delle richieste DNS: {{ internet.dns.blocked.toLocaleString('it-IT') }} su
                  {{ internet.dns.total.toLocaleString('it-IT') }} dal {{ new Date(internet.dns.since * 1000).toLocaleDateString('it-IT') }}
                </span>
              </div>
              <BarList v-if="blockedItems.length" :items="blockedItems" />
              <p v-else class="muted">Nessun dominio bloccato finora.</p>
            </template>
            <p v-else class="muted small">Arriva dal DNS di OPNsense: collegalo in <a href="#" @click.prevent="view = '#settings'">Impostazioni</a>.</p>
          </template>

          <template v-else-if="id === 'clients_ap'">
            <h2>Client per access point</h2>
            <PieChart v-if="byAp.length" :items="byAp" />
            <p v-else class="muted">Nessun client.</p>
          </template>

          <template v-else-if="id === 'band'">
            <h2>Client per banda</h2>
            <PieChart v-if="byBand.length" :items="byBand" />
            <p v-else class="muted">Nessun client.</p>
          </template>

          <!-- dispositivi nuovi -->
          <template v-else-if="id === 'new_devices'">
            <div class="section-head">
              <h2>Dispositivi nuovi</h2>
              <button class="ghost small" @click="view = '#devices'">Gestisci</button>
            </div>
            <p v-if="!newDevices.length" class="muted small">Nessun dispositivo sconosciuto: tutti quelli visti sono riconosciuti.</p>
            <ul v-else class="rows">
              <li v-for="d in newDevices.slice(0, 12)" :key="d.mac">
                <span class="status" :class="d.online ? 'on' : 'idle'" />
                <span class="grow"><strong>{{ d.alias || d.hostname || d.last_ip || d.mac }}</strong>
                  <span class="muted small"> · {{ d.device_type }} · {{ d.last_ap || '—' }}</span></span>
                <span class="muted small">{{ time(d.first_seen) }}</span>
              </li>
            </ul>
          </template>

          <!-- segnale -->
          <template v-else-if="id === 'signal'">
            <h2>Qualità del segnale <span class="muted small">({{ periodLabel }})</span></h2>
            <p v-if="!signalAps?.aps.length" class="muted small">Storico del segnale in raccolta.</p>
            <template v-else>
              <ul class="rows">
                <li v-for="s in signalAps?.aps ?? []" :key="s.ap" :title="`${s.devices} dispositivi`">
                  <span class="grow"><strong>{{ s.ap }}</strong></span>
                  <span class="sig" :class="signal(s.avg).level">{{ s.avg }} dBm</span>
                  <span class="muted small">{{ s.weak_pct }}% deboli</span>
                </li>
              </ul>
              <h3 class="small sub">Segnale peggiore</h3>
              <ul class="rows">
                <li v-for="w in signalAps?.worst ?? []" :key="w.mac">
                  <span class="grow">{{ w.name }} <span class="muted small">· {{ w.ap || '—' }}</span></span>
                  <span class="sig" :class="signal(w.avg).level">{{ w.avg }} dBm</span>
                </li>
              </ul>
            </template>
          </template>

          <!-- roaming -->
          <template v-else-if="id === 'roaming'">
            <h2>Roaming <span class="muted small">({{ periodLabel }})</span></h2>
            <p v-if="!roamItems.length" class="muted small">Nessuno spostamento fra access point nel periodo.</p>
            <template v-else>
              <BarList :items="roamItems" />
              <h3 class="small sub">Chi si sposta di più</h3>
              <ul class="rows">
                <li v-for="d in roaming?.devices ?? []" :key="d.mac">
                  <span class="grow">{{ d.name }} <span class="muted small">· {{ d.aps.join(' ↔ ') }}</span></span>
                  <span v-if="d.bouncing" class="badge ko" title="Rimbalza fra AP: valuta di ridurre la potenza radio in Nebula">rimbalza</span>
                  <strong>{{ d.count }}</strong>
                </li>
              </ul>
            </template>
          </template>

          <!-- consumo per dispositivo -->
          <template v-else-if="id === 'usage_devices'">
            <h2>Consumo per dispositivo <span class="muted small">(dati inviati, {{ periodLabel }})</span></h2>
            <p v-if="deviceUsage?.available && !deviceUsage.debug" class="muted small">NetFlow di OPNsense conta i byte inviati da ogni indirizzo: i download non sono ancora inclusi.</p>
            <div v-if="deviceUsage?.available && deviceUsage.debug" class="usage-debug">
              <p>
                OPNsense ha risposto con <strong>{{ deviceUsage.debug.rows }}</strong> righe e
                <strong>{{ deviceUsage.debug.addresses }}</strong> indirizzi, ma nessuno corrisponde ai dispositivi Wi-Fi.
              </p>
              <p class="muted small">
                Se sono appena passati pochi minuti dall'attivazione di NetFlow è normale: Insight aggrega i dati ogni
                10-15 minuti. Se resta così, copia la risposta qui sotto e mandala.
              </p>
              <p v-if="deviceUsage.debug.sample_addresses.length" class="muted small mono">
                Indirizzi ricevuti: {{ deviceUsage.debug.sample_addresses.join(', ') }}
              </p>
              <div class="actions">
                <button class="ghost small" @click="copyUsageDebug">{{ usageCopied ? 'Copiato' : 'Copia risposta' }}</button>
              </div>
              <pre class="raw">{{ deviceUsage.debug.path }}&#10;{{ deviceUsage.debug.sample }}</pre>
            </div>
            <div v-else-if="deviceUsage?.available" class="split">
              <div><h3 class="small sub">Dispositivi</h3><BarList :items="usageItems" :format="bytes" /></div>
              <div><h3 class="small sub">Per tipologia</h3><BarList :items="usageTypes" :format="bytes" /></div>
            </div>
            <div v-else class="empty">
              <template v-if="deviceUsage?.reason === 'netflow'">
                <p>Serve <strong>NetFlow</strong> su OPNsense.</p>
                <p class="muted small">Reporting → NetFlow: interfaccia LAN, spunta “Capture local”, salva. I dati arrivano in pochi minuti.</p>
              </template>
              <template v-else-if="deviceUsage?.reason === 'error'">
                <p>OPNsense ha risposto in modo inatteso.</p>
                <p class="muted small mono">{{ deviceUsage.message }}</p>
              </template>
              <p v-else class="muted small">Arriva da OPNsense: collegalo in <a href="#" @click.prevent="view = '#settings'">Impostazioni</a>.</p>
            </div>
          </template>

          <!-- andamento -->
          <template v-else-if="id === 'trend'">
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
              Questo AP è letto via SSH: il traffico non è ancora disponibile, guarda il grafico "Client".
            </p>
          </template>

          <!-- client -->
          <template v-else-if="id === 'clients'">
            <h2 class="mb">{{ currentAp ? `Client connessi a ${currentAp.ap}` : 'Tutti i client connessi' }}</h2>
            <p class="muted small mb">Clicca un dispositivo per vedere segnale nel tempo e siti che contatta.</p>
            <ClientsTable :clients="scopedClients" :show-ap="!currentAp" :hours="hours" @rename="rename" />
          </template>

          <template v-else-if="id === 'ap_events' && currentAp">
            <h2 class="mb">Chi si è collegato a {{ currentAp.ap }}</h2>
            <EventsTable :events="scopedEvents" />
          </template>
        </template>
      </Dashboard>
    </main>
  </div>

  <footer class="footer" v-if="health">v{{ health.version }} — Ideato e sviluppato da {{ health.author }}</footer>
</template>
