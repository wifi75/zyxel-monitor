<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, type Role, type User } from '../api'
import { t } from '../i18n'

/** Utenti del pannello: chi è in sola lettura vede tutto ma non può cambiare nulla. */
const list = ref<User[] | null>(null)
const name = ref(''), pwd = ref(''), role = ref<Role>('viewer')
const msg = ref<{ ok: boolean; message: string } | null>(null)
const hidden = ref(false)          // l'elenco è solo per gli amministratori

async function load() {
  try { list.value = await api.users() } catch { hidden.value = true }
}
onMounted(load)

async function add() {
  try {
    await api.createUser(name.value.trim(), pwd.value, role.value)
    msg.value = { ok: true, message: t('Utente {n} creato.', { n: name.value.trim() }) }
    name.value = pwd.value = ''
    await load()
  } catch (e) { msg.value = { ok: false, message: (e as Error).message } }
}
async function remove(u: User) {
  if (!window.confirm(t('Eliminare l’utente {n}?', { n: u.username }))) return
  try { await api.deleteUser(u.username); await load() } catch (e) { msg.value = { ok: false, message: (e as Error).message } }
}
</script>

<template>
  <form v-if="!hidden" class="card ap-editor" @submit.prevent="add">
    <div class="section-head"><h2>{{ t('Utenti') }}</h2></div>
    <p class="muted small">{{ t('Gli utenti in sola lettura vedono dashboard, dispositivi e report, ma non possono cambiare AP, impostazioni o configurazione.') }}</p>
    <ul v-if="list" class="users">
      <li v-for="u in list" :key="u.username">
        <strong>{{ u.username }}</strong>
        <span class="badge" :class="u.role === 'admin' ? 'ok' : ''">{{ u.role === 'admin' ? t('amministratore') : t('sola lettura') }}</span>
        <span class="spacer" />
        <button type="button" class="ghost small danger" @click="remove(u)">{{ t('Elimina') }}</button>
      </li>
    </ul>
    <div class="grid">
      <label>{{ t('Nome utente') }}<input v-model="name" autocomplete="off" required minlength="2" /></label>
      <label>{{ t('Password (min. 10 caratteri)') }}<input v-model="pwd" type="password" autocomplete="new-password" required minlength="10" /></label>
      <label>{{ t('Tipo') }}
        <select v-model="role"><option value="viewer">{{ t('sola lettura') }}</option><option value="admin">{{ t('amministratore') }}</option></select>
      </label>
    </div>
    <div class="actions"><span class="spacer" /><button class="primary">{{ t('Aggiungi utente') }}</button></div>
    <p v-if="msg" class="note" :class="msg.ok ? 'ok' : 'ko'">{{ msg.message }}</p>
  </form>
</template>

<style scoped>
.users { list-style: none; margin: 0 0 12px; padding: 0; display: grid; gap: 6px; }
.users li { display: flex; align-items: center; gap: 8px; }
</style>
