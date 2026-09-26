<script setup lang="ts">
import { computed } from 'vue'
import type { Ap } from '../api'
import { t } from '../i18n'

/** Firmware per modello: AP dello stesso modello con versioni diverse vanno allineati (da Nebula). */
const props = defineProps<{ aps: Ap[] }>()

const models = computed(() => {
  const m = new Map<string, Ap[]>()
  for (const a of props.aps) {
    const k = a.model || t('modello non letto')
    m.set(k, [...(m.get(k) ?? []), a])
  }
  return [...m].map(([model, list]) => {
    const versions = [...new Set(list.map(a => a.firmware).filter(Boolean))] as string[]
    return { model, list, mixed: versions.length > 1, versions }
  })
})
</script>

<template>
  <h2>{{ t('Firmware') }}</h2>
  <div class="table-wrap">
    <table class="compact">
      <thead><tr><th>{{ t('Modello') }}</th><th>AP</th><th>{{ t('Versione') }}</th></tr></thead>
      <tbody>
        <template v-for="g in models" :key="g.model">
          <tr v-for="a in g.list" :key="a.ap">
            <td>{{ g.model }}</td>
            <td>{{ a.ap }}</td>
            <td class="mono small">
              {{ a.firmware || '—' }}
              <span v-if="g.mixed" class="badge ko" :title="t('Gli AP di questo modello hanno versioni diverse')">{{ t('diverso') }}</span>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>
  <p class="muted small">{{ t('Aggiornamenti del firmware da Nebula.') }}</p>
</template>

<style scoped>
table.compact td, table.compact th { padding: 4px 8px; vertical-align: top; }
</style>
