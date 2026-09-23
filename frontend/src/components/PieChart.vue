<script setup lang="ts">
import { Chart, registerables } from 'chart.js'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

Chart.register(...registerables)

const props = defineProps<{
  items: { label: string; value: number }[]
  format?: (v: number) => string
}>()

const PALETTE = ['#3b82f6', '#10b981', '#f59e0b', '#a855f7', '#ef4444', '#14b8a6', '#ec4899', '#84cc16', '#64748b', '#f97316']
const canvas = ref<HTMLCanvasElement>()
let chart: Chart | null = null

function render() {
  chart?.destroy()
  if (!canvas.value) return
  const css = getComputedStyle(document.documentElement)
  const fmt = props.format ?? ((v: number) => String(v))
  const total = props.items.reduce((s, i) => s + i.value, 0) || 1
  chart = new Chart(canvas.value, {
    type: 'doughnut',
    data: {
      labels: props.items.map(i => i.label),
      datasets: [{
        data: props.items.map(i => i.value),
        backgroundColor: props.items.map((_, i) => PALETTE[i % PALETTE.length]),
        borderColor: css.getPropertyValue('--surface').trim(),
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false, cutout: '58%',
      plugins: {
        legend: { position: 'right', labels: { color: css.getPropertyValue('--muted').trim(), boxWidth: 12 } },
        tooltip: {
          callbacks: { label: c => `${c.label}: ${fmt(c.parsed)} (${Math.round((c.parsed / total) * 100)}%)` },
        },
      },
    },
  })
}

onMounted(render)
watch(() => props.items, render, { deep: true })
onBeforeUnmount(() => chart?.destroy())
</script>

<template>
  <div class="pie-box"><canvas ref="canvas" /></div>
</template>
