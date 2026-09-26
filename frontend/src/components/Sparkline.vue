<script setup lang="ts">
import { computed } from 'vue'

/** Mini-linea dell'andamento recente (dentro gli indicatori): niente assi, solo la forma. */
const props = defineProps<{ values: (number | null)[]; color?: string }>()

const path = computed(() => {
  const pts = props.values.map((v, i) => [i, v] as const).filter((p): p is readonly [number, number] => p[1] != null)
  if (pts.length < 2) return ''
  const max = Math.max(...pts.map(p => p[1])) || 1
  const n = props.values.length - 1 || 1
  return pts.map(([i, v], k) => `${k ? 'L' : 'M'}${((i / n) * 100).toFixed(1)},${(28 - (v / max) * 26).toFixed(1)}`).join(' ')
})
</script>

<template>
  <svg v-if="path" class="spark" viewBox="0 0 100 30" preserveAspectRatio="none" aria-hidden="true">
    <path :d="`${path} L100,30 L0,30 Z`" class="area" :style="{ fill: color ?? 'var(--tone)' }" />
    <path :d="path" class="line" :style="{ stroke: color ?? 'var(--tone)' }" />
  </svg>
</template>

<style scoped>
.spark { width: 100%; height: 26px; display: block; }
.line { fill: none; stroke-width: 1.6; vector-effect: non-scaling-stroke; }
.area { opacity: .12; }
</style>
