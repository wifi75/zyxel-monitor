<script setup lang="ts">
/** Logo: access point a disco con le onde del segnale che si propagano (animate se richiesto). */
withDefaults(defineProps<{ size?: number; animated?: boolean }>(), { size: 40, animated: false })
</script>

<template>
  <svg class="app-logo" :class="{ animated }" :width="size" :height="size" viewBox="0 0 64 64" aria-hidden="true">
    <g class="waves" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round">
      <path class="w3" d="M10 30a31 31 0 0 1 44 0" />
      <path class="w2" d="M18 37a20 20 0 0 1 28 0" />
      <path class="w1" d="M26 44a9 9 0 0 1 12 0" />
    </g>
    <ellipse class="disc" cx="32" cy="54" rx="14" ry="4.5" />
    <circle class="led" cx="32" cy="54" r="1.8" />
  </svg>
</template>

<style scoped>
.app-logo { color: var(--accent); display: block; flex: none; }
.disc { fill: var(--accent); }
.led { fill: var(--good); }
.animated .waves path { opacity: .15; animation: wave 1.8s var(--ease, ease-in-out) infinite; }
.animated .w1 { animation-delay: 0s; }
.animated .w2 { animation-delay: .25s; }
.animated .w3 { animation-delay: .5s; }
.animated .led { animation: blink 1.8s ease-in-out infinite; }
@keyframes wave { 0%, 100% { opacity: .15; } 30%, 60% { opacity: 1; } }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: .35; } }
@media (prefers-reduced-motion: reduce) {
  .animated .waves path, .animated .led { animation: none; opacity: 1; }
}
</style>
