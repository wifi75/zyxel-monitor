# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/it/1.1.0/) — versioni: [SemVer](https://semver.org/lang/it/).

## [0.11.0] - 2026-09-24
### Aggiunto
- Impostazioni del sito: password della rete (applicata solo quando la cambi, mai mostrata), rete nascosta, dispositivi bloccati per MAC.

### Modificato
- Salvando un'impostazione si applica solo quella: ogni ingresso in un profilo ricarica le radio dell'AP per qualche secondo, quindi si inviano solo le differenze.

## [0.10.1] - 2026-09-24
### Corretto
- AP con firmware 6.x (WAC6103D-I, NWA1123-AC PRO) letti via SSH: orario di connessione dei client nel formato "ora data".

## [0.10.0] - 2026-09-24
### Aggiunto
- Configurazione → **Impostazioni del sito**, applicate a tutti gli AP e ricontrollate ogni 15 minuti: nome della rete, limiti di download/upload, roaming assistito 802.11k/v e veloce 802.11r, espulsione dei segnali deboli, bilanciamento del carico, LED spenti, SNMP in scrittura, server NTP, hostname uguale al nome della dashboard.
- Gestione AP → Strumenti → **Esplora comandi**: chiede all'AP le opzioni dei suoi profili (solo richieste di aiuto) per completare le impostazioni successive.

## [0.9.0] - 2026-09-24
### Aggiunto
- Interfaccia in italiano e inglese: bandierina per cambiare lingua, scelta automatica (italiano se il browser è in italiano, altrimenti inglese).
- Menu laterale per categorie (Monitoraggio, Gestione, Sistema) con icone e colori; barra superiore con titolo della pagina; su telefono il menu si apre con ☰.

### Modificato
- I messaggi della configurazione riportano solo il valore impostato.

## [0.8.0] - 2026-09-24
### Aggiunto
- Configurazione centralizzata di canale (automatico o fisso, compresi i canali DFS 100-140 della 5 GHz) e larghezza del canale, nel profilo del sito e per singolo AP. Il nome del profilo radio di ogni AP si legge dalla sua configurazione.

### Corretto
- Card AP: client attribuiti alla banda giusta anche sui modelli che non la indicano (si usa lo slot della radio); bande una per riga, testo non più troncato.

## [0.7.1] - 2026-09-24
### Modificato
- Configurazione: "30 dBm" diventa "Massima consentita", lo stato "limitato dall'AP" diventa "al massimo di legge" e ogni banda riporta i limiti italiani (2.4 GHz 20 dBm; 5 GHz 23 dBm sui canali 36-48, 30 dBm sui 100-140).

## [0.7.0] - 2026-09-24
### Aggiunto
- Accesso SSH anche per gli AP letti via SNMP (Gestione AP → Connessione): i dati restano da SNMP, configurazione centralizzata, backup e riavvio passano da SSH. Così tutti e 4 gli AP sono configurabili.

## [0.6.0] - 2026-09-24
### Aggiunto
- Pagina **Configurazione**: configurazione centralizzata della potenza radio per banda, con profilo del sito valido per tutti gli AP e personalizzazione per singolo AP.
- Applicazione immediata via SSH a tutti gli AP e riallineamento automatico se un AP torna indietro (riavvio o sincronizzazione di Nebula); segnalato "limitato dall'AP" quando l'AP non accetta il valore.
- Backup della configurazione completa (running-config) di ogni AP, consultabile, copiabile e scaricabile.
- Eventi "Configurazione" nello storico per ogni modifica applicata.

## [0.5.0] - 2026-09-24
### Aggiunto
- Gestione AP: CPU e memoria degli AP letti via SSH (`show cpu status`, `show mem status`).

### Corretto
- Pulsanti Copia funzionanti anche con la dashboard in http.
- Tolto `show wireless-hal current` dalla lettura SSH: sul firmware V7.12 richiede un parametro.

## [0.4.0] - 2026-09-24
### Aggiunto
- Deploy come stack Portainer da repository Git (`docker-compose.portainer.yml`), aggiornamento con *Pull and redeploy*.
- Pagina **Gestione AP**: aggiungi, modifica, disattiva, elimina; SNMP v1/v2c/v3 e SSH; rileva protocollo, prova connessione, riavvio via SSH, output CLI.
- **Impostazioni**: OPNsense e parametri di raccolta dal pannello; sezione Nebula OpenAPI (richiede licenza Pro).
- Dashboard a griglia: widget trascinabili e ridimensionabili, disposizione salvata per utente.
- Dispositivi mai visti (vista Dispositivi, riconosci/dimentica), storico del segnale per client e per AP, roaming fra AP.
- Linea Internet: latenza e perdita nel tempo, disponibilità, disservizi.
- Consumo per dispositivo da NetFlow di OPNsense (dati inviati).
- AP via SSH: uptime, traffico per radio e uplink, potenza e occupazione del canale, bande anche senza client.
- La pagina aperta si aggiorna da sola dopo un nuovo deploy.

### Modificato
- Siti visitati e DNS bloccati come classifiche a righe; torte compatte con legenda.
- Barra in alto su una riga con icone, indicatori e card AP colorati.

## [0.3.0] - 2026-09-23
### Aggiunto
- Sezione **Internet** (da OPNsense): stato della linea, latenza, perdita pacchetti, velocità WAN nel tempo e GB del periodo.
- Torta "Pubblicità e tracker bloccati" con i totali del DNS di Unbound.
- Siti più contattati da ogni singolo dispositivo (clic sulla riga del client).
- Endpoint `/api/internet`; parametro `ip` per `/api/sites`; variabile `OPNSENSE_WAN_IF`.

### Documentazione
- README: sezione controlli di qualità, badge test e lint.

## [0.2.0] - 2026-09-23
### Aggiunto
- Integrazione OPNsense (solo lettura): nomi dei dispositivi dai lease Kea DHCP e siti visitati dalle query DNS di Unbound.
- Torta "Siti più visitati" (generale e per AP), limitata ai dispositivi Wi-Fi.
- Vista dedicata per ogni access point: KPI, grafici, client e storico collegamenti.
- Torte: dispositivi per tipologia, traffico (GB) e client per AP, client per banda.
- Classificazione dei dispositivi dal nome (`devices.py`), endpoint `/api/usage` e `/api/sites`.
- Licenza MIT.
- Test automatici dei parser (pytest) e configurazione ruff.

### Modificato
- Uptime degli AP SNMP da `hrSystemUptime` (quello dell'agente ripartiva a ogni configurazione di Nebula).
- Il file `.env` si rilegge a ogni ciclo; cercato sia in `backend/` sia nella cartella principale.
- Default neutri per community SNMP e dominio locale: i valori reali stanno solo nel `.env`.
- Dipendenze frontend aggiornate (Vite 8, TypeScript 6).

### Corretto
- Un login SSH rifiutato non viene ritentato per 10 minuti: i tentativi ripetuti facevano bloccare l'IP del server dagli AP.
- Certificati TLS di OPNsense verificati con l'archivio del sistema operativo (`truststore`).

## [0.1.0] - 2026-09-23
### Aggiunto
- Collector SNMP v2c (MIB Zyxel) per WAC6103D-I e NWA1123-AC PRO: client, radio, traffico per SSID, uptime.
- Collector SSH (CLI interattiva) per NWA50AX PRO, dove Nebula non attiva l'agente SNMP.
- Risoluzione nomi dei client via DNS inverso e tabella ARP; alias manuali.
- Storico eventi: connessione, disconnessione, roaming, AP online/offline.
- Dashboard Vue 3: panoramica AP, grafici traffico/client, elenco client con ricerca, eventi.
- Login admin con password predefinita documentata e avviso finché non viene cambiata.
- Dockerfile multi-stage e docker-compose (rete host).
