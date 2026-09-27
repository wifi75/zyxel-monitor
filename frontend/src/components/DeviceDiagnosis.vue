<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { api, type Diagnosis } from '../api'
import { time } from '../format'
import { t } from '../i18n'

/** Diagnosi di un dispositivo: esito in parole semplici, numeri chiave e cronologia con il segnale ai distacchi. */
const props = defineProps<{ mac: string; name: string }>()
const hours = ref(24)
const d = ref<Diagnosis | null>(null)
const error = ref('')

async function load() {
  d.value = null
  try { d.value = await api.diagnosis(props.mac, hours.value); error.value = '' } catch (e) { error.value = (e as Error).message }
}
onMounted(load)
watch(hours, load)

const KIND: Record<string, string> = { connect: 'Collegato', disconnect: 'Scollegato', roam: 'Cambio AP', new_device: 'Nuovo' }
const CAUSE: Record<string, string> = {
  weak: 'segnale debole', config: 'AP riconfigurato', ap: 'AP spento', other: '',
}
const sig = (v: number | null | undefined) => (v == null ? '' : v >= -60 ? 'good' : v >= -67 ? 'ok' : v >= -75 ? 'weak' : 'bad')
</script>

<template>
  <section class="diag">
    <div class="diag-head">
      <strong>{{ t('Diagnosi di {n}', { n: name }) }}</strong>
      <div class="seg">
        <button :class="{ active: hours === 24 }" @click="hours = 24">{{ t('24 ore') }}</button>
        <button :class="{ active: hours === 168 }" @click="hours = 168">{{ t('7 giorni') }}</button>
      </div>
    </div>
    <p v-if="error" class="error small">{{ error }}</p>
    <p v-else-if="!d" class="muted small">{{ t('Caricamento…') }}</p>
    <template v-else>
      <ul class="findings">
        <li v-for="(f, i) in d.findings" :key="i" :class="f.level">
          <strong>{{ t(f.title) }}</strong>
          <span>{{ f.text }}</span>
          <span v-if="f.fix" class="fix">→ {{ f.fix }}</span>
        </li>
      </ul>
      <div class="nums">
        <div><span>{{ t('Scollegamenti') }}</span><strong>{{ d.stats.drops }}</strong></div>
        <div><span>{{ t('Cambi di AP') }}</span><strong>{{ d.stats.roams }}</strong></div>
        <div><span>{{ t('Connessione tipica') }}</span><strong>{{ d.stats.median_session_min != null ? `${d.stats.median_session_min} min` : '—' }}</strong></div>
        <div><span>{{ t('Segnale ai distacchi') }}</span><strong :class="sig(d.stats.rssi_at_drop)">{{ d.stats.rssi_at_drop != null ? `${d.stats.rssi_at_drop} dBm` : '—' }}</strong></div>
        <div><span>{{ t('Soglia di espulsione') }}</span><strong>{{ d.stats.kickout != null ? `${d.stats.kickout} dBm` : t('spenta') }}</strong></div>
      </div>
      <details v-if="d.timeline.length">
        <summary class="small">{{ t('Cronologia ({n} eventi)', { n: d.timeline.length }) }}</summary>
        <div class="table-wrap">
          <table class="compact">
            <thead><tr><th>{{ t('Quando') }}</th><th>{{ t('Evento') }}</th><th>AP</th><th>{{ t('Segnale') }}</th><th>{{ t('Causa probabile') }}</th></tr></thead>
            <tbody>
              <tr v-for="e in d.timeline" :key="e.id" :class="{ drop: e.kind === 'disconnect' }">
                <td class="mono small">{{ time(e.ts) }}</td>
                <td>{{ t(KIND[e.kind] ?? e.kind) }}<span v-if="e.kind === 'connect' && e.info" class="muted small"> · {{ e.info }}</span></td>
                <td>{{ e.ap || '—' }}</td>
                <td><span v-if="e.rssi != null" class="sig" :class="sig(e.rssi)">{{ e.rssi }} dBm</span></td>
                <td class="small">{{ e.cause ? t(CAUSE[e.cause] ?? '') : '' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </details>
    </template>
  </section>
</template>

<style scoped>
/* resta dentro lo schermo anche se la tabella dei dispositivi scorre di lato */
.diag { display: grid; gap: 10px; margin-bottom: 12px; position: sticky; left: 0; max-width: min(1100px, calc(100vw - 340px)); }
.diag-head { display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; }
.findings { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.findings li { display: grid; gap: 2px; padding: 8px 12px; border-radius: var(--radius); border-left: 4px solid var(--good);
  background: color-mix(in srgb, var(--good) 10%, var(--surface)); font-size: 13px; }
.findings li.warn { border-left-color: var(--weak); background: color-mix(in srgb, var(--weak) 10%, var(--surface)); }
.findings li.bad { border-left-color: var(--bad); background: color-mix(in srgb, var(--bad) 9%, var(--surface)); }
.fix { font-weight: 600; }
.nums { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px; }
.nums div { display: grid; gap: 2px; padding: 8px 10px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface); }
.nums span { font-size: 12px; color: var(--muted); }
.nums strong { font-family: var(--font-mono); font-size: 17px; }
.nums .good { color: var(--good); } .nums .ok { color: var(--ok); } .nums .weak { color: var(--weak); } .nums .bad { color: var(--bad); }
table.compact td, table.compact th { padding: 4px 8px; }
tr.drop td { background: color-mix(in srgb, var(--bad) 5%, transparent); }
details summary { cursor: pointer; }
</style>
