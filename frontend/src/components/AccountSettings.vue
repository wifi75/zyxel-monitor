<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
import { t } from '../i18n'

/** Il mio account: cambio della password dell'utente con cui si è entrati. */
const emit = defineEmits<{ changed: [] }>()
const username = ref('')
const oldPwd = ref(''), newPwd = ref(''), again = ref('')
const msg = ref<{ ok: boolean; message: string } | null>(null)
const busy = ref(false)

onMounted(async () => { username.value = (await api.me().catch(() => null))?.username ?? '' })

async function save() {
  msg.value = null
  if (newPwd.value.length < 10) { msg.value = { ok: false, message: t('La nuova password deve avere almeno 10 caratteri.') }; return }
  if (newPwd.value !== again.value) { msg.value = { ok: false, message: t('Le due password non coincidono') }; return }
  busy.value = true
  try {
    await api.changePassword(oldPwd.value, newPwd.value)
    oldPwd.value = newPwd.value = again.value = ''
    msg.value = { ok: true, message: t('Password cambiata: dal prossimo accesso usa quella nuova.') }
    emit('changed')
  } catch (e) { msg.value = { ok: false, message: (e as Error).message } } finally { busy.value = false }
}
</script>

<template>
  <form class="card account" @submit.prevent="save">
    <div class="section-head"><h2>{{ t('Cambia password') }}</h2></div>
    <p class="muted small">{{ t('Utente') }}: <strong>{{ username || '—' }}</strong></p>
    <!-- per i gestori di password del browser: sanno a quale utente appartiene la password -->
    <input :value="username" type="text" name="username" autocomplete="username" hidden readonly />
    <label>{{ t('Password attuale') }}
      <input v-model="oldPwd" type="password" name="current-password" autocomplete="current-password" required />
    </label>
    <label>{{ t('Nuova password') }} <span class="muted">({{ t('almeno 10 caratteri') }})</span>
      <input v-model="newPwd" type="password" name="new-password" autocomplete="new-password" required />
    </label>
    <label>{{ t('Ripeti la nuova password') }}
      <input v-model="again" type="password" name="new-password-again" autocomplete="new-password" required />
    </label>
    <p v-if="msg" class="note" :class="msg.ok ? 'ok' : 'ko'">{{ msg.message }}</p>
    <div><button class="primary" :disabled="busy">{{ busy ? t('Attendi…') : t('Cambia password') }}</button></div>
  </form>
</template>

<style scoped>
.account { display: grid; gap: 14px; max-width: 440px; }
.account label { display: grid; gap: 6px; }
.account .section-head { margin: 0; }
.account p { margin: 0; }
</style>
