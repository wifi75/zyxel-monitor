<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { api, type WiredClients } from '../api'
import { t } from '../i18n'
import Icon from './Icon.vue'

/** Client Wi-Fi e via cavo, come il riquadro "Clients" di Nebula; i cablati vengono dalla tabella ARP di OPNsense. */
const data = ref<WiredClients | null>(null)
const open = ref(false)
let timer = 0
async function load() {
  try { data.value = await api.clientsWired() } catch { /* resta l'ultimo valore */ }
}
onMounted(() => { load(); timer = window.setInterval(load, 120_000) })
onUnmounted(() => window.clearInterval(timer))
</script>

<template>
  <h2>{{ t('Client Wi-Fi e via cavo') }}</h2>
  <div class="wired-kpis">
    <div><Icon name="wifi" :size="20" /><strong>{{ data?.wireless ?? '—' }}</strong><span class="muted small">{{ t('Wi-Fi') }}</span></div>
    <button class="ghost" :disabled="!data?.items.length" :title="t('Mostra i dispositivi via cavo')" @click="open = !open">
      <Icon name="router" :size="20" /><strong>{{ data?.wired ?? '—' }}</strong><span class="muted small">{{ t('Via cavo') }}</span>
    </button>
  </div>
  <p v-if="data && !data.available" class="muted small">
    {{ data.reason === 'opnsense' ? t('I dispositivi via cavo arrivano da OPNsense: collegalo in Impostazioni.') : t('OPNsense non ha dato la tabella ARP: {msg}', { msg: data.message ?? '' }) }}
  </p>
  <div v-if="open && data?.items.length" class="table-wrap">
    <table class="compact">
      <thead><tr><th>{{ t('Dispositivo') }}</th><th>IP</th><th>{{ t('Produttore') }}</th></tr></thead>
      <tbody>
        <tr v-for="d in data.items" :key="d.mac">
          <td>{{ d.name }}</td><td class="mono small">{{ d.ip }}</td><td class="small muted">{{ d.vendor ?? '—' }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.wired-kpis { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 8px 0; }
.wired-kpis > * { display: grid; justify-items: center; gap: 2px; padding: 10px; border: 1px solid var(--border);
                  border-radius: var(--radius); background: var(--surface-2); min-height: 0; height: auto; }
.wired-kpis strong { font: 600 26px var(--font-mono); color: var(--text); }
.wired-kpis .icon { color: var(--accent); }
</style>
