<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api, apForm, type Ap, type ApConfig, type ApTest, type GeneralForm } from '../api'
import { copyText } from '../format'
import { t } from '../i18n'
import ApEditor from './ApEditor.vue'
import NebulaPanel from './NebulaPanel.vue'

const props = defineProps<{ status: Ap[] }>()
const emit = defineEmits<{ changed: [] }>()

// ---- access point ----
const list = ref<ApConfig[]>([])
const editing = ref<number | 'new' | null>(null)
const error = ref('')
const notice = ref('')
const tests = ref<Record<number, ApTest>>({})
const testing = ref<number | null>(null)

async function load() {
  try { list.value = await api.apConfigs(); error.value = '' } catch (e) { error.value = (e as Error).message }
}

const statusOf = (a: ApConfig) => props.status.find(s => s.ap === a.name) ?? null
const protocol = (a: ApConfig) => a.method === 'ssh'
  ? `SSH${a.ssh_port !== 22 ? ` :${a.ssh_port}` : ''}` : `SNMP v${a.snmp_version}`

function credentials(a: ApConfig): { text: string; missing: boolean } {
  if (a.method === 'ssh')
    return { text: `${a.ssh_user} · ${a.has_ssh_password ? t('password impostata') : t('password mancante')}`, missing: !a.has_ssh_password }
  if (a.snmp_version === '3')
    return { text: `${a.snmp_user} · ${a.has_snmp_priv_pass ? t('autenticato e cifrato') : a.has_snmp_auth_pass ? t('autenticato') : t('senza password')}`, missing: false }
  return { text: a.has_snmp_community ? t('community impostata') : t('community public'), missing: false }
}

async function saved(copied: number) {
  editing.value = null
  notice.value = copied ? t('Salvato. Credenziali copiate anche su {n} AP.', { n: copied }) : t('Salvato: la lettura riparte subito.')
  await load()
  emit('changed')
}

async function toggle(a: ApConfig) {
  await run(() => api.updateAp(a.id, { ...apForm(a), enabled: !a.enabled }))
}

async function remove(a: ApConfig) {
  if (!window.confirm(t('Eliminare {name}? Scompare dalla dashboard; lo storico resta fino alla scadenza.', { name: a.name }))) return
  await run(() => api.deleteAp(a.id))
}

async function run(fn: () => Promise<unknown>) {
  try { await fn(); await load(); emit('changed') } catch (e) { error.value = (e as Error).message }
}

async function reboot(a: ApConfig) {
  if (!window.confirm(t('Riavviare {name}? Resta offline per 2-3 minuti.', { name: a.name }))) return
  try { await api.rebootAp(a.id); notice.value = t('Riavvio di {name} inviato: torna online in 2-3 minuti.', { name: a.name }) }
  catch (e) { error.value = (e as Error).message }
}

async function testRow(a: ApConfig) {
  testing.value = a.id
  try { tests.value[a.id] = await api.testAp({ ...apForm(a), id: a.id }) }
  catch (e) { error.value = (e as Error).message }
  finally { testing.value = null }
}

const raw = ref<{ id: number; ts: number | null; text: string } | null>(null)
const copied = ref(false)
async function showRaw(a: ApConfig) {
  if (raw.value?.id === a.id) { raw.value = null; return }
  try { raw.value = { id: a.id, ...(await api.rawOutput(a.id)) }; copied.value = false }
  catch (e) { error.value = (e as Error).message }
}
async function copyRaw() {
  copied.value = await copyText(raw.value?.text ?? '')
}

// ---- OPNsense e raccolta ----
const gen = reactive<GeneralForm>({
  opnsense_url: '', opnsense_key: '', opnsense_secret: '', has_opnsense_secret: false, opnsense_verify_tls: true,
  opnsense_wan_if: 'wan', local_domain: '', poll_interval: 60, retention_days: 30,
})
const genBusy = ref(false)
const genMsg = ref<{ ok: boolean; message: string } | null>(null)

async function loadGeneral() {
  try { Object.assign(gen, await api.general(), { opnsense_secret: '' }) } catch (e) { error.value = (e as Error).message }
}

async function genRun(fn: () => Promise<{ ok: boolean; message: string }>) {
  genBusy.value = true
  genMsg.value = null
  try { genMsg.value = await fn() } catch (e) { genMsg.value = { ok: false, message: (e as Error).message } }
  finally { genBusy.value = false }
}

const testGeneral = () => genRun(() => api.testOpnsense(gen))
const saveGeneral = () => genRun(async () => {
  Object.assign(gen, await api.saveGeneral(gen), { opnsense_secret: '' })
  emit('changed')
  return { ok: true, message: t('Salvato: i dati di OPNsense arrivano entro un minuto.') }
})

onMounted(() => { load(); loadGeneral() })
</script>

<template>
  <main class="settings">
    <p v-if="error" class="banner err">{{ error }}</p>

    <p class="muted small">{{ t('Gli access point si gestiscono nella pagina') }} <strong>{{ t('Gestione AP') }}</strong>.</p>

    <form class="card ap-editor" @submit.prevent="saveGeneral">
      <div class="section-head">
        <h2>{{ t('OPNsense e raccolta') }}</h2>
      </div>
      <p class="muted small">
        {{ t('Facoltativo: dà i nomi dei dispositivi, i siti visitati, le pubblicità bloccate e lo stato della linea Internet.') }}
        {{ t('Serve una chiave API (System → Access → Users → icona chiave).') }}
      </p>
      <div class="grid">
        <label>{{ t('Indirizzo OPNsense') }}<input v-model="gen.opnsense_url" placeholder="https://opnsense.casa.lan" /></label>
        <label>{{ t('Chiave API') }}<input v-model="gen.opnsense_key" autocomplete="off" /></label>
        <label>{{ t('Secret API') }}
          <input v-model="gen.opnsense_secret" type="password" autocomplete="new-password"
                 :placeholder="gen.has_opnsense_secret ? t('invariato — scrivi per cambiarlo') : ''" />
        </label>
        <label>{{ t('Interfaccia WAN') }}<input v-model="gen.opnsense_wan_if" :placeholder="t('wan oppure opt1')" /></label>
        <label>{{ t('Dominio della LAN') }}<input v-model="gen.local_domain" placeholder="casa.lan" /></label>
        <label class="check"><input v-model="gen.opnsense_verify_tls" type="checkbox" /> {{ t('Verifica certificato') }}</label>
        <label>{{ t('Lettura ogni (secondi)') }}<input v-model.number="gen.poll_interval" type="number" min="15" max="3600" /></label>
        <label>{{ t('Storico (giorni)') }}<input v-model.number="gen.retention_days" type="number" min="1" max="365" /></label>
      </div>
      <div class="actions">
        <button type="button" :disabled="genBusy" @click="testGeneral">{{ t('Prova OPNsense') }}</button>
        <span class="spacer" />
        <button class="primary" :disabled="genBusy">{{ genBusy ? t('Attendi…') : t('Salva') }}</button>
      </div>
      <p v-if="genMsg" class="note" :class="genMsg.ok ? 'ok' : 'ko'">{{ genMsg.message }}</p>
    </form>

    <NebulaPanel />
  </main>
</template>
