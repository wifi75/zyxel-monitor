<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { download } from '../api'
import { t } from '../i18n'
import { defOf } from '../widgets'
import Icon from './Icon.vue'

/**
 * Cornice di un widget: icona colorata accanto al titolo, menu "⋯" con le azioni (pagina collegata, CSV),
 * segnaposto animati finché i dati non sono arrivati. Il contenuto arriva dallo slot.
 */
const props = defineProps<{ id: string; editing: boolean; loading?: boolean }>()
const emit = defineEmits<{ remove: []; go: [view: string] }>()
const def = defOf(props.id)
const open = ref(false)
const close = () => { open.value = false }
document.addEventListener('click', close)
onBeforeUnmount(() => document.removeEventListener('click', close))
const hasMenu = !!(def?.link || def?.csv)
</script>

<template>
  <div class="widget card" :class="def?.tone ? `tone-${def.tone}` : ''">
    <div v-if="editing" class="widget-bar">
      <span>⠿ {{ t(def?.title ?? '') }}</span>
      <button class="ghost small" :title="t('Nascondi')" @click="emit('remove')">×</button>
    </div>
    <span v-if="def?.icon && !editing" class="w-ico"><Icon :name="def.icon" :size="15" /></span>
    <div v-if="hasMenu && !editing" class="w-menu" @click.stop>
      <button class="w-more" :title="t('Azioni')" :aria-expanded="open" @click="open = !open">⋯</button>
      <div v-if="open" class="w-drop" role="menu">
        <button v-if="def?.link" role="menuitem" @click="close(); emit('go', def.link.view)">{{ t(def.link.label) }}</button>
        <button v-if="def?.csv" role="menuitem" @click="close(); download(def.csv.path, def.csv.name)">{{ t('Esporta CSV') }}</button>
      </div>
    </div>
    <div class="widget-body" :class="{ 'has-ico': def?.icon && !editing }">
      <div v-if="loading" class="skeleton" aria-hidden="true"><span /><span /><span /></div>
      <slot v-else />
    </div>
  </div>
</template>

<style scoped>
.widget { position: relative; }
.w-ico { position: absolute; top: 12px; left: 14px; width: 26px; height: 26px; display: grid; place-items: center;
  border-radius: var(--radius-s); color: var(--tone, var(--accent)); background: color-mix(in srgb, var(--tone, var(--accent)) 14%, transparent); }
.widget-body.has-ico > :deep(h2:first-child), .widget-body.has-ico > :deep(.section-head:first-child),
.widget-body.has-ico > :deep(.internet:first-child > .section-head) { padding-left: 34px; min-height: 26px; }
.widget-body.has-ico > :deep(h2:first-child)::before, .widget-body.has-ico > :deep(.section-head:first-child h2)::before,
.widget-body.has-ico > :deep(.internet:first-child > .section-head h2)::before { display: none !important; }
/* titoli su una riga: il sottotitolo lungo si accorcia invece di finire sopra il contenuto */
.widget-body :deep(h2) { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: none; }
.w-menu { position: absolute; top: 10px; right: 10px; z-index: 5; }
.w-more { border: none; background: transparent; color: var(--muted); font-size: 18px; line-height: 1; padding: 2px 8px;
  border-radius: var(--radius-s); cursor: pointer; opacity: .55; }
.widget:hover .w-more, .w-more[aria-expanded="true"] { opacity: 1; background: var(--surface-2); }
.w-drop { position: absolute; right: 0; top: 28px; min-width: 180px; display: grid; padding: 4px; background: var(--surface);
  border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow-hover); }
.w-drop button { border: none; background: transparent; text-align: left; padding: 7px 10px; font: inherit; font-size: 13px;
  color: var(--text); border-radius: var(--radius-s); cursor: pointer; justify-content: flex-start; }
.w-drop button:hover { background: var(--surface-2); }
.skeleton { display: grid; gap: 10px; padding-top: 4px; }
.skeleton span { height: 14px; border-radius: 4px; background: linear-gradient(90deg, var(--surface-2) 25%, var(--border) 50%, var(--surface-2) 75%);
  background-size: 200% 100%; animation: shimmer 1.4s infinite linear; }
.skeleton span:nth-child(1) { width: 45%; height: 18px; }
.skeleton span:nth-child(2) { width: 90%; }
.skeleton span:nth-child(3) { width: 70%; }
@keyframes shimmer { from { background-position: 200% 0; } to { background-position: -200% 0; } }
@media (prefers-reduced-motion: reduce) { .skeleton span { animation: none; } }
</style>
