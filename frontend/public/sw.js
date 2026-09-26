// Service worker minimo: rende il pannello installabile come app. Non tiene copie delle pagine né dei dati,
// così dopo un aggiornamento si vede sempre la versione nuova e i numeri non sono mai vecchi.
self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()))
self.addEventListener('fetch', () => { /* tutto dalla rete */ })
