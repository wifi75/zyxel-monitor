<script setup lang="ts">
import type { Event } from '../api'
import { time } from '../format'

defineProps<{ events: Event[]; showAp?: boolean }>()

const LABEL: Record<Event['kind'], string> = {
  connect: 'Connesso', disconnect: 'Disconnesso', roam: 'Roaming', ap_down: 'AP offline', ap_up: 'AP online',
}
</script>

<template>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Quando</th><th>Evento</th><th>Dispositivo</th><th v-if="showAp">AP</th><th>Dettagli</th></tr></thead>
      <tbody>
        <tr v-for="e in events" :key="e.id">
          <td class="mono small">{{ time(e.ts) }}</td>
          <td><span class="ev" :class="e.kind">{{ LABEL[e.kind] }}</span></td>
          <td>{{ e.name || '—' }}</td>
          <td v-if="showAp">{{ e.ap || '—' }}</td>
          <td class="muted small">{{ e.info || '' }}</td>
        </tr>
        <tr v-if="!events.length"><td :colspan="showAp ? 5 : 4" class="muted">Nessun evento registrato.</td></tr>
      </tbody>
    </table>
  </div>
</template>
