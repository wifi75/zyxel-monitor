<script setup lang="ts">
import { Chart, type ChartConfiguration, registerables } from 'chart.js'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { locale } from '../i18n'
import { seriesColor, soft, themeKey } from '../chartColors'
import type { TrafficPoint } from '../api'
import { bps } from '../format'

Chart.register(...registerables)

const props = defineProps<{
  series: Record<string, TrafficPoint[]>
  metric: 'down_bps' | 'up_bps' | 'clients'
}>()

const canvas = ref<HTMLCanvasElement>()
let chart: Chart | null = null

function build(): ChartConfiguration<'line'> {
  const aps = Object.keys(props.series)
  const labels = (props.series[aps[0]] ?? []).map(p =>
    new Date(p.ts * 1000).toLocaleTimeString(locale(), { hour: '2-digit', minute: '2-digit' }))
  const css = getComputedStyle(document.documentElement)
  const grid = css.getPropertyValue('--grid').trim()
  const text = css.getPropertyValue('--muted').trim()
  return {
    type: 'line',
    data: {
      labels,
      datasets: aps.map((ap, i) => ({
        label: ap,
        data: props.series[ap].map(p => p[props.metric]),
        borderColor: seriesColor(i),
        backgroundColor: soft(seriesColor(i)),
        borderWidth: 2, pointRadius: 0, tension: 0.3, spanGaps: true,
      })),
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { labels: { color: text, boxWidth: 12 } },
        tooltip: {
          callbacks: {
            label: c => `${c.dataset.label}: ${props.metric === 'clients' ? c.parsed.y : bps(c.parsed.y)}`,
          },
        },
      },
      scales: {
        x: { ticks: { color: text, maxTicksLimit: 8 }, grid: { color: grid } },
        y: {
          beginAtZero: true, grid: { color: grid },
          ticks: { color: text, callback: v => (props.metric === 'clients' ? v : bps(Number(v))) },
        },
      },
    },
  }
}

function render() {
  chart?.destroy()
  if (canvas.value) chart = new Chart(canvas.value, build())
}

onMounted(render)
watch(() => [props.series, props.metric, themeKey()], render)
onBeforeUnmount(() => chart?.destroy())
</script>

<template>
  <div class="chart-box"><canvas ref="canvas" /></div>
</template>
