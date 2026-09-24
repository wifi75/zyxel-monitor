<script setup lang="ts">
import { computed } from 'vue'
import { locale, t } from '../i18n'

/**
 * spostamenti fra AP a coppie: andata e ritorno sulla stessa riga, ogni barra cresce verso l'AP di arrivo
 * e a destra va la direzione prevalente; "rimbalza" quando tutte e due arrivano alla soglia dei dispositivi
 */
const props = defineProps<{
  pairs: { from: string; to: string; count: number }[]
  threshold: number
}>()

interface Pair { key: string; left: string; right: string; toLeft: number; toRight: number }

const rows = computed(() => {
  const byPair = new Map<string, Pair>()
  for (const p of props.pairs) {
    const key = JSON.stringify([p.from, p.to].sort())
    const r = byPair.get(key)
    if (!r) byPair.set(key, { key, left: p.from, right: p.to, toLeft: 0, toRight: p.count })
    else if (r.left === p.from) r.toRight += p.count
    else r.toLeft += p.count
  }
  return [...byPair.values()]
    .map(r => (r.toLeft > r.toRight ? { ...r, left: r.right, right: r.left, toLeft: r.toRight, toRight: r.toLeft } : r))
    .map(r => ({ ...r, total: r.toLeft + r.toRight, bouncing: Math.min(r.toLeft, r.toRight) >= props.threshold }))
    .sort((a, b) => b.total - a.total || b.toRight - a.toRight)
})
const total = computed(() => rows.value.reduce((s, r) => s + r.total, 0))
const max = computed(() => Math.max(1, ...rows.value.map(r => r.toRight)))
const width = (v: number) => ({ width: `${(v / max.value) * 100}%` })
const fmt = (v: number) => v.toLocaleString(locale())
</script>

<template>
  <div class="roam-pairs">
    <p class="muted small">
      {{ t(total === 1 ? '{n} spostamento' : '{n} spostamenti', { n: fmt(total) }) }}
      · {{ t("ogni barra punta all'access point di arrivo") }}
    </p>
    <ol>
      <li v-for="r in rows" :key="r.key">
        <span class="ap left" :title="r.left">{{ r.left }}</span>
        <span class="n">{{ fmt(r.toLeft) }}</span>
        <span class="half to-left" :title="`${r.right} → ${r.left}: ${fmt(r.toLeft)}`"><span :style="width(r.toLeft)" /></span>
        <span class="half to-right" :title="`${r.left} → ${r.right}: ${fmt(r.toRight)}`"><span :style="width(r.toRight)" /></span>
        <span class="n">{{ fmt(r.toRight) }}</span>
        <span class="ap" :title="r.right">{{ r.right }}</span>
        <span class="tot">
          <span v-if="r.bouncing" class="badge ko"
                :title="t('I dispositivi vanno e tornano fra questi due AP: valuta di ridurre la potenza radio di uno dei due')">{{ t('rimbalza') }}</span>
          <strong>{{ fmt(r.total) }}</strong>
        </span>
      </li>
    </ol>
  </div>
</template>
