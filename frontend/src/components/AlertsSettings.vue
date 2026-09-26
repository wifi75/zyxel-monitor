<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api, type AlertForm, type AlertSettings } from '../api'
import { t } from '../i18n'

/** Avvisi su Telegram: bot, chat, quali eventi e report del lunedì. */
const cur = ref<AlertSettings | null>(null)
const form = reactive<AlertForm>({ token: '', chat_id: '', kinds: [], weekly: true })
const busy = ref(false)
const msg = ref<{ ok: boolean; message: string } | null>(null)

const KIND_LABEL: Record<string, string> = {
  ap_down: 'AP offline', ap_up: 'AP di nuovo online', wan_down: 'Linea Internet caduta', wan_up: 'Linea Internet tornata',
  new_device: 'Dispositivo nuovo', config: 'Modifiche alla configurazione', busy: 'Canale saturo',
}

function fill(s: AlertSettings) {
  cur.value = s
  Object.assign(form, { token: '', chat_id: s.chat_id, kinds: [...s.kinds], weekly: s.weekly })
}
onMounted(async () => { try { fill(await api.alerts()) } catch (e) { msg.value = { ok: false, message: (e as Error).message } } })

async function run(fn: () => Promise<{ ok: boolean; message: string } | AlertSettings>) {
  busy.value = true
  try {
    const r = await fn()
    if ('message' in r) msg.value = r
    else { fill(r); msg.value = { ok: true, message: t('Salvato.') } }
  } catch (e) { msg.value = { ok: false, message: (e as Error).message } } finally { busy.value = false }
}
const save = () => run(() => api.saveAlerts(form))
const test = () => run(() => api.testAlerts(form))
const report = () => run(() => api.sendReport())
function removeToken() {
  if (window.confirm(t('Togliere il token del bot? Gli avvisi si fermano.'))) run(() => api.saveAlerts({ ...form, clear_token: true }))
}
</script>

<template>
  <form class="card ap-editor" @submit.prevent="save">
    <div class="section-head">
      <h2>{{ t('Avvisi su Telegram') }}</h2>
      <span v-if="cur" class="badge" :class="cur.enabled ? 'ok' : 'ko'">{{ cur.enabled ? t('attivi') : t('spenti') }}</span>
    </div>
    <p class="muted small">
      {{ t('Crea un bot con @BotFather e copia il token; scrivi un messaggio al bot e leggi l’id della chat da @userinfobot (per un gruppo, aggiungi il bot al gruppo).') }}
      {{ t('Un AP che sparisce per una sola lettura non genera avvisi.') }}
    </p>
    <div class="grid">
      <label>{{ t('Token del bot') }}
        <input v-model="form.token" type="password" autocomplete="new-password"
               :placeholder="cur?.has_token ? t('invariato — scrivi per cambiarlo') : '123456:ABC…'" />
      </label>
      <label>{{ t('Id della chat') }}<input v-model="form.chat_id" inputmode="numeric" placeholder="123456789" /></label>
    </div>
    <fieldset class="kinds">
      <legend class="muted small">{{ t('Avvisami per') }}</legend>
      <label v-for="k in cur?.all_kinds ?? []" :key="k" class="check inline">
        <input v-model="form.kinds" type="checkbox" :value="k" /> {{ t(KIND_LABEL[k] ?? k) }}
      </label>
      <label class="check inline"><input v-model="form.weekly" type="checkbox" /> {{ t('Report settimanale (lunedì mattina)') }}</label>
    </fieldset>
    <div class="actions">
      <button type="button" :disabled="busy" @click="test">{{ t('Invia prova') }}</button>
      <button type="button" :disabled="busy || !cur?.enabled" @click="report">{{ t('Invia il report adesso') }}</button>
      <button v-if="cur?.has_token" type="button" class="ghost danger" :disabled="busy" @click="removeToken">{{ t('Togli token') }}</button>
      <span class="spacer" />
      <button class="primary" :disabled="busy">{{ busy ? t('Attendi…') : t('Salva') }}</button>
    </div>
    <p v-if="msg" class="note" :class="msg.ok ? 'ok' : 'ko'">{{ msg.message }}</p>
  </form>
</template>

<style scoped>
.kinds { border: 0; padding: 0; margin: 12px 0; display: flex; flex-wrap: wrap; gap: 4px 0; }
.kinds legend { margin-bottom: 6px; }
</style>
