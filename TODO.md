# TODO

## Prossimi passi
- [x] GB per dispositivo e per tipologia da NetFlow (v0.4.0) — solo dati inviati.
- [ ] Download per dispositivo: verificare se Insight ha un totale per indirizzo di destinazione.
- [x] Traffico per gli AP letti via SSH: `show wireless-hal statistic` + `show port status` (v0.4.0).
- [ ] Canale degli AP SSH da `show wireless-hal current`: formato da confermare con l'Output CLI.
- [ ] CPU e memoria degli AP SSH (`show cpu status`, `show mem status`): parser da scrivere sull'output reale.
- [ ] AP estranei da `show rogue-ap detection`: sottocomandi da scoprire.
- [ ] SSH anche su GARAGE e GIARDINO (oggi SNMP): verificare l'accesso.
- [x] Formato di `show version` / `show system uptime` sugli NWA50AX PRO (v0.4.0).
- [x] Deploy sul server Docker come stack Portainer (v0.4.0).
- [ ] Accesso remoto via VPN WireGuard su OPNsense.

## Non fattibili con Nebula Base (verificato: API 403)
- Tutti gli endpoint di sito dell'OpenAPI (firmware, online-status, wlan-settings, band-mode, rate-limit, reporting) rispondono 403 anche con il siteId corretto: riservati alla licenza Pro.
