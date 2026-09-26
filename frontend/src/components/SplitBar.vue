<script setup lang="ts">
import { computed } from 'vue'
import { seriesColor, themeKey } from '../chartColors'

/** Poche categorie (es. bande radio): una barra divisa in proporzione e la legenda su una riga. */
const props = defineProps<{ items: { label: string; value: number }[] }>()

const total = computed(() => props.items.reduce((s, i) => s + i.value, 0) || 1)
const parts = computed(() => {
  themeKey()
  return props.items.map((i, n) => ({ ...i, pct: Math.round((i.value / total.value) * 100), color: seriesColor(n) }))
})
</script>

<template>
  <div class="split-bar">
    <div class="bar" role="img" :aria-label="parts.map(p => `${p.label} ${p.value}`).join(', ')">
      <span v-for="p in parts" :key="p.label" :style="{ width: `${p.pct}%`, background: p.color }" :title="`${p.label}: ${p.value}`" />
    </div>
    <ul class="legend">
      <li v-for="p in parts" :key="p.label">
        <span class="swatch" :style="{ background: p.color }" />
        <span>{{ p.label.replace('GHz', ' GHz') }}</span>
        <strong>{{ p.value }}</strong>
        <span class="muted">{{ p.pct }}%</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.split-bar { display: flex; flex-direction: column; gap: 10px; }
.bar { display: flex; height: 14px; border-radius: 7px; overflow: hidden; background: var(--surface-2); }
.bar span { display: block; height: 100%; min-width: 3px; }
.legend { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 13px; }
.legend li { display: flex; align-items: center; gap: 6px; }
.swatch { width: 10px; height: 10px; border-radius: 2px; }
</style>
