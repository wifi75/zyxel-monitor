<script setup lang="ts">
import { computed, ref } from 'vue'
import { api, download, type Device, type Event, type SignalHistory } from '../api'
import { isPrivateMac, since, time } from '../format'
import EventsTable from './EventsTable.vue'
import LineChart from './LineChart.vue'
import { t } from '../i18n'

const props = defineProps<{ devices: Device[] }>()
const emit = defineEmits<{ changed: []; rename: [d: Device] }>()

const filter = ref<'new' | 'online' | 'all'>(props.devices.some(d => !d.known) ? 'new' : 'all')
const search = ref('')
const error = ref('')

const counts = computed(() => ({
  new: props.devices.filter(d => !d.known).length,
  online: props.devices.filter(d => d.online).length,
  all: props.devices.length,
}))

const shown = computed(() => {
  const q = search.value.trim().toLowerCase()
  return props.devices
    .filter(d => filter.value === 'all' || (filter.value === 'new' ? !d.known : d.online))
    .filter(d => !q || [d.alias, d.hostname, d.last_ip, d.mac, d.last_ap, d.device_type, d.vendor]
      .some(v => v?.toLowerCase().includes(q)))
})

const name = (d: Device) => d.alias || d.hostname || d.last_ip || d.mac

/** colore stabile per tipologia */
const TONES: Record<string, string> = {
  Energia: 'var(--amber)', Domotica: 'var(--teal)', Smartphone: 'var(--violet)', 'TV e media': 'var(--pink)',
  Microcontrollori: 'var(--blue)', Computer: 'var(--green)', Altro: 'var(--muted)',
}
const tone = (k: string) => TONES[k] ?? 'var(--orange)'

// ---- storico del dispositivo: collegamenti, roaming e segnale ----
const openMac = ref<string | null>(null)
const history = ref<{ events: Event[]; signal: SignalHistory | null } | null>(null)
async function toggle(d: Device) {
  if (openMac.value === d.mac) { openMac.value = null; return }
  openMac.value = d.mac
  history.value = null
  const [events, signal] = await Promise.all([
    api.events(100, undefined, d.mac).catch(() => []),
    api.signal(d.mac, 24 * 7).catch(() => null),
  ])
  if (openMac.value === d.mac) history.value = { events, signal }
}
const hasSignal = computed(() => history.value?.signal?.points.some(p => p.avg != null) ?? false)
const dbm = (v: number) => `${v} dBm`

async function run(fn: () => Promise<unknown>) {
  try { await fn(); error.value = ''; emit('changed') } catch (e) { error.value = (e as Error).message }
}
const setKnown = (d: Device, known: boolean) => run(() => api.setKnown(d.mac, known))
const setCritical = (d: Device) => run(() => api.setCritical(d.mac, !d.critical))
const exportCsv = () => download('/export/devices.csv', 'dispositivi.csv').catch(e => { error.value = (e as Error).message })
const allKnown = () => run(() => api.setAllKnown())
function forget(d: Device) {
  if (window.confirm(t("Togliere {n} dall'elenco? Se si ricollega risulterà di nuovo nuovo.", { n: name(d) }))) run(() => api.forgetDevice(d.mac))
}
</script>

<template>
  <main>
    <section class="card">
      <div class="section-head">
        <h2>{{ t('Dispositivi') }}</h2>
        <div class="seg">
          <button :class="{ active: filter === 'new' }" @click="filter = 'new'">{{ t('Nuovi') }} <span class="pill">{{ counts.new }}</span></button>
          <button :class="{ active: filter === 'online' }" @click="filter = 'online'">{{ t('Connessi') }} <span class="pill">{{ counts.online }}</span></button>
          <button :class="{ active: filter === 'all' }" @click="filter = 'all'">{{ t('Tutti') }} <span class="pill">{{ counts.all }}</span></button>
        </div>
        <button v-if="counts.new" class="ghost" @click="allKnown">{{ t('Riconosci tutti') }}</button>
        <button class="ghost" @click="exportCsv">{{ t('Esporta CSV') }}</button>
      </div>
      <input v-model="search" class="search dev-search" :placeholder="t('Cerca nome, IP, MAC, AP…')" />
      <p class="muted small mb">
        {{ t('Ogni dispositivo che si collega per la prima volta finisce tra i') }} <strong>{{ t('nuovi') }}</strong> {{ t('finché non lo riconosci: così ti accorgi subito di chi usa il Wi-Fi. I MAC “privati” cambiano nel tempo e possono ripresentarsi come nuovi.') }}
      </p>
      <p v-if="error" class="error">{{ error }}</p>
      <div class="table-wrap">
        <table>
          <thead><tr>
            <th /><th>{{ t('Dispositivo') }}</th><th>{{ t('Tipo') }}</th><th>{{ t('Produttore') }}</th><th>IP</th><th>MAC</th><th>AP</th><th>{{ t('Prima volta') }}</th><th>{{ t('Ultima volta') }}</th>
            <th :title="t('Scollegamenti e cambi di AP nelle ultime 24 ore')">{{ t('24 ore') }}</th><th />
          </tr></thead>
          <tbody>
            <template v-for="d in shown" :key="d.mac">
            <tr class="clickable-row" :class="{ unknown: !d.known, open: openMac === d.mac }" @click="toggle(d)">
              <td><span class="status" :class="d.online ? 'on' : 'idle'" :title="d.online ? t('connesso') : t('non connesso')" /></td>
              <td class="dev-name">
                <strong :title="name(d)">{{ name(d) }}</strong>
                <span v-if="!d.known" class="badge ko">{{ t('nuovo') }}</span>
                <span v-if="d.critical" class="badge ok" :title="t('Dispositivo importante')">{{ t('importante') }}</span>
              </td>
              <td><span class="chip" :style="{ '--tone': tone(d.device_type) }">{{ t(d.device_type) }}</span></td>
              <td class="small">{{ d.vendor ? t(d.vendor) : '—' }}</td>
              <td class="mono small">{{ d.last_ip || '—' }}</td>
              <td class="mono small">{{ d.mac }}<span v-if="isPrivateMac(d.mac)" class="muted" :title="t('MAC privato (randomizzato)')"> ⓟ</span></td>
              <td><span v-if="d.last_ap" class="chip ap-chip">{{ d.last_ap }}</span><span v-else class="muted">—</span></td>
              <td class="small nowrap">{{ time(d.first_seen) }}</td>
              <td class="small nowrap" :class="{ 'ok-text': d.online }">{{ d.online ? t('adesso') : t('{t} fa', { t: since(d.last_seen) }) }}</td>
              <td class="small nowrap" :class="{ 'warn-text': (d.drops_24h ?? 0) >= 10 }"
                  :title="t('{d} scollegamenti, {r} cambi di AP nelle ultime 24 ore', { d: d.drops_24h ?? 0, r: d.roams_24h ?? 0 })">
                ↯ {{ d.drops_24h ?? 0 }} · ⇄ {{ d.roams_24h ?? 0 }}
              </td>
              <td class="row-actions" @click.stop>
                <button class="ghost small" :class="{ 'crit-on': d.critical }"
                        :title="d.critical ? t('Importante: avviso su Telegram se resta scollegato. Clicca per togliere.') : t('Segna come importante: avviso su Telegram se resta scollegato')"
                        @click="setCritical(d)">{{ d.critical ? '★' : '☆' }}</button>
                <button v-if="!d.known" class="ghost small primary-text" @click="setKnown(d, true)">{{ t('Riconosci') }}</button>
                <button v-else class="ghost small" :title="t('Segna come nuovo')" @click="setKnown(d, false)">{{ t('Nuovo') }}</button>
                <button class="ghost small" @click="emit('rename', d)">{{ t('Rinomina') }}</button>
                <button class="ghost small danger" :title="t('Dimentica')" @click="forget(d)">×</button>
              </td>
            </tr>
            <tr v-if="openMac === d.mac" class="detail-row">
              <td colspan="11">
                <div v-if="!history" class="muted small">{{ t('Caricamento…') }}</div>
                <template v-else>
                  <strong class="small">{{ t('Segnale negli ultimi 7 giorni') }}</strong>
                  <div v-if="hasSignal && history.signal" class="signal-box">
                    <LineChart :ts="history.signal.points.map(p => p.ts)" :format="dbm"
                               :datasets="[{ label: t('Medio'), data: history.signal.points.map(p => p.avg) },
                                           { label: t('Peggiore'), data: history.signal.points.map(p => p.min), color: '--bad' }]" />
                  </div>
                  <p v-else class="muted small">{{ t('Nessuna lettura del segnale nel periodo.') }}</p>
                  <strong class="small">{{ t('Collegamenti e roaming') }}</strong>
                  <EventsTable :events="history.events" show-ap />
                </template>
              </td>
            </tr>
            </template>
            <tr v-if="!shown.length"><td colspan="11" class="muted">{{ t('Nessun dispositivo.') }}</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  </main>
</template>

<style scoped>
.crit-on { color: var(--weak); }
.warn-text { color: var(--weak); }
</style>
