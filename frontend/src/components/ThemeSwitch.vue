<script setup lang="ts">
import { t } from '../i18n'
import { setTheme, theme } from '../theme'
import Icon from './Icon.vue'
</script>

<template>
  <button class="icon-btn" :title="theme === 'dark' ? t('Tema chiaro') : t('Tema scuro')"
          :aria-label="theme === 'dark' ? t('Tema chiaro') : t('Tema scuro')"
          @click="setTheme(theme === 'dark' ? 'light' : 'dark')">
    <Icon :name="theme === 'dark' ? 'sun' : 'moon'" />
  </button>
</template>
