<script setup lang="ts">
import { Chart, type ChartConfiguration, registerables } from 'chart.js'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { locale } from '../i18n'
import { cssColor, seriesColor, soft, themeKey } from '../chartColors'

Chart.register(...registerables)

/** Linee generiche su un asse temporale (segnale, latenza, perdita). */
const props = defineProps<{
  ts: number[]
  /** color: esplicito o variabile del tema ("--bad"); senza, la serie N del tema */
  datasets: { label: string; data: (number | null)[]; color?: string }[]
  format: (v: number) => string
  zero?: boolean
}>()

const canvas = ref<HTMLCanvasElement>()
let chart: Chart | null = null

function build(): ChartConfiguration<'line'> {
  const css = getComputedStyle(document.documentElement)
  const grid = css.getPropertyValue('--grid').trim()
  const text = css.getPropertyValue('--muted').trim()
  const multiDay = props.ts.length > 1 && props.ts[props.ts.length - 1] - props.ts[0] > 86400
  return {
    type: 'line',
    data: {
      labels: props.ts.map(t => new Date(t * 1000).toLocaleString(locale(), multiDay
        ? { day: '2-digit', month: '2-digit', hour: '2-digit' } : { hour: '2-digit', minute: '2-digit' })),
      datasets: props.datasets.map((d, i) => {
        const c = cssColor(d.color ?? seriesColor(i))
        return { label: d.label, data: d.data, borderColor: c, backgroundColor: soft(c),
                 borderWidth: 2, pointRadius: 0, tension: 0.3, spanGaps: true }
      }),
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: props.datasets.length > 1, labels: { color: text, boxWidth: 12 } },
        tooltip: { callbacks: { label: c => `${c.dataset.label}: ${props.format(c.parsed.y ?? 0)}` } },
      },
      scales: {
        x: { ticks: { color: text, maxTicksLimit: 6 }, grid: { color: grid } },
        y: { beginAtZero: !!props.zero, grid: { color: grid },
             ticks: { color: text, maxTicksLimit: 5, callback: v => props.format(Number(v)) } },
      },
    },
  }
}

function render() {
  chart?.destroy()
  if (canvas.value) chart = new Chart(canvas.value, build())
}

onMounted(render)
watch(() => [props.ts, props.datasets, themeKey()], render)
onBeforeUnmount(() => chart?.destroy())
</script>

<template>
  <div class="chart-box"><canvas ref="canvas" /></div>
</template>
