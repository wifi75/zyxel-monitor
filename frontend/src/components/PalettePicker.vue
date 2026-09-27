<script setup lang="ts">
import { CARD_TONES, PALETTES, look, resetLook } from '../palette'
import { t } from '../i18n'

/** Scelta dei colori delle sfumature, mostrata in modalità "Personalizza": l'effetto si vede subito. */
const SWATCH = ['--blue', '--teal', '--green', '--violet', '--pink', '--amber', '--orange']
const CARD_NAME: Record<string, string> = {
  good: 'Verde stato', blue: 'Blu', teal: 'Verde acqua', violet: 'Viola', pink: 'Rosa', amber: 'Ambra', orange: 'Arancio',
}
</script>

<template>
  <div class="palette-panel">
    <div class="pp-row">
      <span class="pp-label small">{{ t('Tavolozza') }}</span>
      <div class="pp-list">
        <button v-for="p in PALETTES" :key="p.id" class="pp-item" :class="{ active: look.palette === p.id }"
                :title="t(p.name)" @click="look.palette = p.id">
          <span class="pp-swatches">
            <i v-for="(v, n) in SWATCH" :key="v" :style="{ background: p.tones ? p.tones[n] : `var(${v})` }" />
          </span>
          <span class="small">{{ t(p.name) }}</span>
        </button>
      </div>
    </div>
    <div class="pp-row">
      <span class="pp-label small">{{ t('Card degli AP') }}</span>
      <div class="pp-list">
        <button v-for="c in CARD_TONES" :key="c" class="pp-dot" :class="{ active: look.card === c }"
                :style="{ background: `var(--${c})` }" :title="t(CARD_NAME[c])" :aria-label="t(CARD_NAME[c])"
                @click="look.card = c" />
      </div>
      <span class="pp-label small">{{ t('Intensità') }}</span>
      <input v-model.number="look.shade" type="range" min="0" max="3" step="0.25" class="pp-range"
             :title="t('Intensità delle sfumature')" />
      <span class="grow" />
      <button class="ghost small" @click="resetLook">{{ t('Colori predefiniti') }}</button>
    </div>
  </div>
</template>

<style scoped>
.palette-panel { display: grid; gap: 10px; padding: 10px 12px; margin-top: 8px; border-radius: 10px;
  background: var(--surface); border: 1px solid var(--border); }
.pp-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.pp-label { color: var(--muted); min-width: 90px; }
.pp-list { display: flex; gap: 8px; flex-wrap: wrap; }
.pp-item { display: grid; gap: 4px; justify-items: center; padding: 6px 8px; border-radius: 8px;
  background: var(--surface-2, var(--bg)); border: 2px solid transparent; cursor: pointer; color: var(--text); }
.pp-item.active { border-color: var(--accent); }
.pp-swatches { display: flex; }
.pp-swatches i { width: 12px; height: 18px; display: block; }
.pp-swatches i:first-child { border-radius: 4px 0 0 4px; }
.pp-swatches i:last-child { border-radius: 0 4px 4px 0; }
.pp-dot { width: 24px; height: 24px; border-radius: 50%; padding: 0; cursor: pointer;
  border: 2px solid var(--surface); box-shadow: 0 0 0 1px var(--border); }
.pp-dot.active { box-shadow: 0 0 0 2px var(--accent); }
.pp-range { width: 140px; }
</style>
