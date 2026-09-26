<script setup lang="ts">
import type { IconName } from '../icons'
import Icon from './Icon.vue'

/** Stato vuoto: icona, spiegazione e, se serve, il pulsante per risolvere (es. "Collega OPNsense"). */
defineProps<{ icon: IconName; text: string; hint?: string; action?: string }>()
const emit = defineEmits<{ action: [] }>()
</script>

<template>
  <div class="empty-state">
    <span class="es-ico"><Icon :name="icon" :size="20" /></span>
    <p class="es-text">{{ text }}</p>
    <p v-if="hint" class="muted small">{{ hint }}</p>
    <button v-if="action" class="ghost small" @click="emit('action')">{{ action }}</button>
  </div>
</template>

<style scoped>
.empty-state { display: grid; justify-items: center; align-content: center; gap: 6px; text-align: center; padding: 14px 8px; flex: 1; }
.es-ico { width: 40px; height: 40px; display: grid; place-items: center; border-radius: 50%;
  color: var(--muted); background: var(--surface-2); }
.es-text { margin: 0; font-size: 14px; }
.empty-state p { margin: 0; }
</style>
