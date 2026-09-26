<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, download, type BackupStatus } from '../api'
import { bytes, time } from '../format'
import { t } from '../i18n'

/** Copia del database: scaricabile adesso, e salvata in automatico ogni notte. */
const st = ref<BackupStatus | null>(null)
const error = ref('')
onMounted(async () => { st.value = await api.backupStatus().catch(() => null) })
const now = () => download('/backup/download', 'zyxel-monitor.db').catch(e => { error.value = (e as Error).message })
</script>

<template>
  <section class="card ap-editor">
    <div class="section-head">
      <h2>{{ t('Backup del database') }}</h2>
      <span class="spacer" />
      <button class="ghost" @click="now">{{ t('Scarica adesso') }}</button>
    </div>
    <p class="muted small">
      {{ t('Storico, dispositivi, impostazioni e backup degli AP stanno in un solo file. Ogni notte dopo le 3 se ne salva una copia; si tengono le ultime {n}.', { n: st?.keep ?? 7 }) }}
      {{ t('Per tenerle fuori da Docker, in Portainer monta una cartella del NAS su questo percorso:') }}
      <code v-if="st">{{ st.folder }}</code>
    </p>
    <ul v-if="st?.files.length" class="site-list">
      <li v-for="f in st.files" :key="f.name"><span class="mono small">{{ f.name }}</span><span class="muted small">{{ bytes(f.size) }} · {{ time(f.ts) }}</span></li>
    </ul>
    <p v-else class="muted small">{{ t('Nessuna copia notturna ancora.') }}</p>
    <p v-if="error" class="error small">{{ error }}</p>
  </section>
</template>
