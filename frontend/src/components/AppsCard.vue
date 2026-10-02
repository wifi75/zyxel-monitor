<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { api, type AppUsage } from '../api'
import { bytes } from '../format'
import { t } from '../i18n'
import BarList from './BarList.vue'

/** Traffico per servizio (YouTube, Netflix…): stima dagli indirizzi remoti di NetFlow, senza DPI. */
const props = defineProps<{ hours: number; periodLabel: string }>()
const data = ref<AppUsage | null>(null)
async function load() {
  try { data.value = await api.usageApps(props.hours) } catch { /* resta l'ultimo valore */ }
}
onMounted(load)
watch(() => props.hours, load)
const items = computed(() => (data.value?.items ?? []).map(i => ({
  label: t(i.name), value: i.bytes,
  title: data.value?.total ? `${Math.round((i.bytes / data.value.total) * 100)}%` : undefined,
})))
</script>

<template>
  <h2>{{ t('Traffico per servizio') }} <span class="muted small">({{ periodLabel }}<template v-if="data?.total"> · {{ bytes(data.total) }}</template>)</span></h2>
  <template v-if="data?.available">
    <BarList v-if="items.length" :items="items" :format="bytes" />
    <p v-else class="muted small">{{ t('Insight non ha ancora dati per questo periodo.') }}</p>
    <p class="muted small">{{ t('Stima dagli indirizzi remoti: il traffico verso le CDN condivise resta col nome della CDN.') }}</p>
  </template>
  <div v-else-if="data" class="empty">
    <template v-if="data.reason === 'netflow'">
      <p>{{ t('Serve') }} <strong>NetFlow</strong> {{ t('su OPNsense.') }}</p>
      <p class="muted small">{{ t('Reporting → NetFlow: interfaccia LAN, spunta “Capture local”, salva. I dati arrivano in pochi minuti.') }}</p>
    </template>
    <p v-else-if="data.reason === 'error'" class="muted small mono">{{ data.message }}</p>
    <p v-else class="muted small">{{ t('Arriva da OPNsense: collegalo in Impostazioni.') }}</p>
  </div>
</template>
