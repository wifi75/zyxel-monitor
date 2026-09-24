<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, type NebulaDevice, type NebulaDiscover, type NebulaSsid, type NebulaStatus } from '../api'

/** Nebula OpenAPI: funziona solo con la licenza Pro. Senza, il collegamento lo dice e il resto resta nascosto. */
const status = ref<NebulaStatus | null>(null)
const key = ref('')
const found = ref<NebulaDiscover | null>(null)
const orgId = ref('')
const siteId = ref('')
const busy = ref('')
const error = ref('')
const notice = ref('')

const devices = ref<NebulaDevice[]>([])
const updates = ref(0)
const ssids = ref<NebulaSsid[]>([])

const sites = computed(() => found.value?.organizations?.find(o => o.orgId === orgId.value)?.sites ?? [])
/** bande proposte: quelle che Nebula usa davvero sulle reti del sito */
const bandOptions = computed(() => [...new Set(ssids.value.flatMap(s => s.enabledBands))].sort())

async function run(kind: string, fn: () => Promise<void>) {
  busy.value = kind; error.value = ''; notice.value = ''
  try { await fn() } catch (e) { error.value = (e as Error).message } finally { busy.value = '' }
}

async function loadData() {
  if (!status.value?.configured) return
  const [d, s] = await Promise.all([api.nebulaDevices(), api.nebulaSsids()])
  devices.value = d.devices; updates.value = d.updates; ssids.value = s
}

onMounted(() => run('load', async () => {
  status.value = await api.nebulaStatus()
  await loadData()
}))

const discover = () => run('discover', async () => {
  found.value = await api.nebulaDiscover(key.value)
  const first = found.value.organizations?.find(o => o.sites.length)
  orgId.value = first?.orgId ?? found.value.organizations?.[0]?.orgId ?? ''
  siteId.value = first?.sites[0]?.siteId ?? ''
})

const connect = () => run('connect', async () => {
  status.value = await api.nebulaConnect(key.value, orgId.value, siteId.value)
  key.value = ''; found.value = null
  await loadData()
  notice.value = 'Nebula collegato.'
})

const disconnect = () => run('connect', async () => {
  if (!window.confirm('Scollegare Nebula? La chiave viene cancellata dal server.')) return
  status.value = await api.nebulaDisconnect()
  devices.value = []; ssids.value = []
})

const reboot = (d: NebulaDevice) => {
  if (!window.confirm(`Riavviare ${d.name || d.devId}? Resta offline per un paio di minuti.`)) return
  run(`reboot-${d.devId}`, async () => { await api.nebulaReboot(d.devId); notice.value = `Riavvio di ${d.name} inviato.` })
}

const saveSsid = (s: NebulaSsid, patch: { name?: string; enabled?: boolean; bands?: string[] }) =>
  run(`ssid-${s.id}`, async () => { await api.nebulaUpdateSsid(s.id, patch); ssids.value = await api.nebulaSsids(); notice.value = 'Rete aggiornata.' })

function rename(s: NebulaSsid) {
  const name = window.prompt('Nuovo nome della rete Wi-Fi', s.name)
  if (name && name !== s.name) saveSsid(s, { name })
}

function toggleBand(s: NebulaSsid, band: string) {
  const bands = s.enabledBands.includes(band) ? s.enabledBands.filter(b => b !== band) : [...s.enabledBands, band]
  if (!bands.length) { error.value = 'Serve almeno una banda.'; return }
  saveSsid(s, { bands })
}

const FW: Record<string, string> = { UP_TO_DATE: 'aggiornato', NOT_UP_TO_DATE: 'aggiornamento disponibile', DEDICATED: 'versione dedicata', 'N/A': '—' }
</script>

<template>
  <section class="card ap-editor">
    <div class="section-head">
      <h2>Nebula <span class="muted small">(licenza Pro)</span></h2>
      <span v-if="status?.configured" class="badge ok">collegato</span>
      <button v-if="status?.configured" class="ghost small danger" :disabled="!!busy" @click="disconnect">Scollega</button>
    </div>
    <p class="muted small">
      Con la licenza <strong>Pro</strong> Nebula permette di vedere firmware e stato degli AP, gestire le reti Wi-Fi e riavviare gli AP.
      La chiave si crea in Nebula → <em>My devices &amp; services → NCC OpenAPI Key</em> e resta solo su questo server.
      Potenza radio e canali non sono gestibili dall'API di Nebula.
    </p>

    <template v-if="!status?.configured">
      <div class="grid">
        <label>Chiave OpenAPI
          <input v-model="key" type="password" autocomplete="off" :placeholder="status?.has_key ? 'salvata — scrivi per cambiarla' : 'incolla la chiave'" />
        </label>
        <template v-if="found?.ok && found.organizations?.length">
          <label>Organizzazione
            <select v-model="orgId">
              <option v-for="o in found.organizations" :key="o.orgId" :value="o.orgId">{{ o.name }} ({{ o.mode }})</option>
            </select>
          </label>
          <label>Sito
            <select v-model="siteId" :disabled="!sites.length">
              <option v-for="s in sites" :key="s.siteId" :value="s.siteId">{{ s.name }} · {{ s.deviceCount }} dispositivi</option>
            </select>
          </label>
        </template>
      </div>
      <div class="actions">
        <button type="button" :disabled="!!busy || (!key && !status?.has_key)" @click="discover">{{ busy === 'discover' ? 'Collego…' : 'Collega' }}</button>
        <span class="spacer" />
        <button v-if="found?.ok && siteId" class="primary" :disabled="!!busy" @click="connect">Salva collegamento</button>
      </div>
      <p v-if="found && !found.ok" class="note ko">{{ found.message }}</p>
      <p v-else-if="found?.message" class="note ko">{{ found.message }}</p>
      <p v-if="found?.ok && !sites.length" class="note ko">
        {{ found.organizations?.find(o => o.orgId === orgId)?.error || "Nessun sito visibile per questa organizzazione." }}
      </p>
    </template>

    <template v-else>
      <h3 class="small sub">
        Dispositivi e firmware
        <span v-if="updates" class="badge ko">{{ updates }} aggiornament{{ updates === 1 ? 'o' : 'i' }} disponibil{{ updates === 1 ? 'e' : 'i' }}</span>
      </h3>
      <div class="table-wrap">
        <table>
          <thead><tr><th /><th>Nome</th><th>Modello</th><th>MAC</th><th>Firmware</th><th>Disponibile</th><th>Stato</th><th /></tr></thead>
          <tbody>
            <tr v-for="d in devices" :key="d.devId">
              <td><span class="status" :class="d.online ? 'on' : 'off'" /></td>
              <td><strong>{{ d.name || d.devId }}</strong></td>
              <td>{{ d.model || '—' }}</td>
              <td class="mono small">{{ d.mac }}</td>
              <td class="mono small">{{ d.currentVersion || '—' }}</td>
              <td class="mono small">{{ d.latestVersion || '—' }}</td>
              <td><span class="chip" :style="{ '--tone': d.firmwareStatus === 'NOT_UP_TO_DATE' ? 'var(--orange)' : 'var(--green)' }">{{ FW[d.firmwareStatus ?? 'N/A'] ?? d.firmwareStatus }}</span></td>
              <td class="row-actions">
                <button class="ghost small" :disabled="!!busy || !d.online" @click="reboot(d)">{{ busy === `reboot-${d.devId}` ? 'Invio…' : 'Riavvia' }}</button>
              </td>
            </tr>
            <tr v-if="!devices.length"><td colspan="8" class="muted">{{ busy === 'load' ? 'Caricamento…' : 'Nessun dispositivo nel sito.' }}</td></tr>
          </tbody>
        </table>
      </div>

      <h3 class="small sub">Reti Wi-Fi</h3>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Rete</th><th>Sicurezza</th><th>VLAN</th><th>Bande</th><th>Attiva</th><th /></tr></thead>
          <tbody>
            <tr v-for="s in ssids" :key="s.id">
              <td><strong>{{ s.name }}</strong> <span v-if="s.guestNetwork" class="chip">ospiti</span> <span v-if="!s.visibility" class="muted small">nascosta</span></td>
              <td class="small">{{ s.security.replace(/_/g, ' ') }}</td>
              <td class="small">{{ s.vlan }}</td>
              <td>
                <label v-for="b in bandOptions" :key="b" class="check inline">
                  <input type="checkbox" :checked="s.enabledBands.includes(b)" :disabled="!!busy" @change="toggleBand(s, b)" /> {{ b }}
                </label>
                <span v-if="!bandOptions.length" class="muted small">{{ s.band.join(', ') }}</span>
              </td>
              <td><input type="checkbox" :checked="s.enabled" :disabled="!!busy" @change="saveSsid(s, { enabled: !s.enabled })" /></td>
              <td class="row-actions"><button class="ghost small" :disabled="!!busy" @click="rename(s)">Rinomina</button></td>
            </tr>
            <tr v-if="!ssids.length"><td colspan="6" class="muted">Nessuna rete.</td></tr>
          </tbody>
        </table>
      </div>
    </template>

    <p v-if="notice" class="note ok">{{ notice }}</p>
    <p v-if="error" class="note ko">{{ error }}</p>
  </section>
</template>
