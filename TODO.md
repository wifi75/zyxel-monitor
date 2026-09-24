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

## Configurazione centralizzata (verso il distacco da Nebula)
- [x] Potenza per banda: profilo del sito + personalizzazione per AP, riallineamento automatico (v0.6.0).
- [x] Backup della running-config di ogni AP (v0.6.0).
- [ ] Verificare quanto regge una modifica con Nebula attivo (prova su SOGGIORNO a 17 dBm del 2026-09-24).
- [ ] Canale e larghezza di banda (`wlan-radio-profile RADIO_SETTING_TYPE_2/5`, DCS attivo): da provare su un AP.
- [ ] SSID e password (`wlan-ssid-profile SSID1`, `wlan-security-profile SECURITY1`): necessari prima di lasciare Nebula.
- [ ] Distacco da Nebula (`hybrid-mode`): solo dopo backup e prova su un AP, con cavo a portata di mano.
- [ ] SNMP con community `ZyxelAP` anche in scrittura (rw) impostata da Nebula: da togliere.

## Non fattibili con Nebula Base (verificato: API 403)
- Tutti gli endpoint di sito dell'OpenAPI (firmware, online-status, wlan-settings, band-mode, rate-limit, reporting) rispondono 403 anche con il siteId corretto: riservati alla licenza Pro.
