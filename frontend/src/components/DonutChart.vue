<script setup lang="ts">
import { computed, ref } from 'vue'
import { seriesColor, themeKey } from '../chartColors'

/**
 * Ciambella con il totale al centro e la legenda a fianco (pallino, nome, percentuale), come le schede di Nebula.
 * Passando su una fetta o su una riga della legenda il centro mostra quella voce.
 */
const props = defineProps<{
  items: { label: string; value: number }[]
  /** testo grande e piccolo al centro quando nessuna voce è evidenziata (es. "80.1" / "GB") */
  center: string; unit?: string
  format?: (v: number) => string
  size?: number
}>()

const R = 42, STROKE = 12, C = 2 * Math.PI * R
const hover = ref<number | null>(null)
const total = computed(() => props.items.reduce((s, i) => s + i.value, 0) || 1)
const slices = computed(() => {
  themeKey()
  let at = 0
  return props.items.map((i, n) => {
    const frac = i.value / total.value
    const gap = props.items.length > 1 ? Math.min(1.2, frac * C * 0.3) : 0     // sottile stacco fra le fette
    const s = { ...i, n, color: seriesColor(n), pct: frac * 100,
                dash: `${Math.max(0, frac * C - gap)} ${C}`, offset: -at * C }
    at += frac
    return s
  })
})
const pctText = (p: number) => (p >= 10 ? Math.round(p) : p.toFixed(1)) + '%'
const shown = computed(() => (hover.value == null ? null : slices.value[hover.value]))
</script>

<template>
  <div class="donut">
    <svg :width="size ?? 132" :height="size ?? 132" viewBox="0 0 100 100" role="img"
         :aria-label="items.map(i => `${i.label} ${i.value}`).join(', ')">
      <circle cx="50" cy="50" :r="R" fill="none" class="track" :stroke-width="STROKE" />
      <circle v-for="s in slices" :key="s.label" cx="50" cy="50" :r="R" fill="none" :stroke="s.color"
              :stroke-width="hover === s.n ? STROKE + 3 : STROKE" :stroke-dasharray="s.dash" :stroke-dashoffset="s.offset"
              transform="rotate(-90 50 50)" class="slice" @mouseenter="hover = s.n" @mouseleave="hover = null" />
      <text x="50" y="50" class="big" text-anchor="middle">{{ shown ? pctText(shown.pct) : center }}</text>
      <text x="50" y="63" class="small-t" text-anchor="middle">{{ shown ? (format ? format(shown.value) : shown.value) : unit }}</text>
    </svg>
    <ul class="donut-legend">
      <li v-for="s in slices" :key="s.label" :class="{ on: hover === s.n }" @mouseenter="hover = s.n" @mouseleave="hover = null">
        <span class="dot-c" :style="{ background: s.color }" />
        <span class="name" :title="s.label">{{ s.label }}</span>
        <span class="pct">{{ pctText(s.pct) }}</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.donut { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.donut svg { flex: none; }
.track { stroke: var(--surface-2); }
.slice { transition: stroke-width var(--t-fast, 120ms); cursor: default; }
.big { font: 700 17px var(--font-mono); fill: var(--text); }
.small-t { font: 600 8px var(--font); fill: var(--muted); }
.donut-legend { list-style: none; margin: 0; padding: 0; flex: 1; min-width: 160px; display: grid; gap: 4px; }
.donut-legend li { display: grid; grid-template-columns: 10px minmax(0, 1fr) auto; align-items: center; gap: 8px;
                   padding: 3px 6px; border-radius: var(--radius-s, 4px); font-size: 13px; }
.donut-legend li.on { background: var(--surface-2); }
.dot-c { width: 10px; height: 10px; border-radius: 50%; }
.name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pct { font-family: var(--font-mono); font-variant-numeric: tabular-nums; color: var(--muted); }
</style>
