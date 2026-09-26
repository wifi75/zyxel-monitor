<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { api, type Ap, type ChannelHistory, type ChannelIssue, type Channels } from '../api'
import { t } from '../i18n'
import LineChart from './LineChart.vue'

/** Canali e occupazione di ogni radio, sovrapposizioni fra AP e canali consigliati (solo consiglio). */
const props = defineProps<{ aps: Ap[] }>()
const data = ref<Channels | null>(null)
const error = ref('')

const history = ref<ChannelHistory | null>(null)
const hours = ref(24)
async function load() {
  try { data.value = await api.channels(); error.value = '' } catch (e) { error.value = (e as Error).message }
  history.value = await api.channelsHistory(hours.value).catch(() => history.value)
}
watch(hours, load)
/** serie dell'occupazione nel tempo per una banda, una linea per AP */
function trend(band: string) {
  const per = history.value?.bands[band]
  if (!per || !Object.values(per).some(v => v.some(x => x != null))) return null
  return Object.entries(per).map(([ap, data]) => ({ label: ap, data }))
}
const pct = (v: number) => `${v}%`
onMounted(load)
// si ricarica quando arriva una nuova lettura degli AP
watch(() => props.aps.map(a => a.updated).join(), load)

const bands = computed(() => Object.entries(data.value?.bands ?? {}).filter(([, b]) => b.radios.length))

function issueText(i: ChannelIssue): string {
  const aps = i.aps.join(', ')
  if (i.kind === 'same') return i.aps.length > 2
    ? t('{n} AP sullo stesso canale {ch} ({aps}): si disturbano a vicenda', { n: i.aps.length, aps, ch: i.channel ?? '?' })
    : t('{aps} sullo stesso canale {ch}: si disturbano', { aps, ch: i.channel ?? '?' })
  if (i.kind === 'overlap') return t('{aps} su canali che si sovrappongono', { aps })
  if (i.kind === 'unclean') return t('{aps} sul canale {ch}: in 2.4 GHz usa solo 1, 6 o 11', { aps, ch: i.channel ?? '?' })
  return t('{aps}: canale occupato al {pct}%', { aps, pct: i.pct ?? 0 })
}
const level = (pct: number | null) => pct == null ? '' : pct >= (data.value?.busy_pct ?? 60) ? 'bad' : pct >= 35 ? 'weak' : 'good'
</script>

<template>
  <div class="section-head">
    <h2>{{ t('Piano dei canali') }}</h2>
    <select v-model.number="hours" :title="t('Periodo del grafico')">
      <option :value="24">{{ t('24 ore') }}</option><option :value="168">{{ t('7 giorni') }}</option>
    </select>
  </div>
  <p v-if="error" class="error small">{{ error }}</p>
  <p v-else-if="!bands.length" class="muted">{{ t('Canali non ancora letti dagli AP.') }}</p>
  <div v-for="[band, b] in bands" :key="band" class="band-block">
    <h3 class="small">{{ band.replace('GHz', ' GHz') }}</h3>
    <div class="table-wrap">
      <table class="compact">
        <thead><tr><th>AP</th><th>{{ t('Canale') }}</th><th>{{ t('Occupazione') }}</th><th>{{ t('Client') }}</th><th>{{ t('Consigliato') }}</th></tr></thead>
        <tbody>
          <tr v-for="r in b.radios" :key="r.ap">
            <td>{{ r.ap }}</td>
            <td class="mono">{{ r.channel ?? '—' }}<span v-if="r.auto" class="muted small"> {{ t('auto') }}</span></td>
            <td>
              <span v-if="r.utilization != null" class="util" :class="level(r.utilization)">
                <span class="util-bar"><span :style="{ width: `${Math.min(100, r.utilization)}%` }" /></span>{{ r.utilization }}%
              </span>
              <span v-else class="muted small" :title="t('Questo AP non fornisce l’occupazione del canale')">—</span>
            </td>
            <td>{{ r.clients }}</td>
            <td class="mono">
              <strong v-if="b.changes[r.ap] != null" class="warn-text">{{ b.changes[r.ap] }}</strong>
              <span v-else class="muted">{{ t('ok') }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="trend(band)" class="trend">
      <LineChart :ts="history!.ts" :datasets="trend(band)!" :format="pct" zero />
    </div>
    <p v-else class="muted small">{{ t('Andamento dell’occupazione in raccolta: servono alcune ore.') }}</p>
    <ul v-if="b.issues.length" class="issues">
      <li v-for="(i, n) in b.issues" :key="n" class="small">{{ issueText(i) }}</li>
    </ul>
  </div>
  <p v-if="bands.some(([, b]) => Object.keys(b.changes).length)" class="muted small">
    {{ t('I canali consigliati vanno impostati in Nebula: finché la gestione dal pannello è spenta, qui non si invia nulla agli AP.') }}
  </p>
</template>

<style scoped>
.band-block + .band-block { margin-top: 10px; }
.trend { height: 150px; margin-top: 6px; }
.band-block h3 { margin: 0 0 4px; }
table.compact td, table.compact th { padding: 4px 8px; }
.util { display: inline-flex; align-items: center; gap: 6px; font-variant-numeric: tabular-nums; }
.util-bar { width: 56px; height: 6px; border-radius: 3px; background: var(--surface-2); overflow: hidden; display: inline-block; }
.util-bar span { display: block; height: 100%; background: var(--good); }
.util.weak .util-bar span { background: var(--weak); }
.util.bad .util-bar span { background: var(--bad); }
.issues { margin: 6px 0 0; padding-left: 18px; color: var(--weak); }
.warn-text { color: var(--weak); }
</style>
