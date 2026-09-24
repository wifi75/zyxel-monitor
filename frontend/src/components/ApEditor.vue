<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { api, apForm, type ApConfig, type ApTest, type Detect, type Secret } from '../api'
import { duration } from '../format'
import { t } from '../i18n'

const props = defineProps<{ ap: ApConfig | null; all: ApConfig[] }>()
const emit = defineEmits<{ saved: [copied: number]; cancel: [] }>()

const AUTH = ['SHA', 'SHA-256', 'SHA-512', 'SHA-224', 'SHA-384', 'MD5']
const PRIV = ['AES', 'AES-256', 'AES-192', 'DES']
const HAS = {
  snmp_community: 'has_snmp_community', snmp_auth_pass: 'has_snmp_auth_pass',
  snmp_priv_pass: 'has_snmp_priv_pass', ssh_password: 'has_ssh_password',
} as const

const form = reactive(apForm(props.ap))
const busy = ref<'' | 'save' | 'test' | 'detect'>('')
const result = ref<ApTest | null>(null)
const found = ref<Detect | null>(null)
const error = ref('')

// nuovo AP: parte dalle credenziali di un AP esistente con lo stesso protocollo
watch(() => form.method, m => {
  if (props.ap) return
  const s = props.all.find(a => a.method === m)
  form.copy_from = s?.id ?? null
  if (!s) return
  Object.assign(form, {
    snmp_version: s.snmp_version, snmp_user: s.snmp_user, snmp_auth_proto: s.snmp_auth_proto,
    snmp_priv_proto: s.snmp_priv_proto, ssh_port: s.ssh_port, ssh_user: s.ssh_user,
  })
}, { immediate: true })

const source = computed(() => props.ap ?? props.all.find(a => a.id === form.copy_from) ?? null)
const others = computed(() => props.all.filter(a => a.method === form.method && a.id !== props.ap?.id).length)

/** segnaposto dei campi password: dice se resta quella salvata o quella copiata */
function keeps(k: Secret, fallback: string) {
  const s = source.value
  if (!s || !s[HAS[k]]) return fallback
  return props.ap ? t('invariata — scrivi per cambiarla') : t('come {name}', { name: s.name })
}

async function run(kind: 'save' | 'test' | 'detect', fn: () => Promise<void>) {
  busy.value = kind
  error.value = ''
  try { await fn() } catch (e) { error.value = (e as Error).message } finally { busy.value = '' }
}

const payload = () => ({ ...form, id: props.ap?.id ?? null })

const detect = () => run('detect', async () => {
  result.value = null
  found.value = await api.detectAp(payload())
  if (found.value.suggested) form.method = found.value.suggested
  if (found.value.used_default_community && !form.snmp_community) form.snmp_community = 'public'
})

const test = () => run('test', async () => {
  found.value = null
  result.value = await api.testAp(payload())
})

const save = () => run('save', async () => {
  const r = props.ap ? await api.updateAp(props.ap.id, form) : await api.createAp(form)
  emit('saved', r.copied)
})
</script>

<template>
  <form class="ap-editor" @submit.prevent="save">
    <div class="grid">
      <label>{{ t('Nome') }}<input v-model="form.name" required maxlength="40" :placeholder="t('es. TAVERNA')" /></label>
      <label>{{ t('Indirizzo IP o nome host') }}<input v-model="form.host" required placeholder="192.168.1.15" /></label>
      <label>{{ t('Protocollo') }}
        <select v-model="form.method"><option value="snmp">SNMP</option><option value="ssh">SSH</option></select>
      </label>
      <label class="check"><input v-model="form.enabled" type="checkbox" /> {{ t('Attivo') }}</label>
    </div>

    <div v-if="form.method === 'snmp'" class="grid">
      <label>{{ t('Versione SNMP') }}
        <select v-model="form.snmp_version">
          <option value="2c">v2c</option><option value="3">{{ t('v3 (utente e password)') }}</option><option value="1">v1</option>
        </select>
      </label>
      <label v-if="form.snmp_version !== '3'">Community
        <input v-model="form.snmp_community" type="password" autocomplete="off" :placeholder="keeps('snmp_community', 'public')" />
      </label>
      <template v-else>
        <label>{{ t('Utente') }}<input v-model="form.snmp_user" required autocomplete="off" /></label>
        <label>{{ t('Autenticazione') }}
          <select v-model="form.snmp_auth_proto"><option v-for="p in AUTH" :key="p">{{ p }}</option></select>
        </label>
        <label>{{ t('Password autenticazione') }}
          <input v-model="form.snmp_auth_pass" type="password" autocomplete="new-password" :placeholder="keeps('snmp_auth_pass', t('min. 8 caratteri'))" />
        </label>
        <label>{{ t('Cifratura') }}
          <select v-model="form.snmp_priv_proto"><option v-for="p in PRIV" :key="p">{{ p }}</option></select>
        </label>
        <label>{{ t('Password cifratura') }}
          <input v-model="form.snmp_priv_pass" type="password" autocomplete="new-password" :placeholder="keeps('snmp_priv_pass', t('vuota = senza cifratura'))" />
        </label>
      </template>
    </div>

    <details v-if="form.method === 'snmp'" class="ssh-extra" :open="!!props.ap?.has_ssh_password">
      <summary>{{ t('Accesso SSH per configurazione e riavvio') }} <span class="muted small">{{ t('(facoltativo: i dati si leggono via SNMP)') }}</span></summary>
      <div class="grid">
        <label>{{ t('Utente SSH') }}<input v-model="form.ssh_user" autocomplete="off" /></label>
        <label>{{ t('Password SSH') }}
          <input v-model="form.ssh_password" type="password" autocomplete="new-password" :placeholder="keeps('ssh_password', t('Local credentials di Nebula'))" />
        </label>
        <label>{{ t('Porta') }}<input v-model.number="form.ssh_port" type="number" min="1" max="65535" /></label>
      </div>
    </details>

    <div v-else class="grid">
      <label>{{ t('Utente') }}<input v-model="form.ssh_user" required autocomplete="off" /></label>
      <label>{{ t('Password') }}
        <input v-model="form.ssh_password" type="password" autocomplete="new-password" :placeholder="keeps('ssh_password', t('Local credentials di Nebula'))" />
      </label>
      <label>{{ t('Porta') }}<input v-model.number="form.ssh_port" type="number" min="1" max="65535" /></label>
    </div>

    <label v-if="others" class="check">
      <input v-model="form.apply_to_all" type="checkbox" />
      {{ others === 1 ? t("Usa queste credenziali anche per l'altro AP {proto}", { proto: form.method.toUpperCase() }) : t('Usa queste credenziali anche per gli altri {n} AP {proto}', { n: others, proto: form.method.toUpperCase() }) }}
    </label>

    <div class="actions">
      <button type="button" :disabled="!form.host || !!busy" @click="detect">{{ busy === 'detect' ? t('Rilevo…') : t('Rileva protocollo') }}</button>
      <button type="button" :disabled="!form.host || !!busy" @click="test">{{ busy === 'test' ? t('Provo…') : t('Prova connessione') }}</button>
      <span class="spacer" />
      <button type="button" class="ghost" @click="emit('cancel')">{{ t('Annulla') }}</button>
      <button class="primary" :disabled="!!busy">{{ busy === 'save' ? t('Salvo…') : t('Salva') }}</button>
    </div>

    <p v-if="found" class="note" :class="found.suggested ? 'ok' : 'ko'">{{ found.message }}</p>
    <div v-if="result" class="note" :class="result.online ? 'ok' : 'ko'">
      <template v-if="result.online">
        <strong>{{ t('Connesso') }}</strong> {{ t('in {ms} ms', { ms: result.ms }) }} — {{ result.model || t('modello non letto') }}
        <template v-if="result.firmware"> · {{ t('firmware {v}', { v: result.firmware }) }}</template>
        · {{ result.clients }} client
        <template v-if="result.uptime_s"> · {{ t('acceso da {d}', { d: duration(result.uptime_s) }) }}</template>
        <template v-if="!result.traffic"> · {{ t('traffico non disponibile') }}</template>
      </template>
      <template v-else>
        <strong>{{ t('Non risponde:') }}</strong> {{ result.error }}
        <p v-if="result.hint" class="muted">{{ result.hint }}</p>
      </template>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
  </form>
</template>
