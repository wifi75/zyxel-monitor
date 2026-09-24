<script setup lang="ts">
import { lang, setLang } from '../i18n'
</script>

<template>
  <button class="icon-btn lang-btn" :title="lang === 'it' ? 'Switch to English' : 'Passa all’italiano'"
          @click="setLang(lang === 'it' ? 'en' : 'it')">
    <!-- si mostra la bandiera della lingua attiva -->
    <svg v-if="lang === 'it'" viewBox="0 0 3 2" width="22" height="15" aria-label="Italiano">
      <rect width="1" height="2" fill="#009246" /><rect x="1" width="1" height="2" fill="#fff" /><rect x="2" width="1" height="2" fill="#ce2b37" />
    </svg>
    <svg v-else viewBox="0 0 60 30" width="22" height="15" aria-label="English">
      <clipPath id="uk"><path d="M0,0 v30 h60 v-30 z" /></clipPath>
      <clipPath id="ukd"><path d="M30,15 h30 v15 z v15 h-30 z h-30 v-15 z v-15 h30 z" /></clipPath>
      <g clip-path="url(#uk)">
        <path d="M0,0 v30 h60 v-30 z" fill="#012169" />
        <path d="M0,0 L60,30 M60,0 L0,30" stroke="#fff" stroke-width="6" />
        <path d="M0,0 L60,30 M60,0 L0,30" clip-path="url(#ukd)" stroke="#C8102E" stroke-width="4" />
        <path d="M30,0 v30 M0,15 h60" stroke="#fff" stroke-width="10" />
        <path d="M30,0 v30 M0,15 h60" stroke="#C8102E" stroke-width="6" />
      </g>
    </svg>
  </button>
</template>
