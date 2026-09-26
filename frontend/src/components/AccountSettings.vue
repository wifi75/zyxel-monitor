<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../api'
import { t } from '../i18n'

/** Il mio account: cambio della password dell'utente con cui si è entrati. */
const emit = defineEmits<{ changed: [] }>()
const oldPwd = ref(''), newPwd = ref(''), again = ref('')
const msg = ref<{ ok: boolean; message: string } | null>(null)
const busy = ref(false)

async function save() {
  if (newPwd.value !== again.value) { msg.value = { ok: false, message: t('Le due password non coincidono') }; return }
  busy.value = true
  try {
    await api.changePassword(oldPwd.value, newPwd.value)
    oldPwd.value = newPwd.value = again.value = ''
    msg.value = { ok: true, message: t('Password cambiata.') }
    emit('changed')
  } catch (e) { msg.value = { ok: false, message: (e as Error).message } } finally { busy.value = false }
}
</script>

<template>
  <form class="card ap-editor" @submit.prevent="save">
    <div class="section-head"><h2>{{ t('Cambia password') }}</h2></div>
    <div class="grid">
      <label>{{ t('Password attuale') }}<input v-model="oldPwd" type="password" autocomplete="current-password" required /></label>
      <label>{{ t('Nuova password (min. 10 caratteri)') }}<input v-model="newPwd" type="password" autocomplete="new-password" minlength="10" required /></label>
      <label>{{ t('ripeti la password') }}<input v-model="again" type="password" autocomplete="new-password" minlength="10" required /></label>
    </div>
    <div class="actions"><span class="spacer" /><button class="primary" :disabled="busy">{{ busy ? t('Attendi…') : t('Salva') }}</button></div>
    <p v-if="msg" class="note" :class="msg.ok ? 'ok' : 'ko'">{{ msg.message }}</p>
  </form>
</template>
