<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api, apForm, type Ap, type ApConfig, type ApTest, type GeneralForm } from '../api'
import ApEditor from './ApEditor.vue'

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
    return { text: `${a.ssh_user} · ${a.has_ssh_password ? 'password impostata' : 'password mancante'}`, missing: !a.has_ssh_password }
  if (a.snmp_version === '3')
    return { text: `${a.snmp_user} · ${a.has_snmp_priv_pass ? 'autenticato e cifrato' : a.has_snmp_auth_pass ? 'autenticato' : 'senza password'}`, missing: false }
  return { text: a.has_snmp_community ? 'community impostata' : 'community public', missing: false }
}

async function saved(copied: number) {
  editing.value = null
  notice.value = copied ? `Salvato. Credenziali copiate anche su ${copied} AP.` : 'Salvato: la lettura riparte subito.'
  await load()
  emit('changed')
}

async function toggle(a: ApConfig) {
  await run(() => api.updateAp(a.id, { ...apForm(a), enabled: !a.enabled }))
}

async function remove(a: ApConfig) {
  if (!window.confirm(`Eliminare ${a.name}? Scompare dalla dashboard; lo storico resta fino alla scadenza.`)) return
  await run(() => api.deleteAp(a.id))
}

async function run(fn: () => Promise<unknown>) {
  try { await fn(); await load(); emit('changed') } catch (e) { error.value = (e as Error).message }
}

async function testRow(a: ApConfig) {
  testing.value = a.id
  try { tests.value[a.id] = await api.testAp({ ...apForm(a), id: a.id }) }
  catch (e) { error.value = (e as Error).message }
  finally { testing.value = null }
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
  return { ok: true, message: 'Salvato: i dati di OPNsense arrivano entro un minuto.' }
})

onMounted(() => { load(); loadGeneral() })
</script>

<template>
  <main class="settings">
    <p v-if="error" class="banner err">{{ error }}</p>

    <section class="card">
      <div class="section-head">
        <h2>Access point</h2>
        <button class="primary" :disabled="editing === 'new'" @click="editing = 'new'; notice = ''">+ Aggiungi AP</button>
      </div>
      <p class="muted small mb">
        Password e community non vengono mai mostrate: lasciale vuote per tenere quelle salvate.
        “Rileva protocollo” prova da solo SNMP e SSH e ti dice quale usare.
      </p>
      <p v-if="notice" class="note ok mb">{{ notice }}</p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th /><th>Nome</th><th>Indirizzo</th><th>Protocollo</th><th>Credenziali</th><th>Ultima lettura</th><th /></tr>
          </thead>
          <tbody>
            <template v-for="a in list" :key="a.id">
              <tr :class="{ disabled: !a.enabled }">
                <td><span class="status" :class="!a.enabled ? 'idle' : statusOf(a)?.online ? 'on' : 'off'" /></td>
                <td><strong>{{ a.name }}</strong></td>
                <td class="mono">{{ a.host }}</td>
                <td><span class="tag">{{ protocol(a) }}</span></td>
                <td class="small" :class="{ error: credentials(a).missing }">{{ credentials(a).text }}</td>
                <td class="small">
                  <template v-if="!a.enabled">disattivato</template>
                  <template v-else-if="testing === a.id">prova in corso…</template>
                  <template v-else-if="tests[a.id]">
                    <span :class="tests[a.id].online ? 'ok-text' : 'error'">
                      {{ tests[a.id].online ? `prova riuscita · ${tests[a.id].clients} client · ${tests[a.id].ms} ms` : tests[a.id].error }}
                    </span>
                    <div v-if="tests[a.id].hint" class="muted">{{ tests[a.id].hint }}</div>
                  </template>
                  <template v-else-if="statusOf(a)">
                    <span v-if="statusOf(a)!.online">online · {{ statusOf(a)!.clients ?? 0 }} client</span>
                    <span v-else class="error">{{ statusOf(a)!.error || 'non raggiungibile' }}</span>
                  </template>
                  <span v-else class="muted">in attesa</span>
                </td>
                <td class="row-actions">
                  <button class="ghost small" :disabled="testing !== null || !a.enabled" @click="testRow(a)">Prova</button>
                  <button class="ghost small" @click="editing = editing === a.id ? null : a.id; notice = ''">Modifica</button>
                  <button class="ghost small" @click="toggle(a)">{{ a.enabled ? 'Disattiva' : 'Attiva' }}</button>
                  <button class="ghost small danger" @click="remove(a)">Elimina</button>
                </td>
              </tr>
              <tr v-if="editing === a.id" class="edit-row">
                <td colspan="7"><ApEditor :ap="a" :all="list" @saved="saved" @cancel="editing = null" /></td>
              </tr>
            </template>
            <tr v-if="editing === 'new'" class="edit-row">
              <td colspan="7"><ApEditor :ap="null" :all="list" @saved="saved" @cancel="editing = null" /></td>
            </tr>
            <tr v-if="!list.length && editing !== 'new'"><td colspan="7" class="muted">Nessun access point: aggiungine uno.</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <form class="card ap-editor" @submit.prevent="saveGeneral">
      <div class="section-head">
        <h2>OPNsense e raccolta</h2>
      </div>
      <p class="muted small">
        Facoltativo: dà i nomi dei dispositivi, i siti visitati, le pubblicità bloccate e lo stato della linea Internet.
        Serve una chiave API (System → Access → Users → icona chiave).
      </p>
      <div class="grid">
        <label>Indirizzo OPNsense<input v-model="gen.opnsense_url" placeholder="https://opnsense.casa.lan" /></label>
        <label>Chiave API<input v-model="gen.opnsense_key" autocomplete="off" /></label>
        <label>Secret API
          <input v-model="gen.opnsense_secret" type="password" autocomplete="new-password"
                 :placeholder="gen.has_opnsense_secret ? 'invariato — scrivi per cambiarlo' : ''" />
        </label>
        <label>Interfaccia WAN<input v-model="gen.opnsense_wan_if" placeholder="wan oppure opt1" /></label>
        <label>Dominio della LAN<input v-model="gen.local_domain" placeholder="casa.lan" /></label>
        <label class="check"><input v-model="gen.opnsense_verify_tls" type="checkbox" /> Verifica certificato</label>
        <label>Lettura ogni (secondi)<input v-model.number="gen.poll_interval" type="number" min="15" max="3600" /></label>
        <label>Storico (giorni)<input v-model.number="gen.retention_days" type="number" min="1" max="365" /></label>
      </div>
      <div class="actions">
        <button type="button" :disabled="genBusy" @click="testGeneral">Prova OPNsense</button>
        <span class="spacer" />
        <button class="primary" :disabled="genBusy">{{ genBusy ? 'Attendi…' : 'Salva' }}</button>
      </div>
      <p v-if="genMsg" class="note" :class="genMsg.ok ? 'ok' : 'ko'">{{ genMsg.message }}</p>
    </form>
  </main>
</template>
