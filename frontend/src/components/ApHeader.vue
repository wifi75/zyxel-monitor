<script setup lang="ts">
import { computed } from 'vue'
import type { Ap } from '../api'
import { apColor } from '../apColors'
import { duration } from '../format'
import { t } from '../i18n'

/** Intestazione del singolo AP: stato, nome, modello e una tessera per banda (canale, client, occupazione). */
const props = defineProps<{ ap: Ap }>()
const emit = defineEmits<{ band: [band: string] }>()

const level = (pct: number | null | undefined) => pct == null ? '' : pct >= 60 ? 'bad' : pct >= 35 ? 'weak' : 'good'
const bands = computed(() => props.ap.radios.filter(r => r.band !== '?'))
</script>

<template>
  <section class="card ap-hero" :class="{ off: !ap.online }" :style="{ '--ap': apColor(ap.ap) }">
    <div class="who">
      <span class="status" :class="ap.online ? 'on' : 'off'" />
      <div>
        <h2>{{ ap.ap }}</h2>
        <p class="muted small">
          {{ ap.model || t('modello non letto') }} · <span class="mono">{{ ap.host }}</span> · {{ t('firmware') }} {{ ap.firmware || '—' }}
          · {{ ap.online ? t('acceso da {t}', { t: duration(ap.uptime_s) }) : t('offline') }}
        </p>
        <p v-if="ap.error" class="error small">{{ ap.error }}</p>
      </div>
    </div>
    <div class="band-tiles">
      <button v-for="r in bands" :key="r.band" class="band-tile" :title="t('Clicca per vedere i dispositivi su questa banda')"
              @click="emit('band', r.band)">
        <span class="bt-head"><b>{{ r.band.replace('GHz', ' GHz') }}</b>
          <span class="muted">{{ r.channel ? t('canale {n}', { n: r.channel }) : r.channel_auto ? t('canale auto') : '—' }}</span></span>
        <span class="bt-num">{{ r.clients }} <small>{{ t('client') }}</small></span>
        <span v-if="r.utilization != null" class="bt-util" :class="level(r.utilization)">
          <span class="bt-bar"><span :style="{ width: `${Math.min(100, r.utilization)}%` }" /></span>
          <small>{{ t('occupato {p}%', { p: r.utilization }) }}</small>
        </span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.ap-hero { display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap;
  border-left: 4px solid var(--ap) !important; }
.ap-hero.off { border-left-color: var(--bad) !important; }
.who { display: flex; gap: 12px; align-items: flex-start; min-width: 0; }
.who .status { margin-top: 8px; }
.who h2 { margin: 0; font-size: 22px; }
.who p { margin: 2px 0 0; }
.band-tiles { display: flex; gap: 10px; flex-wrap: wrap; }
.band-tile { display: grid; gap: 4px; min-width: 150px; padding: 8px 12px; text-align: left; font: inherit; color: var(--text);
  background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--radius); cursor: pointer; }
.band-tile:hover { border-color: var(--ap); }
.bt-head { display: flex; justify-content: space-between; gap: 10px; font-size: 12px; }
.bt-num { font-family: var(--font-mono); font-size: 20px; font-weight: 700; }
.bt-num small { font-size: 12px; font-weight: 500; color: var(--muted); font-family: var(--font); }
.bt-util { display: grid; gap: 2px; font-size: 11px; color: var(--muted); }
.bt-bar { height: 5px; border-radius: 3px; background: var(--border); overflow: hidden; }
.bt-bar span { display: block; height: 100%; background: var(--good); }
.bt-util.weak .bt-bar span { background: var(--weak); }
.bt-util.bad .bt-bar span { background: var(--bad); }
</style>
