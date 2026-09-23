# TODO

## Prossimi passi
- [ ] **GB per dispositivo e per tipologia**: attivare NetFlow in OPNsense (*Reporting → NetFlow*, interfaccia LAN, *Capture local*) e leggerlo da `/api/diagnostics/networkinsight/...`.
- [ ] Traffico per gli AP letti via SSH (NWA50AX PRO): trovare il comando CLI con i contatori delle interfacce.
- [ ] Verificare il formato di `show version` sugli NWA50AX PRO: modello, firmware e uptime oggi possono restare vuoti.
- [ ] Deploy sul server Docker e accesso remoto via VPN (Tailscale/WireGuard).

## Non fattibili con Nebula Base (verificato: API 403)
- Tutti gli endpoint di sito dell'OpenAPI (firmware, online-status, wlan-settings, band-mode, rate-limit, reporting) rispondono 403 anche con il siteId corretto: riservati alla licenza Pro.
