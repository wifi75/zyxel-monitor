# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/it/1.1.0/) — versioni: [SemVer](https://semver.org/lang/it/).

## [0.25.0] - 2026-09-26
### Aggiunto
- Avvisi su Telegram: AP offline e di nuovo online, linea caduta e tornata, dispositivi nuovi, modifiche alla configurazione, canali saturi; un AP che manca a una sola lettura non genera avvisi. Report settimanale il lunedì mattina.
- Pagina Report (24 ore, 7 o 30 giorni): disponibilità, cadute, client medi e di picco, traffico e segnale per AP; linea Internet; dispositivi nuovi e più presenti.
- Widget Mappa della rete (Internet → router → AP → client per banda), Piano dei canali (sovrapposizioni, occupazione, canali consigliati da impostare in Nebula) e Firmware (versioni diverse sullo stesso modello).
- Produttore dal MAC con l'elenco pubblico IEEE, scaricato nell'immagine Docker; i MAC privati sono indicati come tali.
- Storico per dispositivo: collegamenti, roaming e segnale degli ultimi 7 giorni, aprendo la riga in Dispositivi.
- Client per banda anche in Panoramica.
- Blocco del login per 15 minuti dopo 5 password sbagliate; intestazioni di sicurezza e HSTS in HTTPS.
- README: HTTPS con HAProxy di OPNsense e accesso remoto con WireGuard.
### Modificato
- Grafici con i colori del tema chiaro/scuro, ridisegnati al cambio di tema.
- Pagine di gestione caricate solo quando si aprono e librerie in file separati: niente più pacchetto unico oltre i 500 kB.

## [0.24.3] - 2026-09-25
### Corretto
- Solo monitoraggio: la potenza si confronta sul valore impostato negli AP (`output-power`), non su quella reale che dipende dal modello.

## [0.24.2] - 2026-09-25
### Corretto
- Orari del Wi-Fi letti anche nel formato dei firmware 6.x (`mon enable HH:MM-HH:MM`); su quei firmware non vengono scritti finché la sintassi non è verificata.

## [0.24.1] - 2026-09-25
### Corretto
- Password della rete riconosciuta anche sui firmware 6.x (riga `wpa-psk`): "impostata" invece di "non leggibile".

## [0.24.0] - 2026-09-25
### Aggiunto
- Capacità per modello: intestazione con modello e generazione Wi-Fi; larghezze e sicurezza proposte solo se il modello le supporta (160 MHz e WPA3 solo Wi-Fi 6); un valore del sito oltre le capacità diventa il massimo del modello ("max del modello").
- Voci assenti nella configurazione di un AP mostrate come "non disponibile" e mai inviate.
### Modificato
- Solo monitoraggio: la colonna Sito mostra il valore che hanno adesso gli AP (quello di Nebula) e il ✓/⚠ confronta gli AP fra loro, non con le regole salvate del pannello.
- Larghezze coi nomi di Nebula (20/40/80/160 MHz); canali 2.4 GHz in ordine con 1/6/11 consigliati; logo e favicon.

## [0.22.0] - 2026-09-25
### Aggiunto
- Interruttore generale della gestione: spento (predefinito) il pannello solo monitora e non invia nulla agli AP.
- Anteprima dei comandi per ogni AP prima di applicare (password mascherate); annullando si rimettono i valori di prima.
- Prova controllata: la modifica va prima su un AP scelto, dopo 5 minuti si contano i dispositivi collegati e solo se non sono calati si estende agli altri.
- Ripristino automatico: se i dispositivi calano oltre il 30% ogni AP toccato torna al backup fatto subito prima e va in pausa; si elencano i dispositivi non rientrati.
### Modificato
- Salvare un'impostazione non la invia più agli AP: l'invio passa sempre dall'anteprima e dalla prova.

## [0.21.0] - 2026-09-25
### Aggiunto
- Pulsante Ripristina sui backup e pausa della gestione per singolo AP.

## [0.20.1] - 2026-09-24
### Modificato
- Configurazione: nome della rete 2.4 GHz e 5 GHz impostabili separatamente; stesso nome = un'unica rete.
### Corretto
- Icona del gruppo sulla stessa riga del titolo.

## [0.20.0] - 2026-09-24
### Aggiunto
- Tema chiaro e tema scuro a scelta (pulsante sole/luna, predefinito dal sistema), con file di token grafici.
### Modificato
- Barra del titolo a fondo pieno, controlli di altezza unica, icone al posto delle emoji; "in attesa" diventa "da applicare".

## [0.19.0] - 2026-09-24
### Modificato
- Pannello Roaming: una riga per access point con arrivi e partenze e i relativi AP.
### Aggiunto
- Configurazione: nome rete separato per i 5 GHz.

## [0.18.4] - 2026-09-24
### Modificato
- Pannello Roaming a coppie: andata e ritorno fra due access point sulla stessa riga (una riga per coppia invece che per direzione), con la barra che punta all'AP di arrivo e il totale della coppia. La coppia è segnata "rimbalza" quando tutte e due le direzioni arrivano alla soglia già usata per i dispositivi.

## [0.18.3] - 2026-09-24
### Aggiunto
- Indicatore Segnale debole: elenco dei dispositivi passando col mouse; cliccandolo la tabella dei client mostra solo quelli sotto -75 dBm.

## [0.18.2] - 2026-09-24
### Modificato
- Tabella di configurazione più leggibile: colonna Sito come pulsante con matita ("lascia all'AP" se non gestito), celle degli AP come testo semplice con ✓ allineato / ⚠ diverso, pallino verde/grigio per le funzioni accese/spente, spiegazioni in un'icona ⓘ, parole concrete (visibile/nascosta, accesi/spenti, sempre acceso).
### Corretto
- Password non letta sui firmware 6.x mostrata come "—" invece di "nessuna" e non più segnalata come diversa.

## [0.18.1] - 2026-09-24
### Corretto
- Applica modifiche: tutte le regole vengono salvate e poi applicate con un solo giro per AP (prima le radio si ricaricavano una volta per ogni modifica).
- Le voci sì/no gestite non risultano più sempre "diverse": il confronto usa i valori, non le etichette.
- Rete ospiti e orari del Wi-Fi si spengono con un valore vuoto; svuotare l'elenco dei MAC sblocca i dispositivi; una password vuota non cancella più quella impostata.
### Aggiunto
- Pulsante Riapplica per spingere subito la configurazione a tutti gli AP; backup chiudibili e limitati agli ultimi 8; colore diverso per ogni gruppo della tabella.

## [0.18.0] - 2026-09-24
### Modificato
- Pagina Configurazione rifatta come tabella di confronto: una riga per impostazione, colonna Sito (vale per tutti) e una colonna per AP con il valore attuale; caselle diverse in arancione, modifiche in attesa in viola e applicate insieme con "Applica modifiche"; backup apribili dalla barra.

## [0.17.0] - 2026-09-24
### Aggiunto
- Impostazioni del sito: orari del Wi-Fi (fascia giornaliera in cui la rete è accesa, con conferma). Completate tutte le 19 impostazioni dell'elenco.

## [0.16.0] - 2026-09-24
### Aggiunto
- Impostazioni del sito: riavvio programmato (ogni giorno, sabato o domenica alle 4:00).
- Gestione AP → Strumenti: uscita da Nebula (gestione locale, hybrid-mode standalone) e ritorno a Nebula, per singolo AP, con backup automatico prima e doppia conferma.

## [0.15.0] - 2026-09-24
### Aggiunto
- Impostazioni del sito: band steering (spento, standard, forzato).

## [0.14.0] - 2026-09-24
### Aggiunto
- Impostazioni del sito: sicurezza della rete (WPA2, WPA2+WPA3, solo WPA3, con conferma).
- Rete ospiti: seconda rete isolata dalla casa (guest-ssid) sui profili SSID2/SECURITY2, con nome e password propri; nome vuoto = spenta.

## [0.13.0] - 2026-09-24
### Aggiunto
- Configurazione radio: valore attuale letto dagli AP accanto a potenza, canale e larghezza di ogni AP, e riepilogo nel profilo del sito (uguale su tutti o diverso, dettaglio passando col mouse).

## [0.12.0] - 2026-09-24
### Aggiunto
- Impostazioni del sito: sotto ogni voce il valore attuale letto dagli AP (uguale per tutti o diverso, con il dettaglio passando col mouse). "Non gestito" significa che la dashboard non impone nulla e resta il valore dell'AP.
- Canale degli AP via SSH letto dal profilo radio della configurazione: numero se fisso, "automatico" se lo sceglie l'AP (DCS).

### Modificato
- Tolto show wlan all dalla lettura SSH: non riporta il canale.

## [0.11.1] - 2026-09-24
### Aggiunto
- AP via SSH: lettura del canale da show wlan all (formato da confermare con l'Output CLI).

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
