# TODO

## Prossimi passi
- [x] GB per dispositivo e per tipologia da NetFlow (v0.4.0) — solo dati inviati.
- [ ] Download per dispositivo: verificare se Insight ha un totale per indirizzo di destinazione.
- [x] Traffico per gli AP letti via SSH: `show wireless-hal statistic` + `show port status` (v0.4.0).
- [x] Canale degli AP SSH (dalla running-config).
- [x] CPU e memoria degli AP SSH.
- [ ] AP estranei da `show rogue-ap detection`: sottocomandi da scoprire.
- [x] SSH su tutti e 4 gli AP.
- [x] Formato di `show version` / `show system uptime` sugli NWA50AX PRO (v0.4.0).
- [x] Deploy sul server Docker come stack Portainer (v0.4.0).
- [ ] Accesso remoto via VPN WireGuard su OPNsense.
- [ ] HTTPS per il pannello.
- [ ] Avvisi Telegram (facoltativi).
- [ ] Grafici con i colori del tema chiaro/scuro; revisione pagina per pagina nei due temi e su smartphone.

## Configurazione centralizzata (verso il distacco da Nebula)
- [x] Potenza per banda: profilo del sito + personalizzazione per AP, riallineamento automatico (v0.6.0).
- [x] Backup della running-config di ogni AP (v0.6.0).
- [ ] Verificare quanto regge una modifica con Nebula attivo (prova su SOGGIORNO a 17 dBm del 2026-09-24).
- [ ] Prova sul campo delle 20 impostazioni della pagina Configurazione, una alla volta (nessuna ancora verificata su un AP reale), compresi canale/larghezza e nome rete 5 GHz separato (profilo `SSID5G`).
- [x] SSID e password gestibili dal pannello (v0.17+).
- [ ] Distacco da Nebula (`hybrid-mode`): solo dopo backup e prova su un AP, con cavo a portata di mano.
- [ ] SNMP con community `ZyxelAP` anche in scrittura (rw) impostata da Nebula: da togliere.

## Non fattibili con Nebula Base (verificato: API 403)
- Tutti gli endpoint di sito dell'OpenAPI (firmware, online-status, wlan-settings, band-mode, rate-limit, reporting) rispondono 403 anche con il siteId corretto: riservati alla licenza Pro.
