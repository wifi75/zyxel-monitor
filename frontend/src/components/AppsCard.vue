<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { api, type AppUsage } from '../api'
import { bytes } from '../format'
import { t } from '../i18n'
import DonutChart from './DonutChart.vue'

/** Traffico per servizio (YouTube, Netflix…): stima dagli indirizzi remoti di NetFlow, senza DPI. */
const props = defineProps<{ hours: number; periodLabel: string }>()
const data = ref<AppUsage | null>(null)
async function load() {
  try { data.value = await api.usageApps(props.hours) } catch { /* resta l'ultimo valore */ }
}
onMounted(load)
watch(() => props.hours, load)

/** i primi servizi uno per uno, il resto in "Altro": una ciambella con troppe fette non si legge */
const TOP = 6
const items = computed(() => {
  const all = (data.value?.items ?? []).map(i => ({ label: t(i.name), value: i.bytes }))
  const head = all.filter(i => i.label !== t('Altro')).slice(0, TOP)
  const rest = all.reduce((s, i) => s + i.value, 0) - head.reduce((s, i) => s + i.value, 0)
  return rest > 0 ? [...head, { label: t('Altro'), value: rest }] : head
})
const totalParts = computed(() => {
  const [num, unit] = bytes(data.value?.total ?? 0).split(' ')
  return { num, unit }
})
</script>

<template>
  <h2>{{ t('Traffico per servizio') }} <span class="muted small">({{ periodLabel }})</span></h2>
  <template v-if="data?.available">
    <DonutChart v-if="items.length" :items="items" :center="totalParts.num" :unit="totalParts.unit" :format="bytes" />
    <p v-else class="muted small">{{ t('Insight non ha ancora dati per questo periodo.') }}</p>
    <p class="muted small note-line">{{ t('Stima dagli indirizzi remoti: il traffico verso le CDN condivise resta col nome della CDN.') }}</p>
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

<style scoped>
.note-line { margin: 10px 0 0; }
</style>
