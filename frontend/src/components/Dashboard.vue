<script setup lang="ts">
import { GridItem, GridLayout } from 'grid-layout-plus'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api, type SavedLayout, type ViewKind, type WidgetPos } from '../api'
import { t } from '../i18n'
import { COLS, appendWidget, defOf, defaultLayout, normalize, widgetsFor } from '../widgets'

/**
 * Griglia stile Zabbix: in modalità "Personalizza" i widget si trascinano dalla barra del titolo
 * e si ridimensionano dall'angolo. La disposizione si salva per utente, separata per panoramica e AP.
 */
const props = defineProps<{ view: ViewKind }>()
defineSlots<{ widget(props: { id: string }): unknown }>()
/** acceso dal pulsante "Personalizza" nella barra in alto */
const editing = defineModel<boolean>('editing', { default: false })

const saved = ref<SavedLayout>({})
const layout = ref<WidgetPos[]>(defaultLayout(props.view))
const addId = ref('')

// sotto i 768 px la griglia non ha senso: i widget si impilano nell'ordine della disposizione
const mq = window.matchMedia('(max-width: 767px)')
const narrow = ref(mq.matches)
const onMq = (e: MediaQueryListEvent) => { narrow.value = e.matches }

onMounted(async () => {
  mq.addEventListener('change', onMq)
  saved.value = await api.layout().catch(() => ({}))
  layout.value = normalize(props.view, saved.value[props.view])
})
onBeforeUnmount(() => mq.removeEventListener('change', onMq))
watch(() => props.view, v => { layout.value = normalize(v, saved.value[v]) })

const stacked = computed(() => [...layout.value].sort((a, b) => a.y - b.y || a.x - b.x))
const missing = computed(() => {
  const shown = new Set(layout.value.map(p => p.i))
  return widgetsFor(props.view).filter(w => !shown.has(w.id))
})

let timer: number | undefined
function persist() {
  const clean: WidgetPos[] = layout.value.map(({ i, x, y, w, h }) => ({ i, x, y, w, h }))
  const patch: SavedLayout = {}
  patch[props.view] = clean
  saved.value = { ...saved.value, ...patch }
  clearTimeout(timer)
  timer = window.setTimeout(() => api.saveLayout(patch).catch(() => {}), 600)
}

function remove(id: string) {
  layout.value = layout.value.filter(p => p.i !== id)
  persist()
}

function add() {
  if (!addId.value) return
  layout.value = [...layout.value, appendWidget(layout.value, addId.value)]
  addId.value = ''
  persist()
}

async function reset() {
  if (!window.confirm(t('Ripristinare la disposizione iniziale di questa vista?'))) return
  layout.value = defaultLayout(props.view)
  persist()
}
</script>

<template>
  <div v-if="editing" class="dash-tools">
    <span class="muted small grow">{{ t("Trascina un widget dalla barra del titolo, ridimensionalo dall'angolo in basso a destra.") }}</span>
    <select v-if="missing.length" v-model="addId" @change="add">
      <option value="">{{ t('+ Aggiungi widget…') }}</option>
      <option v-for="w in missing" :key="w.id" :value="w.id">{{ t(w.title) }}</option>
    </select>
    <button class="ghost small" @click="reset">{{ t('Ripristina') }}</button>
    <button class="primary small" @click="editing = false">{{ t('Fatto') }}</button>
  </div>

  <div v-if="narrow" class="dash-stack">
    <div v-for="p in stacked" :key="p.i" class="widget card">
      <div v-if="editing" class="widget-bar">
        <span>{{ t(defOf(p.i)?.title ?? '') }}</span>
        <button class="ghost small" :title="t('Nascondi')" @click="remove(p.i)">×</button>
      </div>
      <div class="widget-body"><slot name="widget" :id="p.i" /></div>
    </div>
  </div>

  <GridLayout
    v-else
    v-model:layout="layout"
    class="dash-grid"
    :class="{ editing }"
    :col-num="COLS"
    :row-height="40"
    :margin="[12, 12]"
    :is-draggable="editing"
    :is-resizable="editing"
    :vertical-compact="true"
    :use-css-transforms="true"
    @layout-updated="editing && persist()"
  >
    <GridItem
      v-for="p in layout"
      :key="p.i"
      :i="p.i" :x="p.x" :y="p.y" :w="p.w" :h="p.h"
      :min-w="defOf(p.i)?.minW ?? 2"
      :min-h="defOf(p.i)?.minH ?? 3"
      drag-allow-from=".widget-bar"
    >
      <div class="widget card">
        <div v-if="editing" class="widget-bar">
          <span>⠿ {{ t(defOf(p.i)?.title ?? '') }}</span>
          <button class="ghost small" :title="t('Nascondi')" @click="remove(p.i)">×</button>
        </div>
        <div class="widget-body"><slot name="widget" :id="p.i" /></div>
      </div>
    </GridItem>
  </GridLayout>
</template>
