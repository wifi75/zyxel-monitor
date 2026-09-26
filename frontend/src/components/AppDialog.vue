<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { closeDialog, dialog } from '../dialog'
import { t } from '../i18n'

/** Finestra di conferma o di inserimento del pannello, centrata e con i colori del tema. */
const field = ref<HTMLInputElement>()
const okBtn = ref<HTMLButtonElement>()
watch(dialog, async d => {
  if (!d) return
  await nextTick()
  if (d.input) { field.value?.focus(); field.value?.select() } else okBtn.value?.focus()
})
const ok = () => closeDialog(dialog.value?.input ? dialog.value.value : '')
</script>

<template>
  <Teleport to="body">
    <div v-if="dialog" class="dlg-backdrop" @click.self="closeDialog(null)" @keydown.esc="closeDialog(null)">
      <div class="dlg card" role="alertdialog" aria-modal="true">
        <p class="dlg-msg">{{ dialog.message }}</p>
        <input v-if="dialog.input" ref="field" v-model="dialog.value" @keyup.enter="ok" />
        <div class="actions">
          <span class="grow" />
          <button class="ghost" @click="closeDialog(null)">{{ t('Annulla') }}</button>
          <button ref="okBtn" class="primary" :class="{ danger: dialog.danger }" @click="ok">{{ dialog.input ? t('Salva') : t('Conferma') }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.dlg-backdrop { position: fixed; inset: 0; z-index: 100; display: grid; place-items: center; padding: 16px;
  background: color-mix(in srgb, var(--text) 30%, transparent); }
.dlg { width: min(460px, 100%); display: grid; gap: 14px; box-shadow: var(--shadow-hover) !important; }
.dlg-msg { margin: 0; white-space: pre-line; line-height: 1.45; }
.dlg input { width: 100%; box-sizing: border-box; }
.danger { background: var(--bad) !important; border-color: var(--bad) !important; }
</style>
