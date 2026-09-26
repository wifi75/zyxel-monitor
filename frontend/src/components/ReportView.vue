<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { api, type Report } from '../api'
import { bytes, time } from '../format'
import { t } from '../i18n'

/** Report del periodo: lo stesso che arriva il lunedì su Telegram, più dettagliato. */
const days = ref(7)
const rep = ref<Report | null>(null)
const error = ref('')
const sent = ref<{ ok: boolean; message: string } | null>(null)

async function load() {
  try { rep.value = await api.report(days.value); error.value = '' } catch (e) { error.value = (e as Error).message }
}
onMounted(load)
watch(days, load)

async function send() {
  try { sent.value = await api.sendReport() } catch (e) { sent.value = { ok: false, message: (e as Error).message } }
}
const avail = (v: number | null) => (v == null ? '—' : `${v}%`)
const level = (v: number) => (v >= 99 ? 'good' : v >= 95 ? 'weak' : 'bad')
</script>

<template>
  <main>
    <section class="card">
      <div class="section-head">
        <h2>{{ t('Report') }}</h2>
        <div class="seg">
          <button :class="{ active: days === 1 }" @click="days = 1">{{ t('24 ore') }}</button>
          <button :class="{ active: days === 7 }" @click="days = 7">{{ t('7 giorni') }}</button>
          <button :class="{ active: days === 30 }" @click="days = 30">{{ t('30 giorni') }}</button>
        </div>
        <span class="spacer" />
        <button class="ghost" @click="send">{{ t('Invia su Telegram') }}</button>
      </div>
      <p v-if="rep" class="muted small">{{ t('Dal {a} al {b}', { a: time(rep.since), b: time(rep.until) }) }}</p>
      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="sent" class="note" :class="sent.ok ? 'ok' : 'ko'">{{ sent.message }}</p>
    </section>

    <template v-if="rep">
      <section class="kpis">
        <div class="kpi"><span>{{ t('Wi-Fi scaricati') }}</span><strong>{{ bytes(rep.wifi.down) }}</strong></div>
        <div class="kpi"><span>{{ t('Wi-Fi inviati') }}</span><strong>{{ bytes(rep.wifi.up) }}</strong></div>
        <div class="kpi"><span>{{ t('Linea disponibile') }}</span><strong>{{ avail(rep.internet.availability) }}</strong></div>
        <div class="kpi"><span>{{ t('Disservizi linea') }}</span><strong :class="{ warn: rep.internet.outages }">{{ rep.internet.outages }}</strong></div>
        <div class="kpi"><span>{{ t('Dispositivi nuovi') }}</span><strong :class="{ warn: rep.new_devices.length }">{{ rep.new_devices.length }}</strong></div>
      </section>

      <section class="card">
        <h2 class="mb">{{ t('Access point') }}</h2>
        <div class="table-wrap">
          <table>
            <thead><tr>
              <th>AP</th><th>{{ t('Online') }}</th><th>{{ t('Cadute') }}</th><th>{{ t('Client (media / picco)') }}</th>
              <th>{{ t('Traffico') }}</th><th>{{ t('Segnale medio') }}</th><th>{{ t('Letture deboli') }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="a in rep.aps" :key="a.ap">
                <td><strong>{{ a.ap }}</strong></td>
                <td><span class="sig" :class="level(a.availability)">{{ a.availability }}%</span></td>
                <td>{{ a.outages }}</td>
                <td>{{ a.avg_clients }} / {{ a.peak_clients }}</td>
                <td>{{ a.down + a.up ? bytes(a.down + a.up) : '—' }}</td>
                <td>{{ a.rssi != null ? `${a.rssi} dBm` : '—' }}</td>
                <td>{{ a.weak_pct != null ? `${a.weak_pct}%` : '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="muted small">{{ t('“Online” è la quota di letture riuscite nel periodo: un AP aggiunto da poco parte dalla sua prima lettura.') }}</p>
      </section>

      <div class="split">
        <section class="card">
          <h2 class="mb">{{ t('Dispositivi più presenti') }}</h2>
          <ol class="site-list">
            <li v-for="d in rep.busiest" :key="d.mac"><span>{{ d.name }}</span><span class="muted">{{ t('{h} ore', { h: d.hours }) }}</span></li>
          </ol>
          <p v-if="!rep.busiest.length" class="muted">{{ t('Nessun dato nel periodo.') }}</p>
        </section>
        <section class="card">
          <h2 class="mb">{{ t('Dispositivi nuovi') }}</h2>
          <ol class="site-list">
            <li v-for="d in rep.new_devices" :key="d.mac">
              <span>{{ d.name }} <span v-if="!d.known" class="badge ko">{{ t('da riconoscere') }}</span></span>
              <span class="muted">{{ time(d.first_seen) }}</span>
            </li>
          </ol>
          <p v-if="!rep.new_devices.length" class="muted">{{ t('Nessun dispositivo nuovo.') }}</p>
        </section>
        <section class="card">
          <h2 class="mb">{{ t('Linea Internet') }}</h2>
          <template v-if="rep.internet.available">
            <p>{{ t('Latenza media') }}: <strong>{{ rep.internet.delay_ms ?? '—' }} ms</strong></p>
            <p>{{ t('Perdita massima') }}: <strong>{{ rep.internet.max_loss ?? '—' }}%</strong></p>
            <p>{{ t('Scaricati') }}: <strong>{{ bytes(rep.internet.down) }}</strong> · {{ t('Inviati') }}: <strong>{{ bytes(rep.internet.up) }}</strong></p>
          </template>
          <p v-else class="muted">{{ t('Collega OPNsense per lo stato della linea.') }}</p>
          <p v-if="rep.bouncing.length" class="note ko">{{ t('{n} dispositivi rimbalzano spesso fra gli AP: potenze da rivedere.', { n: rep.bouncing.length }) }}</p>
        </section>
      </div>
    </template>
  </main>
</template>
