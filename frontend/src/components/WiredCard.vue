<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { api, type WiredClients } from '../api'
import { t } from '../i18n'
import Icon from './Icon.vue'

/**
 * Client Wi-Fi e via cavo, come il riquadro "Clients" di Nebula. I cablati vengono dalla tabella ARP di OPNsense:
 * l'elenco resta sempre sotto i numeri, così si vede subito se il conteggio è giusto.
 */
const data = ref<WiredClients | null>(null)
let timer = 0
async function load() {
  try { data.value = await api.clientsWired() } catch { /* resta l'ultimo valore */ }
}
onMounted(() => { load(); timer = window.setInterval(load, 120_000) })
onUnmounted(() => window.clearInterval(timer))
</script>

<template>
  <h2>{{ t('Client') }}</h2>
  <div class="wired-kpis">
    <div class="kpi-big">
      <strong>{{ data?.wireless ?? '—' }}</strong>
      <span class="lbl"><Icon name="wifi" :size="18" /> {{ t('Wi-Fi') }}</span>
    </div>
    <div class="kpi-big">
      <strong>{{ data?.wired ?? '—' }}</strong>
      <span class="lbl"><Icon name="router" :size="18" /> {{ t('Via cavo') }}</span>
    </div>
  </div>
  <p v-if="data && !data.available" class="muted small">
    {{ data.reason === 'opnsense' ? t('I dispositivi via cavo arrivano da OPNsense: collegalo in Impostazioni.') : t('OPNsense non ha dato la tabella ARP: {msg}', { msg: data.message ?? '' }) }}
  </p>
  <template v-else-if="data">
    <h3 class="small sub">{{ t('Dispositivi via cavo') }}</h3>
    <div v-if="data.items.length" class="table-wrap">
      <table class="compact">
        <thead><tr><th>{{ t('Dispositivo') }}</th><th>IP</th><th>{{ t('Produttore') }}</th><th>{{ t('Rete') }}</th></tr></thead>
        <tbody>
          <tr v-for="d in data.items" :key="d.mac">
            <td :title="d.mac">{{ d.name || t('senza nome') }}</td>
            <td class="mono small">{{ d.ip }}</td>
            <td class="small muted">{{ d.vendor ?? '—' }}</td>
            <td class="small muted">{{ d.intf ?? '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-else class="muted small">{{ t('Nessun dispositivo via cavo nella rete degli access point.') }}</p>
    <p class="muted small">{{ t('Sono esclusi gli AP e i dispositivi visti almeno una volta in Wi-Fi.') }}</p>
  </template>
</template>

<style scoped>
.wired-kpis { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 6px 0 8px; }
.kpi-big { display: grid; justify-items: center; gap: 4px; padding: 6px 4px; }
.kpi-big strong { font: 700 34px/1 var(--font-mono); color: var(--text); letter-spacing: -.02em; }
.lbl { display: inline-flex; align-items: center; gap: 6px; font-size: 15px; color: var(--text); }
.lbl .icon { color: var(--good); }
</style>
