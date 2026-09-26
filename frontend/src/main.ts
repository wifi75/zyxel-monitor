import { createApp } from 'vue'
import App from './App.vue'
import './style.css'
import './tokens.css'
import './theme'
import './i18n/en-main'
import './i18n/en-admin'
import './i18n/en-extra'
import './i18n/en-ops'

createApp(App).mount('#app')

// installabile come app sul telefono: il browser lo permette solo in HTTPS (o su localhost)
if ('serviceWorker' in navigator && window.isSecureContext) {
  navigator.serviceWorker.register('/sw.js').catch(() => { /* senza, il pannello funziona lo stesso */ })
}
