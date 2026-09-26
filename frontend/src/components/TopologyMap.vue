<script setup lang="ts">
import { computed } from 'vue'
import type { Ap, Client, Internet } from '../api'
import { t } from '../i18n'
import Icon from './Icon.vue'
import { apColor } from '../apColors'

/** Mappa della rete: Internet → router → access point → client per banda. Un clic sull'AP apre il dettaglio. */
const props = defineProps<{ aps: Ap[]; clients: Client[]; internet: Internet | null }>()
const emit = defineEmits<{ open: [ap: string] }>()

const gateway = computed(() => props.internet?.gateways?.[0] ?? null)
const lineState = computed(() => !props.internet?.available ? 'idle' : gateway.value?.online ? 'on' : 'off')

const nodes = computed(() => props.aps.map(a => {
  const mine = props.clients.filter(c => c.ap === a.ap)
  const bands = new Map<string, number>()
  for (const c of mine) bands.set(c.band || '?', (bands.get(c.band || '?') ?? 0) + 1)
  const weak = mine.filter(c => c.rssi_dbm != null && c.rssi_dbm < -75).length
  return { ap: a, total: mine.length, weak, bands: [...bands].sort() }
}))
</script>

<template>
  <h2>{{ t('Mappa della rete') }}</h2>
  <div class="topo">
    <div class="node root" :class="lineState">
      <Icon name="globe" :size="16" />
      <div>
        <strong>Internet</strong>
        <span class="muted small">
          <template v-if="gateway">{{ gateway.name }} · {{ gateway.delay || '—' }}</template>
          <template v-else>{{ t('stato non disponibile') }}</template>
        </span>
      </div>
    </div>
    <div class="link" />
    <div class="node root on">
      <Icon name="router" :size="16" />
      <div><strong>{{ t('Router') }}</strong><span class="muted small">{{ t('rete di casa') }}</span></div>
    </div>
    <div class="link" />
    <ul class="leaves">
      <li v-for="n in nodes" :key="n.ap.ap">
        <button class="node ap" :class="n.ap.online ? 'on' : 'off'" :style="{ '--ap': apColor(n.ap.ap) }" @click="emit('open', n.ap.ap)">
          <Icon name="wifi" :size="16" />
          <div>
            <strong>{{ n.ap.ap }}</strong>
            <span class="muted small">{{ n.ap.online ? t('{n} client', { n: n.total }) : t('offline') }}</span>
            <span class="bands">
              <span v-for="[band, count] in n.bands" :key="band" class="band">{{ band.replace('GHz', '') }}: {{ count }}</span>
              <span v-if="n.weak" class="band weak" :title="t('Dispositivi con segnale debole')">⚠ {{ n.weak }}</span>
            </span>
          </div>
        </button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.topo { display: flex; flex-direction: column; align-items: center; gap: 0; padding: 4px 0; }
.node { display: flex; align-items: center; gap: 8px; padding: 6px 12px; border: 1px solid var(--border);
  border-left: 3px solid var(--muted); border-radius: var(--radius); background: var(--surface); text-align: left;
  color: var(--text); font: inherit; min-width: 0; }
.node > div { display: flex; flex-direction: column; min-width: 0; }
.node.on { border-left-color: var(--good); }
.node.off { border-left-color: var(--bad); }
.node.ap { width: 100%; cursor: pointer; border-left-color: var(--ap); }
.node.ap.off { border-left-color: var(--bad); }
.node.ap:hover { border-color: var(--accent); }
.link { width: 2px; height: 14px; background: var(--border); }
.leaves { list-style: none; margin: 0; padding: 10px 0 0; width: 100%; border-top: 2px solid var(--border);
  display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; }
.bands { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 2px; }
.band { font-size: 11px; padding: 0 6px; border-radius: 99px; background: var(--surface-2); color: var(--muted); }
.band.weak { color: var(--weak); }
</style>
