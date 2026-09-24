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
- Linea Internet: contatori WAN salvati nella tabella `samples` come AP fittizio `_internet` (esclusi da `/api/traffic` e `/api/usage`); stato gateway e totali DNS tenuti in memoria (`poller.internet_state`), non nel DB.
- La WAN di casa è la VLAN Fastweb `opt1` (`OPNSENSE_WAN_IF=opt1` nel `.env`), non `wan`.
- Commit senza trailer né riferimenti all'assistente.

## Scoperte (verificate il 2026-09-23)
- Nebula "Permit access… from designated IP" su *Deny all* bloccava tutto: aggiunto il range LAN.
- NWA50AX PRO: `show snmp status` → `active: no` nonostante SNMP attivo in Nebula; nessuna risposta v1/v2c/v3.
- CLI SSH: niente comandi in riga (`% session is not found`), serve una shell interattiva.
- Troppi login SSH falliti → l'AP rifiuta anche la password giusta; il riavvio da Nebula lo sblocca.
- SNMP a volte non risponde al primo colpo → `-t 3 -r 2`. `sysUpTime` è dell'agente: usare `hrSystemUptime`.
- Nebula OpenAPI su Base: 200 solo su `/organizations` e `/trial/status`; tutto il resto → 403, anche gli endpoint di sito con il siteId corretto (lo si legge nell'URL del portale Nebula).
- NetFlow di OPNsense spento (`/api/diagnostics/netflow/status` → inactive): serve per i GB per dispositivo.
- OPNsense risponde solo sul nome host (reverse proxy): con l'IP torna "Host non configurato".
- Python di macOS non usa il portachiavi → `truststore`. npm: `NODE_EXTRA_CA_CERTS` con i certificati esportati.
- iOS usa MAC privati: il nome giusto arriva dal lease DHCP (`iphone`), non dal vecchio record DNS.

## Stato
- v0.2.0 (2026-09-23): prima versione pubblica su github.com/wifi75/zyxel-monitor.
- v0.3.0 (2026-09-23): sezione Internet, DNS bloccati, siti per dispositivo. Nulla in sospeso in locale.
- v0.4.0 (2026-09-24): gestione AP e impostazioni dal pannello, dashboard a griglia, dispositivi, segnale, roaming, storico linea, NetFlow, AP SSH completi.
- Produzione: stack Portainer da Git (`docker-compose.portainer.yml`, porta 8200 con `PORT`), aggiornamento con *Pull and redeploy*; la pagina si ricarica da sola.
- AP, credenziali e OPNsense stanno nel DB (pannello), non più nel `.env`: il `.env` serve solo al primo avvio.
- NWA50AX PRO (fw V7.12) via SSH: traffico da `show wireless-hal statistic` (slot 1 = 2.4, 2 = 5 GHz) e `show port status`; nessun contatore in `show interface`. `reboot` senza argomenti riavvia.
- NetFlow Insight `FlowSourceAddrTotals` = byte **inviati** per indirizzo: i download non sono per dispositivo.
- Nebula OpenAPI: solo Pro; non esistono endpoint per potenza radio e canali. L'utente ha licenza Base.
- Controlli prima di ogni commit: `ruff check backend`, `(cd backend && pytest tests)`, `npm run build` (include vue-tsc): un errore di tipi blocca il deploy su Portainer.
- Versioning: bump a ogni blocco di lavoro chiuso, l'utente legge la versione nel piè di pagina per sapere dove si trova.
Vedi [TODO.md](TODO.md).
