# Memory — Zyxel Monitor

## Contesto
- 4 AP Zyxel in Nebula, licenza **Base**. Rete 192.168.1.0/24, router **OPNsense 26.7** (192.168.1.1).
- AP: ZONA NOTTE .11 e SOGGIORNO .12 (NWA50AX PRO, SSH) · GARAGE .13 (WAC6103D-I, SNMP) · GIARDINO .14 (NWA1123-AC PRO, SNMP).
- Valori reali (community SNMP, password SSH, chiavi OPNsense/Nebula, dominio LAN) **solo nel `.env`**, mai nel codice: il repo è pubblico.
- In locale gira sul Mac dell'utente, porta 8000 (`backend/static` è un link a `frontend/dist`).

## Decisioni
- SQLite invece di PostgreSQL: progetto piccolo per uso domestico.
- Frontend Vue 3 + TS (web, apribile dallo smartphone). Un'eventuale app Flutter userebbe le stesse API.
- Siti visitati = query DNS di Unbound (OPNsense), filtrate sui soli client Wi-Fi presenti nella tabella `clients`.
- Nomi: lease Kea DHCP > DNS inverso > IP; gli alias manuali hanno la precedenza su tutto.
- Licenza MIT.

## Scoperte (verificate il 2026-09-23)
- Nebula "Permit access… from designated IP" su *Deny all* bloccava tutto: aggiunto il range LAN.
- NWA50AX PRO: `show snmp status` → `active: no` nonostante SNMP attivo in Nebula; nessuna risposta v1/v2c/v3.
- CLI SSH: niente comandi in riga (`% session is not found`), serve una shell interattiva.
- Troppi login SSH falliti → l'AP rifiuta anche la password giusta; il riavvio da Nebula lo sblocca.
- SNMP a volte non risponde al primo colpo → `-t 3 -r 2`. `sysUpTime` è dell'agente: usare `hrSystemUptime`.
- Nebula OpenAPI su Base: 200 solo su `/organizations` e `/trial/status`; siti, dispositivi, firmware → 403.
- OPNsense risponde solo sul nome host (reverse proxy): con l'IP torna "Host non configurato".
- Python di macOS non usa il portachiavi → `truststore`. npm: `NODE_EXTRA_CA_CERTS` con i certificati esportati.
- iOS usa MAC privati: il nome giusto arriva dal lease DHCP (`iphone`), non dal vecchio record DNS.

## Stato
- v0.2.0 rilasciata il 2026-09-23 (prima versione pubblica su GitHub).
- Controlli prima di ogni commit: `ruff check backend`, `pytest backend/tests`, `npm run build` (include vue-tsc).
Vedi [TODO.md](TODO.md).
