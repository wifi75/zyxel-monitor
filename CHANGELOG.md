# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/it/1.1.0/) — versioni: [SemVer](https://semver.org/lang/it/).

## [Non rilasciato]
### Aggiunto
- Integrazione OPNsense (solo lettura): nomi dei dispositivi dai lease Kea DHCP e siti visitati dalle query DNS di Unbound.
- Torta "Siti più visitati" (generale e per AP), limitata ai dispositivi Wi-Fi.
- Vista dedicata per ogni access point: KPI, grafici, client e storico collegamenti.
- Torte: dispositivi per tipologia, traffico (GB) e client per AP, client per banda.
- Classificazione dei dispositivi dal nome (`devices.py`), endpoint `/api/usage` e `/api/sites`.
- Licenza MIT.

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
