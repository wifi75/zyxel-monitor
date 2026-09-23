<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Client } from '../api'
import { isPrivateMac, signal, since } from '../format'

const props = defineProps<{ clients: Client[]; showAp?: boolean }>()
const emit = defineEmits<{ rename: [c: Client] }>()
const search = ref('')

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return props.clients
  return props.clients.filter(c =>
    [c.alias, c.hostname, c.ip, c.mac, c.ssid, c.ap, c.device_type].some(v => v?.toLowerCase().includes(q)))
})

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
        <tr v-for="c in filtered" :key="c.mac">
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
          <td><button class="ghost small" @click="emit('rename', c)">Rinomina</button></td>
        </tr>
        <tr v-if="!filtered.length"><td :colspan="showAp ? 8 : 7" class="muted">Nessun client.</td></tr>
      </tbody>
    </table>
  </div>
</template>
