<script setup lang="ts">
import { computed, ref } from 'vue'
import { api, type Client, type Sites } from '../api'
import { isPrivateMac, signal, since } from '../format'

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
  if (c.ip) deviceSites.value = await api.sites(props.hours ?? 24, undefined, c.ip).catch(() => null)
}

function displayName(c: Client) { return c.alias || c.hostname || c.ip || c.mac }
</script>

<template>
  <div class="section-head">
    <input v-model="search" class="search" placeholder="Cerca nome, IP, MAC, tipo…" />
    <span class="muted small">{{ filtered.length }} client</span>
  </div>
  <div class="table-wrap">
    <table>
      <thead><tr>
        <th>Dispositivo</th><th>Tipo</th><th v-if="showAp">AP</th><th>Banda</th><th>Segnale</th><th>Velocità</th><th>Connesso da</th><th />
      </tr></thead>
      <tbody>
        <template v-for="c in filtered" :key="c.mac">
        <tr class="clickable-row" :class="{ open: openMac === c.mac }" @click="toggleSites(c)">
          <td>
            <strong>{{ displayName(c) }}</strong>
            <div class="muted small mono">{{ c.ip || '—' }} · {{ c.mac }}<span v-if="isPrivateMac(c.mac)" title="MAC privato (randomizzato)"> · privato</span></div>
          </td>
          <td>{{ c.device_type }}</td>
          <td v-if="showAp">{{ c.ap }}</td>
          <td>{{ c.band || '—' }}<div class="muted small">{{ c.capability || '' }}</div></td>
          <td><span class="sig" :class="signal(c.rssi_dbm).level">{{ c.rssi_dbm ?? '—' }} dBm</span></td>
          <td class="mono small">{{ c.tx_rate != null ? `↓${c.tx_rate} ↑${c.rx_rate} Mbps` : '—' }}</td>
          <td>{{ since(c.connected_at) }}</td>
          <td><button class="ghost small" @click.stop="emit('rename', c)">Rinomina</button></td>
        </tr>
        <tr v-if="openMac === c.mac" class="detail-row">
          <td :colspan="showAp ? 8 : 7">
            <strong class="small">Siti più contattati da {{ displayName(c) }}</strong>
            <div v-if="!c.ip" class="muted small">IP sconosciuto: nessun dato DNS.</div>
            <div v-else-if="!deviceSites" class="muted small">Caricamento…</div>
            <div v-else-if="!deviceSites.items.length" class="muted small">Nessuna richiesta DNS nel periodo.</div>
            <ol v-else class="site-list">
              <li v-for="i in deviceSites.items" :key="i.site"><span>{{ i.site }}</span><span class="muted">{{ i.queries }}</span></li>
            </ol>
          </td>
        </tr>
        </template>
        <tr v-if="!filtered.length"><td :colspan="showAp ? 8 : 7" class="muted">Nessun client.</td></tr>
      </tbody>
    </table>
  </div>
</template>
