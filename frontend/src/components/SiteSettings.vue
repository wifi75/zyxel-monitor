<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, type PolicyResult, type SiteItem } from '../api'
import { t } from '../i18n'
import Icon from './Icon.vue'
import type { IconName } from '../icons'

/** Impostazioni del sito: valgono per tutti gli AP e il sistema le mantiene (controllo ogni 15 minuti). */
const emit = defineEmits<{ results: [r: PolicyResult[]] }>()

const items = ref<SiteItem[]>([])
const draft = ref<Record<string, string>>({})
const busy = ref('')
const error = ref('')

const SECTIONS: { key: string; title: string; icon: IconName; tone: string }[] = [
  { key: 'rete', title: 'Rete Wi-Fi', icon: 'wifi', tone: 'tone-blue' },
  { key: 'ospiti', title: 'Rete ospiti', icon: 'users', tone: 'tone-pink' },
  { key: 'radio', title: 'Radio e roaming', icon: 'activity', tone: 'tone-violet' },
  { key: 'sistema', title: 'Sistema', icon: 'gear', tone: 'tone-teal' },
]
const bySection = computed(() => Object.fromEntries(SECTIONS.map(s => [s.key, items.value.filter(i => i.section === s.key)])))

async function load() {
  try {
    items.value = await api.siteItems()
    draft.value = Object.fromEntries(items.value.map(i => [i.key,
      i.value == null || i.kind === 'password' ? '' : Array.isArray(i.value) ? i.value.join('\n') : String(i.value)]))
  } catch (e) { error.value = (e as Error).message }
}
onMounted(load)

async function save(i: SiteItem, value: string | number | boolean | string[] | null) {
  if (i.key === 'security_mode' && value === 'wpa3' &&
      !window.confirm(t('Solo WPA3: i dispositivi più vecchi (stampanti, domotica, vecchi telefoni) non si collegheranno più. Procedere?'))) return
  if (i.key === 'wifi_password' && value != null &&
      !window.confirm(t('Cambiare la password scollega tutti i dispositivi: andranno ricollegati con la nuova password. Procedere?'))) return
  if (i.key === 'ssid_name' && value != null &&
      !window.confirm(t('Cambiare il nome della rete scollega tutti i dispositivi: andranno ricollegati alla rete "{n}". Procedere?', { n: String(value) }))) return
  busy.value = i.key; error.value = ''
  try { emit('results', (await api.setSiteItem(i.key, value)).results); await load() }
  catch (e) { error.value = (e as Error).message } finally { busy.value = '' }
}

/** select per le voci sì/no: "" = non gestito */
function saveBool(i: SiteItem, v: string) { save(i, v === '' ? null : v === 'on') }
function saveList(i: SiteItem) {
  const macs = draft.value[i.key].split(/[\s,;]+/).map(m => m.trim()).filter(Boolean)
  save(i, macs)
}
function saveText(i: SiteItem) {
  const v = i.kind === 'password' ? draft.value[i.key] : draft.value[i.key].trim()
  save(i, v === '' ? null : i.kind === 'int' ? Number(v) : v)
}
/** valore attuale sugli AP: uguale per tutti, diverso, o non ancora letto */
function currentText(i: SiteItem): { text: string; detail: string } | null {
  const entries = Object.entries(i.current ?? {})
  if (!entries.length) return null
  const fmt = (v: unknown): string => {
    if (v == null) return '—'
    if (i.kind === 'password') return v ? t('impostata') : t('nessuna')
    if (typeof v === 'boolean') return v ? t('attivo') : t('spento')
    if (Array.isArray(v)) return v.length ? v.join(', ') : t('nessuno')
    if (i.kind === 'choice' && String(v) === '0') return t('disattivata')
    return i.unit ? `${v} ${i.unit}` : String(v)
  }
  const values = [...new Set(entries.map(([, v]) => fmt(v)))]
  const detail = entries.map(([ap, v]) => `${ap}: ${fmt(v)}`).join(' · ')
  if (values.length === 1) return { text: t('Attuale: {v} (tutti e {n} gli AP)', { v: values[0], n: entries.length }), detail }
  return { text: t('Diverso fra gli AP'), detail }
}

const CHOICE: Record<string, string> = {
  disable: 'Spento', standard: 'Standard', force: 'Forzato', off: 'Spento',
  'daily-04': 'Ogni giorno alle 4:00', 'sun-04': 'La domenica alle 4:00', 'sat-04': 'Il sabato alle 4:00',
}
const boolValue = (i: SiteItem) => (i.value == null ? '' : i.value ? 'on' : 'off')
</script>

<template>
  <section class="card">
    <h2 class="mb">{{ t('Impostazioni del sito') }} <span class="muted small">{{ t('(valgono per tutti gli AP, controllate ogni 15 minuti)') }}</span></h2>
    <p v-if="error" class="note ko mb">{{ error }}</p>
    <div class="site-sections">
      <div v-for="s in SECTIONS" :key="s.key" class="site-section" :class="s.tone">
        <div class="site-head"><span class="nav-ico"><Icon :name="s.icon" :size="17" /></span><h3>{{ t(s.title) }}</h3></div>
        <div v-for="i in bySection[s.key]" :key="i.key" class="site-row">
          <div class="grow">
            <strong>{{ t(i.label) }}</strong>
            <p class="muted small">{{ t(i.help) }}</p>
            <p v-if="currentText(i)" class="site-current" :class="{ diff: currentText(i)!.text === t('Diverso fra gli AP') }"
               :title="currentText(i)!.detail">{{ currentText(i)!.text }}</p>
          </div>
          <div class="site-ctrl">
            <select v-if="i.kind === 'bool'" :value="boolValue(i)" :disabled="!!busy" @change="saveBool(i, ($event.target as HTMLSelectElement).value)">
              <option value="">{{ t('Non gestito') }}</option>
              <option value="on">{{ t('Attivo') }}</option>
              <option value="off">{{ t('Spento') }}</option>
            </select>
            <select v-else-if="i.kind === 'choice'" :value="i.value == null ? '' : String(i.value)" :disabled="!!busy"
                    @change="save(i, ($event.target as HTMLSelectElement).value || null)">
              <option value="">{{ t('Non gestito') }}</option>
              <option v-for="c in i.choices" :key="c" :value="c">{{ c === '0' ? t('Disattivata') : i.unit ? `${c} ${i.unit}` : CHOICE[c] ? t(CHOICE[c]) : c.toUpperCase().replace('/', ' + ') }}</option>
            </select>
            <form v-else-if="i.kind === 'list'" class="site-list" @submit.prevent="saveList(i)">
              <textarea v-model="draft[i.key]" rows="3" placeholder="aa:bb:cc:dd:ee:ff" :disabled="!!busy" />
              <button class="ghost small" :disabled="!!busy">{{ busy === i.key ? t('Applico…') : t('Applica') }}</button>
            </form>
            <form v-else class="site-input" @submit.prevent="saveText(i)">
              <input v-model="draft[i.key]" :type="i.kind === 'int' ? 'number' : i.kind === 'password' ? 'password' : 'text'"
                     :autocomplete="i.kind === 'password' ? 'new-password' : 'off'"
                     :placeholder="i.kind === 'password' ? (i.value ? t('impostata — scrivi per cambiarla') : t('Non gestita')) : t('Non gestito')" :disabled="!!busy" />
              <span v-if="i.unit" class="muted small">{{ i.unit }}</span>
              <button class="ghost small" :disabled="!!busy">{{ busy === i.key ? t('Applico…') : t('Applica') }}</button>
            </form>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
