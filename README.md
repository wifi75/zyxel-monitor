# Zyxel Monitor

[![Backend](https://img.shields.io/badge/Backend-FastAPI%200.141-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![Frontend](https://img.shields.io/badge/Frontend-Vue%203.5-4FC08D?logo=vuedotjs&logoColor=white)](https://vuejs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-6.0-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Vite](https://img.shields.io/badge/Build-Vite%208-646CFF?logo=vite&logoColor=white)](https://vite.dev)
[![Chart.js](https://img.shields.io/badge/Grafici-Chart.js%204.5-FF6384?logo=chartdotjs&logoColor=white)](https://www.chartjs.org)
[![Database](https://img.shields.io/badge/DB-SQLite-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org)
[![Docker](https://img.shields.io/badge/Deploy-Docker-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![Fonti](https://img.shields.io/badge/Fonti-SNMP%20%7C%20SSH%20%7C%20OPNsense-5A6B7B)](#come-legge-i-dati)
[![API](https://img.shields.io/badge/API-68%20endpoint-0A7EA4)](backend/app/api.py)
[![Test](https://img.shields.io/badge/Test-38%20pytest-0A9EDC?logo=pytest&logoColor=white)](backend/tests)
[![Lint](https://img.shields.io/badge/Lint-ruff-D7FF64?logo=ruff&logoColor=black)](ruff.toml)
[![SemVer](https://img.shields.io/badge/SemVer-2.0.0-blue)](https://semver.org/lang/it/)
[![Keep a Changelog](https://img.shields.io/badge/Changelog-Keep%20a%20Changelog-E05735)](CHANGELOG.md)
[![Mantenuto](https://img.shields.io/badge/Mantenuto-s%C3%AC%20(2026)-brightgreen)](https://github.com/wifi75/zyxel-monitor/commits)
[![Ultimo commit](https://img.shields.io/github/last-commit/wifi75/zyxel-monitor)](https://github.com/wifi75/zyxel-monitor/commits)
[![Stelle](https://img.shields.io/github/stars/wifi75/zyxel-monitor?style=flat)](https://github.com/wifi75/zyxel-monitor/stargazers)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

Monitoraggio self-hosted degli access point **Zyxel gestiti da Nebula Base**, cioè senza licenza Pro:
l'OpenAPI di Nebula su Base non espone client né statistiche, quindi i dati vengono letti in locale.

Cosa mostra la dashboard, in generale e per ogni singolo AP:
- stato degli AP (online, modello, firmware, uptime, canali, client per radio);
- client connessi con nome, tipologia, banda, segnale, velocità e durata della connessione;
- grafici di download, upload e numero di client nel tempo;
- torte: **siti più visitati** dai dispositivi Wi-Fi, dispositivi per tipologia, traffico e client per AP;
- storico di connessioni, disconnessioni, roaming e AP offline;
- con OPNsense: stato della linea Internet, velocità e GB della WAN, pubblicità e tracker bloccati, siti contattati da ogni dispositivo;
- mappa della rete, piano dei canali con sovrapposizioni e canali consigliati, firmware per modello;
- produttore di ogni dispositivo dal MAC (elenco IEEE) e storico per dispositivo di collegamenti, roaming e segnale;
- avvisi su Telegram (AP offline, linea caduta, dispositivi nuovi, canali saturi) e report settimanale.

## Come legge i dati

| Fonte | Cosa fornisce | Modelli / note |
|---|---|---|
| **SNMP v2c** (MIB Zyxel `1.3.6.1.4.1.890.1.15.3`) | client (MAC, SSID, RSSI, ora connessione), radio, traffico per SSID, uptime | WAC6103D-I, NWA1123-AC PRO |
| **SSH** (CLI `show wireless-hal station info`) | client con IP, banda, RSSI, velocità, standard Wi-Fi | NWA50AX PRO: in Nebula l'agente SNMP resta `active: no` |
| **OPNsense API** (facoltativa) | nomi dai lease Kea DHCP, siti visitati e bloccati (Unbound), stato gateway, contatori WAN | solo chiamate GET |
| DNS inverso / tabella ARP | nomi e IP di riserva | quando OPNsense non è configurato |

I nomi dei dispositivi si possono sovrascrivere dalla dashboard (*Rinomina*).

### Prerequisiti in Nebula
*Site-wide → Configure → General settings*:
- **SNMP access**: SNMPv2 attivo con una community a scelta;
- **Administrative Access**: SSH e SNMP spuntati;
- **Permit access… from designated IP addresses**: aggiungere l'IP del server di monitoraggio,
  altrimenti la regola predefinita *Deny all* blocca tutto.

### Prerequisiti in OPNsense (facoltativo)
- *Unbound DNS*: statistiche attive (`/api/unbound/overview/isEnabled` deve restituire `1`);
- una chiave API (*System → Access → Users → icona chiave*).

## Installazione con Docker

```bash
git clone https://github.com/wifi75/zyxel-monitor.git && cd zyxel-monitor
cp .env.example .env          # compilare almeno APS, SNMP_COMMUNITY, SSH_PASSWORD
docker compose up -d --build
```
Dashboard: `http://<ip-server>:8000` — documentazione API: `/docs`.

Il container usa `network_mode: host` per raggiungere gli AP e leggere la tabella ARP; dati in `./data`.

## Accesso

Credenziali iniziali: **utente `admin` — password `Admin12345`**.
Finché non viene cambiata, la dashboard mostra un avviso (pulsante *Password* in alto).

## Sviluppo locale

```bash
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
cd frontend && npm install && npm run build && cd ..
ln -s ../frontend/dist backend/static                         # la UI compilata servita dal backend
cd backend && ../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Per lavorare sulla UI con ricarica automatica: `cd frontend && npm run dev` (porta 5173, proxy su `/api`).

Su macOS servono `snmpget`/`snmpbulkwalk`, già presenti nel sistema. Se `npm` fallisce con
`UNABLE_TO_GET_ISSUER_CERT_LOCALLY`, esportare i certificati di sistema e passarli a Node:
```bash
security find-certificate -a -p /Library/Keychains/System.keychain /System/Library/Keychains/SystemRootCertificates.keychain > /tmp/ca.pem
NODE_EXTRA_CA_CERTS=/tmp/ca.pem npm install
```

## Controlli di qualità

Da eseguire prima di ogni commit (dalla cartella principale):
```bash
.venv/bin/ruff check backend                               # linter Python (regole in ruff.toml)
(cd backend && ../.venv/bin/python -m pytest -q tests)     # test dei parser
(cd frontend && npm run build)                             # build + controllo dei tipi (vue-tsc)
```

## Configurazione (`.env`)

| Variabile | Default | Descrizione |
|---|---|---|
| `APS` | 4 AP d'esempio | `NOME\|IP\|snmp o ssh`, separati da virgola |
| `SNMP_COMMUNITY` | `public` | community SNMP v2c impostata in Nebula |
| `SSH_USER` / `SSH_PASSWORD` | `admin` / — | *Local credentials* di Nebula |
| `OPNSENSE_URL` | — | es. `https://opnsense.example.lan` (usare il nome host se c'è un reverse proxy) |
| `OPNSENSE_KEY` / `OPNSENSE_SECRET` | — | chiave API di OPNsense |
| `OPNSENSE_VERIFY_TLS` | `true` | `false` solo per certificati autofirmati |
| `OPNSENSE_WAN_IF` | `wan` | interfaccia verso Internet (es. `opt1` se la linea è su una VLAN) |
| `LOCAL_DOMAIN` | — | dominio della LAN, escluso dai "siti visitati" |
| `POLL_INTERVAL` | `60` | secondi tra due letture |
| `RETENTION_DAYS` | `30` | giorni di storico |
| `SECRET_KEY` | generata | firma delle sessioni; se lasciata d'esempio viene creata in `data/secret.key` |

Il file `.env` si rilegge a ogni ciclo: una password corretta vale senza riavviare.

## Struttura

```
backend/app/
  main.py              avvio FastAPI, raccolta in background, UI statica
  api.py               endpoint REST (/api/...)
  poller.py            ciclo di raccolta: stato AP, client, eventi, campioni, DNS
  devices.py           tipologia del dispositivo dal nome
  collectors/          snmp.py · ssh.py · opnsense.py · names.py (ARP/DNS)
  core/                config.py · db.py (schema SQLite) · security.py (login) · version.py
backend/tests/         test pytest dei parser (SSH, siti DNS, tipologia dispositivi)
frontend/src/
  App.vue              panoramica (AP, Internet, torte), schede per AP, eventi
  components/          grafici (linee, torte), tabelle client ed eventi, login
```

## Sicurezza
- Il login SSH fallito non viene ripetuto per 10 minuti: gli AP Zyxel bloccano l'IP dopo troppi tentativi.
- Login del pannello: dopo 5 password sbagliate lo stesso utente è bloccato per 15 minuti.
- Intestazioni di sicurezza su ogni risposta (`nosniff`, niente iframe, niente referrer); HSTS quando si arriva in HTTPS.
- Il file `.env` (password, chiavi) è escluso da git.

### HTTPS
Il container parla solo HTTP: il certificato lo mette il reverse proxy davanti. Con OPNsense (plugin
`os-acme-client` e `os-haproxy`):
1. ACME: certificato per il nome del pannello (es. `wifi.casa.example`), validazione DNS.
2. HAProxy: *Real server* = IP del server Docker e porta del pannello; *Backend pool* con quel server;
   *Public service* in ascolto su 443 con il certificato ACME e l'intestazione `X-Forwarded-Proto: https`.
3. Unbound: *Host override* del nome verso OPNsense, così dalla LAN si arriva al proxy.

### Accesso da fuori casa
Non aprire la porta del pannello sul router: usare la VPN WireGuard di OPNsense.
1. *VPN → WireGuard → Instances*: nuova istanza (porta UDP 51820, rete del tunnel es. `10.10.10.1/24`).
2. *Peers*: un peer per ogni telefono o PC, con la sua chiave pubblica e un IP del tunnel (`10.10.10.2/32`).
3. *Firewall → Rules → WAN*: consenti UDP 51820; *Rules → WireGuard*: consenti il tunnel verso il server.
4. Sul telefono, app WireGuard con DNS = OPNsense: il pannello si apre col suo nome, come da casa.

## Licenza

[MIT](LICENSE) — Ideato e sviluppato da Tiziano Cassone
