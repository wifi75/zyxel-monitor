<script setup lang="ts">
import { computed } from 'vue'
import { locale, t } from '../i18n'

/**
 * roaming per access point: una riga per AP con quanti dispositivi arrivano e quanti se ne vanno,
 * e da/verso quali AP; "rimbalza" quando andata e ritorno con lo stesso AP superano la soglia
 */
const props = defineProps<{
  pairs: { from: string; to: string; count: number }[]
  threshold: number
}>()

interface Link { ap: string; n: number; bounce: boolean }

const rows = computed(() => {
  const count = (a: string, b: string) => props.pairs.find(p => p.from === a && p.to === b)?.count ?? 0
  const aps = [...new Set(props.pairs.flatMap(p => [p.from, p.to]))]
  const sortDesc = (l: Link[]) => l.filter(x => x.n > 0).sort((a, b) => b.n - a.n)
  return aps.map(ap => {
    const bounce = (o: string) => Math.min(count(ap, o), count(o, ap)) >= props.threshold
    const others = aps.filter(o => o !== ap)
    const inn = sortDesc(others.map(o => ({ ap: o, n: count(o, ap), bounce: bounce(o) })))
    const out = sortDesc(others.map(o => ({ ap: o, n: count(ap, o), bounce: bounce(o) })))
    const sum = (l: Link[]) => l.reduce((s, x) => s + x.n, 0)
    return { ap, inn, out, nIn: sum(inn), nOut: sum(out) }
  }).sort((a, b) => b.nIn + b.nOut - a.nIn - a.nOut)
})
const total = computed(() => props.pairs.reduce((s, p) => s + p.count, 0))
const fmt = (v: number) => v.toLocaleString(locale())
</script>

<template>
  <div class="roam-ap">
    <p class="muted small">{{ t(total === 1 ? '{n} spostamento' : '{n} spostamenti', { n: fmt(total) }) }}</p>
    <div class="roam-row head">
      <span>{{ t('Access point') }}</span><span>{{ t('Arrivano da') }}</span><span>{{ t('Vanno verso') }}</span>
    </div>
    <div v-for="r in rows" :key="r.ap" class="roam-row">
      <strong :title="r.ap">{{ r.ap }}</strong>
      <div class="flow">
        <span class="tot in">↘ {{ fmt(r.nIn) }}</span>
        <span v-for="l in r.inn" :key="l.ap" class="chip in" :class="{ bounce: l.bounce }">{{ l.ap }} <b>{{ fmt(l.n) }}</b></span>
      </div>
      <div class="flow">
        <span class="tot out">↗ {{ fmt(r.nOut) }}</span>
        <span v-for="l in r.out" :key="l.ap" class="chip out" :class="{ bounce: l.bounce }">{{ l.ap }} <b>{{ fmt(l.n) }}</b></span>
      </div>
    </div>
    <p v-if="rows.some(r => r.inn.some(l => l.bounce))" class="muted small">
      <span class="chip bounce">⇄</span>
      {{ t('I dispositivi vanno e tornano fra questi due AP: valuta di ridurre la potenza radio di uno dei due') }}
    </p>
  </div>
</template>
