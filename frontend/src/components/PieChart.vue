<script setup lang="ts">
import { Chart, registerables } from 'chart.js'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { locale } from '../i18n'
import { seriesColor, themeKey } from '../chartColors'

Chart.register(...registerables)

/** Ciambella compatta: grafico piccolo a sinistra, legenda con valore e percentuale a destra. */
const props = defineProps<{
  items: { label: string; value: number }[]
  format?: (v: number) => string
  /** colori espliciti per voce (es. il colore fisso di ogni AP); senza, le serie del tema */
  colors?: string[]
}>()

// ricalcolati al cambio di tema, così legenda e ciambella restano uguali
const colors = computed(() => { themeKey(); return props.items.map((_, i) => props.colors?.[i] ?? seriesColor(i)) })
const canvas = ref<HTMLCanvasElement>()
let chart: Chart | null = null

const total = computed(() => props.items.reduce((s, i) => s + i.value, 0) || 1)
const fmt = (v: number) => (props.format ?? ((x: number) => x.toLocaleString(locale())))(v)
const pct = (v: number) => `${Math.round((v / total.value) * 100)}%`

function render() {
  chart?.destroy()
  if (!canvas.value) return
  const css = getComputedStyle(document.documentElement)
  chart = new Chart(canvas.value, {
    type: 'doughnut',
    data: {
      labels: props.items.map(i => i.label),
      datasets: [{
        data: props.items.map(i => i.value),
        backgroundColor: colors.value,
        borderColor: css.getPropertyValue('--surface').trim(),
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false, cutout: '62%',
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: c => `${c.label}: ${fmt(c.parsed)} (${pct(c.parsed)})` } },
      },
    },
  })
}

onMounted(render)
watch(() => props.items, render, { deep: true })
watch(themeKey, render)
onBeforeUnmount(() => chart?.destroy())
</script>

<template>
  <div class="pie">
    <div class="pie-canvas"><canvas ref="canvas" /></div>
    <ul class="pie-legend">
      <li v-for="(i, n) in items" :key="i.label" :title="i.label">
        <span class="swatch" :style="{ background: colors[n] }" />
        <span class="name">{{ i.label }}</span>
        <span class="value">{{ fmt(i.value) }}</span>
        <span class="muted pct">{{ pct(i.value) }}</span>
      </li>
    </ul>
  </div>
</template>
