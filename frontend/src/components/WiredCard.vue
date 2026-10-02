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
  <h2>{{ t('Client') }}</h2>
  <div class="wired-kpis">
    <div class="kpi-big">
      <strong>{{ data?.wireless ?? '—' }}</strong>
      <span class="lbl"><Icon name="wifi" :size="18" /> {{ t('Wi-Fi') }}</span>
    </div>
    <button class="kpi-big" :disabled="!data?.items.length" :aria-expanded="open"
            :title="t('Mostra i dispositivi via cavo')" @click="open = !open">
      <strong>{{ data?.wired ?? '—' }}</strong>
      <span class="lbl"><Icon name="router" :size="18" /> {{ t('Via cavo') }}</span>
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
.wired-kpis { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 6px 0 4px; }
.kpi-big { display: grid; justify-items: center; gap: 4px; padding: 6px 4px; border: none; background: transparent;
           min-height: 0; height: auto; border-radius: var(--radius); }
button.kpi-big:not(:disabled):hover { background: var(--surface-2); }
.kpi-big strong { font: 700 34px/1 var(--font-mono); color: var(--text); letter-spacing: -.02em; }
.lbl { display: inline-flex; align-items: center; gap: 6px; font-size: 15px; color: var(--text); }
.lbl .icon { color: var(--good); }
</style>
