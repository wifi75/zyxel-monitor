<script setup lang="ts">
import { PATHS, type IconName } from '../icons'

/** Icona a tratto, colore dal testo. */
withDefaults(defineProps<{ name: IconName; size?: number }>(), { size: 18 })
</script>

<template>
  <svg class="icon" :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor"
       stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" v-html="PATHS[name]" />
</template>
