<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Internet, TrafficPoint } from '../api'
import { bps, bytes, duration, time } from '../format'
import { locale, t } from '../i18n'
import LineChart from './LineChart.vue'
import TrafficChart from './TrafficChart.vue'

const props = defineProps<{ internet: Internet | null; periodLabel: string }>()
const emit = defineEmits<{ settings: [] }>()

const metric = ref<'down_bps' | 'up_bps' | 'delay' | 'loss'>('down_bps')
const gateway = computed(() => props.internet?.gateways[0] ?? null)
const series = computed(() => {
  const out: Record<string, TrafficPoint[]> = {}
  if (props.internet?.available) out.Internet = props.internet.series
  return out
})
const now = computed(() => [...(props.internet?.series ?? [])].reverse().find(x => x.down_bps != null) ?? null)
const quality = computed(() => props.internet?.quality ?? [])
const hasQuality = computed(() => quality.value.some(p => p.delay_ms != null))
const ms = (v: number) => `${v.toLocaleString(locale(), { maximumFractionDigits: 1 })} ms`
const perc = (v: number) => `${v.toLocaleString(locale(), { maximumFractionDigits: 1 })}%`
</script>

<template>
  <div v-if="!internet?.available" class="empty">
    <p>{{ t('Lo stato della linea arriva da') }} <strong>OPNsense</strong>.</p>
    <p class="muted small">{{ t('Collegalo in') }} <a href="#" @click.prevent="emit('settings')">{{ t('Impostazioni') }}</a>.</p>
  </div>
  <div v-else class="internet">
    <div class="section-head">
      <h2>Internet <span class="muted small">{{ gateway?.name }}</span></h2>
      <span v-if="gateway" class="badge" :class="gateway.online ? 'ok' : 'ko'">{{ gateway.online ? 'Online' : gateway.status }}</span>
      <div class="seg">
        <button :class="{ active: metric === 'down_bps' }" @click="metric = 'down_bps'">Download</button>
        <button :class="{ active: metric === 'up_bps' }" @click="metric = 'up_bps'">Upload</button>
        <button :class="{ active: metric === 'delay' }" @click="metric = 'delay'">{{ t('Latenza') }}</button>
        <button :class="{ active: metric === 'loss' }" @click="metric = 'loss'">{{ t('Perdita') }}</button>
      </div>
    </div>
    <div class="kpis inner">
      <div class="kpi"><span>{{ t('Latenza') }}</span><strong>{{ gateway?.delay || '—' }}</strong></div>
      <div class="kpi"><span>{{ t('Pacchetti persi') }}</span><strong>{{ gateway?.loss || '—' }}</strong></div>
      <div class="kpi"><span>{{ t('Disponibilità {period}', { period: periodLabel }) }}</span>
        <strong :class="{ warn: internet.availability != null && internet.availability < 99.9 }">
          {{ internet.availability != null ? perc(internet.availability) : '—' }}</strong></div>
      <div class="kpi"><span>{{ t('Download ora') }}</span><strong>{{ bps(now?.down_bps) }}</strong></div>
      <div class="kpi"><span>{{ t('Upload ora') }}</span><strong>{{ bps(now?.up_bps) }}</strong></div>
      <div class="kpi"><span>{{ t('Scaricati · inviati') }}</span><strong class="small-num">{{ bytes(internet.period.down) }} · {{ bytes(internet.period.up) }}</strong></div>
    </div>
    <div class="internet-body">
      <div class="grow">
        <template v-if="metric === 'down_bps' || metric === 'up_bps'">
          <TrafficChart v-if="internet.series.some(p => p.down_bps != null)" :series="series" :metric="metric === 'up_bps' ? 'up_bps' : 'down_bps'" />
          <p v-else class="muted small">{{ t('Il grafico della linea si popola dopo qualche minuto.') }}</p>
        </template>
        <template v-else>
          <LineChart v-if="hasQuality" :ts="quality.map(p => p.ts)" zero
                     :datasets="[metric === 'delay'
                       ? { label: t('Latenza'), data: quality.map(p => p.delay_ms), color: '--weak' }
                       : { label: t('Perdita'), data: quality.map(p => p.loss_pct), color: '--bad' }]"
                     :format="metric === 'delay' ? ms : perc" />
          <p v-else class="muted small">{{ t('Lo storico di latenza e perdita si popola dopo qualche minuto.') }}</p>
        </template>
      </div>
      <div class="outages">
        <h3 class="small">{{ t('Disservizi {period}', { period: periodLabel }) }}</h3>
        <p v-if="!internet.outages.length" class="muted small">{{ t('Nessuna interruzione della linea.') }}</p>
        <ul v-else class="rows">
          <li v-for="o in internet.outages" :key="o.start">
            <span class="status" :class="o.end ? 'off' : 'off pulse'" />
            <span class="mono small">{{ time(o.start) }}</span>
            <span>{{ o.end ? duration(o.duration) : t('in corso da {d}', { d: duration(o.duration) }) }}</span>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>
