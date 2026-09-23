# TODO

## Prossimi passi
- [ ] **GB per dispositivo e per tipologia**: attivare NetFlow in OPNsense (*Reporting → NetFlow*, interfaccia LAN, *Capture local*) e leggerlo da `/api/diagnostics/networkinsight/...`.
- [ ] Traffico per gli AP letti via SSH (NWA50AX PRO): trovare il comando CLI con i contatori delle interfacce.
- [ ] Verificare il formato di `show version` sugli NWA50AX PRO: modello, firmware e uptime oggi possono restare vuoti.
- [ ] Deploy sul server Docker e accesso remoto via VPN (Tailscale/WireGuard).

## Non fattibili con Nebula Base (verificato: API 403)
- Avviso "firmware disponibile", impostazioni Wi-Fi e stato porte dall'OpenAPI di Nebula: riservati alla licenza Pro.
