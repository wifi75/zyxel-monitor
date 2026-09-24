# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/it/1.1.0/) — versioni: [SemVer](https://semver.org/lang/it/).

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
