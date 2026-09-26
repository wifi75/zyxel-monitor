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
- v0.20.1 (2026-09-24): configurazione a tabella di confronto (sito + colonna per AP, applicazione raggruppata per non ricaricare le radio a ogni modifica), roaming per AP, temi chiaro/scuro.
- Grafica: `frontend/src/tokens.css` (caricato dopo `style.css`) ridefinisce le variabili per `[data-theme=light|dark]`; tema chiaro "denso operativo" (Public Sans + IBM Plex Mono, blu petrolio), scuro "console" (IBM Plex Sans + JetBrains Mono, ciano). Scelta in `localStorage` `zm-theme`, altrimenti dal sistema. Icone solo dalla famiglia a tratto di `icons.ts`, niente emoji.
- Nome rete 5 GHz separato: copia del profilo SSID della 2.4 in `SSID5G` assegnata a `wlan slot2`; stesso nome = slot2 torna al profilo della 2.4.
- **Incidente 2026-09-25**: modifiche inviate dal pannello sopra la configurazione di Nebula (password, WPA2+WPA3 poi WPA2, potenze) → inverter in garage non rientrava; risolto spegnendo il pannello e riavviando gli AP (tornano alla config salvata da Nebula, il pannello non fa `write`). Regola: **un solo capo per la configurazione**; oggi Nebula configura e il pannello solo monitora.
- v0.24.3 (2026-09-25): protezioni in `guard.py` — interruttore generale spento di default (chiave `config_enabled` in `settings`), anteprima dei comandi con password mascherate, prova su un AP con verifica dei client dopo 5 min, ripristino automatico se calano oltre il 30% (`restore.py`, pausa per AP in `config_paused`). Salvare un'impostazione non la invia più: l'invio passa sempre da `/api/policy/rollout`.
- Capacità per modello in `capabilities.py`: Wi-Fi 6 = modelli "AX" (160 MHz, WPA3); Wi-Fi 5 fino a 80 MHz e solo WPA2. Voci assenti nella config di un AP = "non disponibile", mai inviate.
- Firmware 6.x (WAC6103D-I V6.28, output reale del 2026-09-25): password in chiaro su `wpa-psk` (7.x: `encrypted-wpa-psk`), orari come `mon enable 04:00-22:00` nel profilo SSID. Nebula ha `rssi-kickout -70` (Smart steering) e `dot11r activate`: sospetti per l'inverter.
- In solo monitoraggio la colonna Sito mostra il valore comune degli AP (quello di Nebula) e il ✓/⚠ confronta gli AP fra loro.
- v0.26.0 (2026-09-26): personalizzazioni per AP delle voci del sito in `site_config` con chiave `<voce>@ap:<id>` (`{"unmanaged": true}` = non gestita); `load()` restituisce solo il sito, `for_ap()` unisce. Occupazione del canale salvata in `samples` con iface `_util:<banda>`. Il 26/09 GARAGE è sceso dall'80% al 16% di occupazione dopo `reject-legacy-station` (attivato per errore dall'Esplora) e il riavvio delle radio: da confermare nel tempo col nuovo grafico.
- v0.25.7 (2026-09-26): capacità imparate per AP da Esplora comandi (chiave `caps:<AP>` in `settings`, firme in `capabilities.HELP_SIGNS`); velocità minima 2.4 GHz = `2g-wlan-rate-control` nel profilo radio, uguale su fw 6.28 e 7.12. Mai `?` su comandi senza valori: l'invio li esegue (successo con `reject-legacy-station` su GARAGE e ZONA NOTTE). Uscire e rientrare in un profilo radio fa ripartire la radio (righe "Setup 2.4G … channel").
- v0.25.1 (2026-09-26): tabelle nei widget con `flex-shrink: 0`, altrimenti con `overflow-x` si schiacciano e nascondono righe.
- v0.25.0 (2026-09-26): avvisi Telegram (`alerts.py`: eventi letti per id dalla tabella events, chiavi `alert_*` in `settings`, un AP giù per una sola lettura non avvisa), report (`report.py`, anche il lunedì su Telegram), piano canali (`channels.py`, solo consiglio), produttore dal MAC (`oui.py`; `oui.csv` IEEE scaricato nel Dockerfile con User-Agent da browser, altrimenti risponde 418), storico per dispositivo, blocco login. Colori dei grafici da `--series` in `tokens.css`. Su Windows i test partono da `backend` con `PYTHONPATH=.`.
Vedi [TODO.md](TODO.md).
