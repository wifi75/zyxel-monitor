<script setup lang="ts">
import type { Event } from '../api'
import { time } from '../format'
import { t } from '../i18n'

defineProps<{ events: Event[]; showAp?: boolean }>()

const LABEL: Record<Event['kind'], string> = {
  connect: 'Connesso', disconnect: 'Disconnesso', roam: 'Roaming', ap_down: 'AP offline', ap_up: 'AP online',
  new_device: 'Nuovo dispositivo', wan_down: 'Linea caduta', wan_up: 'Linea tornata', config: 'Configurazione',
}
</script>

<template>
  <div class="table-wrap">
    <table>
      <thead><tr><th>{{ t('Quando') }}</th><th>{{ t('Evento') }}</th><th>{{ t('Dispositivo') }}</th><th v-if="showAp">AP</th><th>{{ t('Dettagli') }}</th></tr></thead>
      <tbody>
        <tr v-for="e in events" :key="e.id">
          <td class="mono small">{{ time(e.ts) }}</td>
          <td><span class="ev" :class="e.kind">{{ t(LABEL[e.kind]) }}</span></td>
          <td>{{ e.name || '—' }}</td>
          <td v-if="showAp">{{ e.ap || '—' }}</td>
          <td class="muted small">{{ e.info || '' }}</td>
        </tr>
        <tr v-if="!events.length"><td :colspan="showAp ? 5 : 4" class="muted">{{ t('Nessun evento registrato.') }}</td></tr>
      </tbody>
    </table>
  </div>
</template>
