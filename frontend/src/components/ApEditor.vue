<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { api, apForm, type ApConfig, type ApTest, type Detect, type Secret } from '../api'
import { duration } from '../format'

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
  return props.ap ? 'invariata — scrivi per cambiarla' : `come ${s.name}`
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
      <label>Nome<input v-model="form.name" required maxlength="40" placeholder="es. TAVERNA" /></label>
      <label>Indirizzo IP o nome host<input v-model="form.host" required placeholder="192.168.1.15" /></label>
      <label>Protocollo
        <select v-model="form.method"><option value="snmp">SNMP</option><option value="ssh">SSH</option></select>
      </label>
      <label class="check"><input v-model="form.enabled" type="checkbox" /> Attivo</label>
    </div>

    <div v-if="form.method === 'snmp'" class="grid">
      <label>Versione SNMP
        <select v-model="form.snmp_version">
          <option value="2c">v2c</option><option value="3">v3 (utente e password)</option><option value="1">v1</option>
        </select>
      </label>
      <label v-if="form.snmp_version !== '3'">Community
        <input v-model="form.snmp_community" type="password" autocomplete="off" :placeholder="keeps('snmp_community', 'public')" />
      </label>
      <template v-else>
        <label>Utente<input v-model="form.snmp_user" required autocomplete="off" /></label>
        <label>Autenticazione
          <select v-model="form.snmp_auth_proto"><option v-for="p in AUTH" :key="p">{{ p }}</option></select>
        </label>
        <label>Password autenticazione
          <input v-model="form.snmp_auth_pass" type="password" autocomplete="new-password" :placeholder="keeps('snmp_auth_pass', 'min. 8 caratteri')" />
        </label>
        <label>Cifratura
          <select v-model="form.snmp_priv_proto"><option v-for="p in PRIV" :key="p">{{ p }}</option></select>
        </label>
        <label>Password cifratura
          <input v-model="form.snmp_priv_pass" type="password" autocomplete="new-password" :placeholder="keeps('snmp_priv_pass', 'vuota = senza cifratura')" />
        </label>
      </template>
    </div>

    <div v-else class="grid">
      <label>Utente<input v-model="form.ssh_user" required autocomplete="off" /></label>
      <label>Password
        <input v-model="form.ssh_password" type="password" autocomplete="new-password" :placeholder="keeps('ssh_password', 'Local credentials di Nebula')" />
      </label>
      <label>Porta<input v-model.number="form.ssh_port" type="number" min="1" max="65535" /></label>
    </div>

    <label v-if="others" class="check">
      <input v-model="form.apply_to_all" type="checkbox" />
      Usa queste credenziali anche per {{ others === 1 ? "l'altro AP" : `gli altri ${others} AP` }} {{ form.method.toUpperCase() }}
    </label>

    <div class="actions">
      <button type="button" :disabled="!form.host || !!busy" @click="detect">{{ busy === 'detect' ? 'Rilevo…' : 'Rileva protocollo' }}</button>
      <button type="button" :disabled="!form.host || !!busy" @click="test">{{ busy === 'test' ? 'Provo…' : 'Prova connessione' }}</button>
      <span class="spacer" />
      <button type="button" class="ghost" @click="emit('cancel')">Annulla</button>
      <button class="primary" :disabled="!!busy">{{ busy === 'save' ? 'Salvo…' : 'Salva' }}</button>
    </div>

    <p v-if="found" class="note" :class="found.suggested ? 'ok' : 'ko'">{{ found.message }}</p>
    <div v-if="result" class="note" :class="result.online ? 'ok' : 'ko'">
      <template v-if="result.online">
        <strong>Connesso</strong> in {{ result.ms }} ms — {{ result.model || 'modello non letto' }}
        <template v-if="result.firmware"> · firmware {{ result.firmware }}</template>
        · {{ result.clients }} client
        <template v-if="result.uptime_s"> · acceso da {{ duration(result.uptime_s) }}</template>
        <template v-if="!result.traffic"> · traffico non disponibile</template>
      </template>
      <template v-else>
        <strong>Non risponde:</strong> {{ result.error }}
        <p v-if="result.hint" class="muted">{{ result.hint }}</p>
      </template>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
  </form>
</template>
