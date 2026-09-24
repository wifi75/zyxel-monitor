<script setup lang="ts">
import { computed, ref } from 'vue'
import { api, type Client, type SignalHistory, type Sites } from '../api'
import { isPrivateMac, signal, since } from '../format'
import LineChart from './LineChart.vue'
import { t } from '../i18n'

const props = defineProps<{ clients: Client[]; showAp?: boolean; hours?: number }>()
const emit = defineEmits<{ rename: [c: Client] }>()
const search = ref('')

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return props.clients
  return props.clients.filter(c =>
    [c.alias, c.hostname, c.ip, c.mac, c.ssid, c.ap, c.device_type].some(v => v?.toLowerCase().includes(q)))
})

const openMac = ref<string | null>(null)
const deviceSites = ref<Sites | null>(null)
async function toggleSites(c: Client) {
  if (openMac.value === c.mac) { openMac.value = null; return }
  openMac.value = c.mac
  deviceSites.value = null
  history.value = null
  const h = props.hours ?? 24
  const [s, g] = await Promise.all([
    c.ip ? api.sites(h, undefined, c.ip).catch(() => null) : Promise.resolve(null),
    api.signal(c.mac, h).catch(() => null),
  ])
  deviceSites.value = s
  history.value = g
}

const history = ref<SignalHistory | null>(null)
const hasHistory = computed(() => history.value?.points.some(p => p.avg != null) ?? false)
const dbm = (v: number) => `${v} dBm`

function displayName(c: Client) { return c.alias || c.hostname || c.ip || c.mac }
</script>

<template>
  <div class="section-head">
    <input v-model="search" class="search" :placeholder="t('Cerca nome, IP, MAC, tipo…')" />
    <span class="muted small">{{ t('{n} client', { n: filtered.length }) }}</span>
  </div>
  <div class="table-wrap">
    <table>
      <thead><tr>
        <th>{{ t('Dispositivo') }}</th><th>{{ t('Tipo') }}</th><th v-if="showAp">AP</th><th>{{ t('Banda') }}</th><th>{{ t('Segnale') }}</th><th>{{ t('Velocità') }}</th><th>{{ t('Connesso da') }}</th><th />
      </tr></thead>
      <tbody>
        <template v-for="c in filtered" :key="c.mac">
        <tr class="clickable-row" :class="{ open: openMac === c.mac }" @click="toggleSites(c)">
          <td>
            <strong>{{ displayName(c) }}</strong>
            <div class="muted small mono">{{ c.ip || '—' }} · {{ c.mac }}<span v-if="isPrivateMac(c.mac)" :title="t('MAC privato (randomizzato)')"> · {{ t('privato') }}</span></div>
          </td>
          <td>{{ t(c.device_type) }}</td>
          <td v-if="showAp">{{ c.ap }}</td>
          <td>{{ c.band || '—' }}<div class="muted small">{{ c.capability || '' }}</div></td>
          <td><span class="sig" :class="signal(c.rssi_dbm).level">{{ c.rssi_dbm ?? '—' }} dBm</span></td>
          <td class="mono small">{{ c.tx_rate != null ? `↓${c.tx_rate} ↑${c.rx_rate} Mbps` : '—' }}</td>
          <td>{{ since(c.connected_at) }}</td>
          <td><button class="ghost small" @click.stop="emit('rename', c)">{{ t('Rinomina') }}</button></td>
        </tr>
        <tr v-if="openMac === c.mac" class="detail-row">
          <td :colspan="showAp ? 8 : 7">
            <strong class="small">{{ t('Segnale di {n} nel tempo', { n: displayName(c) }) }}</strong>
            <div v-if="hasHistory && history" class="signal-box">
              <LineChart :ts="history.points.map(p => p.ts)" :format="dbm"
                         :datasets="[{ label: t('Medio'), data: history.points.map(p => p.avg) },
                                     { label: t('Peggiore'), data: history.points.map(p => p.min), color: '#ef4444' }]" />
            </div>
            <div v-else class="muted small mb">{{ t('Storico del segnale in raccolta.') }}</div>
            <strong class="small">{{ t('Siti più contattati da {n}', { n: displayName(c) }) }}</strong>
            <div v-if="!c.ip" class="muted small">{{ t('IP sconosciuto: nessun dato DNS.') }}</div>
            <div v-else-if="!deviceSites" class="muted small">{{ t('Caricamento…') }}</div>
            <div v-else-if="!deviceSites.items.length" class="muted small">{{ t('Nessuna richiesta DNS nel periodo.') }}</div>
            <ol v-else class="site-list">
              <li v-for="i in deviceSites.items" :key="i.site"><span>{{ i.site }}</span><span class="muted">{{ i.queries }}</span></li>
            </ol>
          </td>
        </tr>
        </template>
        <tr v-if="!filtered.length"><td :colspan="showAp ? 8 : 7" class="muted">{{ t('Nessun client.') }}</td></tr>
      </tbody>
    </table>
  </div>
</template>
