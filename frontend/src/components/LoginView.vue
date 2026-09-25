<script setup lang="ts">
import { ref } from 'vue'
import { api, auth } from '../api'
import { t } from '../i18n'
import AppLogo from './AppLogo.vue'

const emit = defineEmits<{ done: [] }>()
const username = ref('admin')
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  busy.value = true
  error.value = ''
  try {
    const r = await api.login(username.value, password.value)
    auth.set(r.token)
    emit('done')
  } catch (e) {
    error.value = (e as Error).message || t('Accesso non riuscito')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="login">
    <form class="card login-card" @submit.prevent="submit">
      <div class="login-logo"><AppLogo :size="72" animated /></div>
      <div class="brand login-brand">Zyxel Monitor</div>
      <p class="muted">{{ t('Accedi per vedere access point, client e traffico.') }}</p>
      <label>{{ t('Utente') }}<input v-model="username" autocomplete="username" required /></label>
      <label>{{ t('Password') }}<input v-model="password" type="password" autocomplete="current-password" required /></label>
      <p v-if="error" class="error">{{ error }}</p>
      <button class="primary" :disabled="busy">{{ busy ? t('Accesso…') : t('Accedi') }}</button>
    </form>
  </div>
</template>
