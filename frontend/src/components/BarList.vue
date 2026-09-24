<script setup lang="ts">
import { computed } from 'vue'
import { locale } from '../i18n'

/** classifica a righe: nome intero, barra proporzionale al primo, valore */
const props = defineProps<{
  items: { label: string; value: number; title?: string }[]
  format?: (v: number) => string
}>()

const max = computed(() => Math.max(1, ...props.items.map(i => i.value)))
const fmt = (v: number) => (props.format ?? ((x: number) => x.toLocaleString(locale())))(v)
</script>

<template>
  <ol class="bar-list">
    <li v-for="(i, n) in items" :key="i.label" :title="i.title ? `${i.label} — ${i.title}` : i.label">
      <span class="rank">{{ n + 1 }}</span>
      <span class="name">{{ i.label }}</span>
      <span class="value">{{ fmt(i.value) }}</span>
      <span class="bar"><span :style="{ width: `${(i.value / max) * 100}%` }" /></span>
    </li>
  </ol>
</template>
