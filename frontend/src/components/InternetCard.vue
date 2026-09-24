<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Internet, TrafficPoint } from '../api'
import { bps, bytes, duration, time } from '../format'
import LineChart from './LineChart.vue'
import TrafficChart from './TrafficChart.vue'

const props = defineProps<{ internet: Internet | null; periodLabel: string }>()
const emit = defineEmits<{ settings: [] }>()

const metric = ref<'down_bps' | 'up_bps' | 'delay' | 'loss'>('down_bps')
const gateway = computed(() => props.internet?.gateways[0] ?? null)
const series = computed<Record<string, TrafficPoint[]>>(() =>
  props.internet?.available ? { Internet: props.internet.series } : {})
const now = computed(() => [...(props.internet?.series ?? [])].reverse().find(x => x.down_bps != null) ?? null)
const quality = computed(() => props.internet?.quality ?? [])
const hasQuality = computed(() => quality.value.some(p => p.delay_ms != null))
const ms = (v: number) => `${v.toLocaleString('it-IT', { maximumFractionDigits: 1 })} ms`
const perc = (v: number) => `${v.toLocaleString('it-IT', { maximumFractionDigits: 1 })}%`
</script>

<template>
  <div v-if="!internet?.available" class="empty">
    <p>Lo stato della linea arriva da <strong>OPNsense</strong>.</p>
    <p class="muted small">Collegalo in <a href="#" @click.prevent="emit('settings')">Impostazioni</a>.</p>
  </div>
  <div v-else class="internet">
    <div class="section-head">
      <h2>Internet <span class="muted small">{{ gateway?.name }}</span></h2>
      <span v-if="gateway" class="badge" :class="gateway.online ? 'ok' : 'ko'">{{ gateway.online ? 'Online' : gateway.status }}</span>
      <div class="seg">
        <button :class="{ active: metric === 'down_bps' }" @click="metric = 'down_bps'">Download</button>
        <button :class="{ active: metric === 'up_bps' }" @click="metric = 'up_bps'">Upload</button>
        <button :class="{ active: metric === 'delay' }" @click="metric = 'delay'">Latenza</button>
        <button :class="{ active: metric === 'loss' }" @click="metric = 'loss'">Perdita</button>
      </div>
    </div>
    <div class="kpis inner">
      <div class="kpi"><span>Latenza</span><strong>{{ gateway?.delay || '—' }}</strong></div>
      <div class="kpi"><span>Pacchetti persi</span><strong>{{ gateway?.loss || '—' }}</strong></div>
      <div class="kpi"><span>Disponibilità {{ periodLabel }}</span>
        <strong :class="{ warn: internet.availability != null && internet.availability < 99.9 }">
          {{ internet.availability != null ? perc(internet.availability) : '—' }}</strong></div>
      <div class="kpi"><span>Download ora</span><strong>{{ bps(now?.down_bps) }}</strong></div>
      <div class="kpi"><span>Upload ora</span><strong>{{ bps(now?.up_bps) }}</strong></div>
      <div class="kpi"><span>Scaricati · inviati</span><strong class="small-num">{{ bytes(internet.period.down) }} · {{ bytes(internet.period.up) }}</strong></div>
    </div>
    <div class="internet-body">
      <div class="grow">
        <template v-if="metric === 'down_bps' || metric === 'up_bps'">
          <TrafficChart v-if="internet.series.some(p => p.down_bps != null)" :series="series" :metric="metric === 'up_bps' ? 'up_bps' : 'down_bps'" />
          <p v-else class="muted small">Il grafico della linea si popola dopo qualche minuto.</p>
        </template>
        <template v-else>
          <LineChart v-if="hasQuality" :ts="quality.map(p => p.ts)" zero
                     :datasets="[metric === 'delay'
                       ? { label: 'Latenza', data: quality.map(p => p.delay_ms), color: '#f59e0b' }
                       : { label: 'Perdita', data: quality.map(p => p.loss_pct), color: '#ef4444' }]"
                     :format="metric === 'delay' ? ms : perc" />
          <p v-else class="muted small">Lo storico di latenza e perdita si popola dopo qualche minuto.</p>
        </template>
      </div>
      <div class="outages">
        <h3 class="small">Disservizi {{ periodLabel }}</h3>
        <p v-if="!internet.outages.length" class="muted small">Nessuna interruzione della linea.</p>
        <ul v-else class="rows">
          <li v-for="o in internet.outages" :key="o.start">
            <span class="status" :class="o.end ? 'off' : 'off pulse'" />
            <span class="mono small">{{ time(o.start) }}</span>
            <span>{{ o.end ? duration(o.duration) : `in corso da ${duration(o.duration)}` }}</span>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>
