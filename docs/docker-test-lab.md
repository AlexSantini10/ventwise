# Docker Test Lab

Il Docker Test Lab è un'istanza locale e isolata di Home Assistant pensata per
provare VentWise manualmente, senza sensori, dispositivi o automazioni reali.
Usa sempre lo ZIP prodotto dal checkout corrente: ciò che si prova nel Lab è
quindi lo stesso contenuto distribuibile agli utenti, non una cartella dei
sorgenti montata in Docker.

> [!IMPORTANT]
> Il Lab non legge né modifica il profilo del tuo Home Assistant reale. Il suo
> profilo è separato e persistente sul computer locale. Un `reset` elimina solo
> quel profilo di prova.

## Prerequisiti

- Docker Desktop avviato e funzionante;
- Python disponibile nel terminale;
- un checkout del repository VentWise.

Da PowerShell, nella root del repository:

```powershell
docker info
python scripts/ha-local-docker-test.py up
```

Al primo avvio Docker scarica l'immagine di Home Assistant se non è già
presente, crea il pacchetto `ventwise-lab.zip`, installa l'integrazione nel
profilo del Lab e avvia Home Assistant su [http://localhost:8123](http://localhost:8123).

## Primo accesso

Un profilo appena creato non ha utenti registrati. Apri
[http://localhost:8123](http://localhost:8123) e completa l'onboarding di
Home Assistant creando un utente locale dedicato al Lab.

Poi apri dalla barra laterale **VentWise Test Lab**. VentWise è già configurato
con due stanze simulate: Camera e Soggiorno.

## Uso rapido

La dashboard contiene tutto ciò che serve per una prova immediata:

1. Modifica temperatura, umidità, CO₂, meteo o vento nei dati simulati.
2. Usa i toggle delle finestre per simulare i contatti aperto/chiuso.
3. Premi **Ricevi consiglio ora**.
4. Leggi raccomandazione, punteggio, motivazione, stato aggregato delle
   finestre e flag di raccomandazione attiva per ogni stanza.

Una richiesta manuale crea sempre una notifica persistente con il risultato
attuale: è una risposta esplicita al pulsante, non un invio automatico. Prima
del calcolo VentWise attende gli aggiornamenti di stato HA pendenti, quindi un
contatto appena aperto viene considerato anche se premi subito il pulsante.

I controlli VentWise consentono inoltre di abilitare/disabilitare integrazione,
notifiche, comfort automatico e fascia silenziosa, senza riconfigurare il Lab.

### Scenario finestre consigliato

1. Lascia chiusi tutti i contatti.
2. Imposta la Camera più calda dell'esterno.
3. Premi **Ricevi consiglio ora**: dovrebbe comparire un consiglio di apertura.
4. Apri il contatto sinistro o destro della Camera.
5. Premi di nuovo il pulsante: VentWise non deve suggerire di riaprire una
   finestra già aperta.

La Camera ha due contatti: l'apertura di uno qualunque produce lo stato
aggregato `open`.

### Scenari dati e trace

Il Lab include anche PM2.5, polline d'erba, allarme fumo esplicito e
temperatura superficiale della Camera. Le policy di esempio riducono il
beneficio di apertura quando PM2.5 raggiunge 25 µg/m³; nessun polline influisce
finché non viene configurata una policy personale. L'allarme fumo usa soltanto
il binary sensor dedicato e, con una finestra aperta, propone la chiusura.

Apri gli attributi di `sensor.camera_test_recommendation` per ispezionare
`core_action`, `delivered_action`, candidati, blocchi, penalità, qualità dati e
trace. La Camera include anche una calibrazione fisica completa: questa può
rifinire durata/confidenza o segnalare condensa, ma non cambia i blocchi.

## Comandi

## Collaudo manuale DDP

Esegui questa checklist solo dopo che tutti i test automatici sono verdi. Il
Lab non controlla finestre o altri dispositivi: ogni risultato resta una
raccomandazione e ogni evidenza resta nel profilo isolato del Lab.

1. Avvia una prova pulita con `python scripts/ha-local-docker-test.py reset`,
   poi `up`, completa l'onboarding e apri **VentWise Test Lab**.
2. Per ogni scenario modifica soltanto i controlli della dashboard, premi
   **Ricevi consiglio ora** e apri la card **Trace e qualità dati — Camera**.
3. Registra sempre: `scenario`; valori impostati; risultato osservato
   (`core_action`/`delivered_action`, durata, blocchi e soppressione); trace
   completo o screenshot della card. Un'anomalia va riportata insieme a quei
   quattro elementi, senza dati o endpoint personali.

| Scenario | Valori da impostare | Risultato atteso |
| --- | --- | --- |
| Comfort caldo / freddo | Camera 28 °C, esterno 20 °C; poi inverti (camera 19 °C, esterno 31 °C con contatto aperto) | `open`; poi `close` se la finestra è già aperta. |
| Umidità / CO₂ | Camera 22 °C, umidità 70%, esterno più secco; oppure CO₂ 1400 ppm | `ventilate`, con durata e trace di punteggio. |
| Nessun beneficio | Camera ed esterno 22 °C | `none`. |
| Contatti multipli | Prima tutti chiusi; poi apri uno dei due contatti Camera | Il primo consiglio è consegnabile; il secondo è soppresso come finestra già aperta. |
| Pioggia, temporale, vento o raffica | Seleziona `rainy` o `thunderstorm`; oppure porta vento/raffica oltre 14 m/s | Se la finestra è aperta: `close`; trace e blocco di sicurezza prevalgono su CO₂. |
| Fumo, PM e polline | Attiva fumo; PM2.5 a 25; polline erba a 25 | Fumo e polline `avoid` bloccano; PM `reduce` applica una penalità. |
| Conflitto CO₂ + pericolo esterno | CO₂ 1400 e uno fra pioggia, temporale, vento, fumo o polline avoid | Nessun `open`/`ventilate`; se aperta, `close`. |
| Fonte assente / obsoleta | Spegni **Weather Source Available**; per obsolescenza lascia invariati tutti gli input meteo per oltre 15 minuti | `critical_weather_unavailable`, qualità dati e trace espliciti. |
| Quiet hours, cooldown e stabilità | Usa i controlli VentWise; ripeti la stessa richiesta | L'azione core resta visibile, mentre quella consegnata può essere soppressa con la causa indicata. |
| Riavvio e modifica configurazione | `restart`; poi `reset`/`up` per verificare l'onboarding | Stato persistente e configurazione vengono ripristinati o ricreati in modo leggibile. |

La card trace mostra anche i dati utilizzati, scartati e in attesa; gli
attributi completi restano cliccabili su `sensor.camera_test_recommendation`.
La stessa procedura può essere ripetuta per il Soggiorno usando le sue entità.

| Comando | Effetto |
| --- | --- |
| `python scripts/ha-local-docker-test.py up` | Genera lo ZIP dal checkout corrente, lo installa e avvia il Lab. |
| `python scripts/ha-local-docker-test.py restart` | Ricostruisce e reinstalla lo ZIP, poi ricrea il container preservando il profilo. |
| `python scripts/ha-local-docker-test.py down` | Ferma e rimuove il container, ma conserva profilo, utente e dati. |
| `python scripts/ha-local-docker-test.py logs` | Mostra i log live del container; interrompi con `Ctrl+C`. |
| `python scripts/ha-local-docker-test.py reset` | Ferma il Lab ed elimina il suo profilo locale, compresi utente e dati. |

Per usare una porta o un'immagine differenti:

```powershell
python scripts/ha-local-docker-test.py up --port 8124
python scripts/ha-local-docker-test.py up --image ghcr.io/home-assistant/home-assistant:stable
```

## Aggiornare il Lab dopo modifiche al codice

Non è necessario costruire a mano un'immagine Docker. Dopo ogni modifica al
codice di VentWise esegui:

```powershell
python scripts/ha-local-docker-test.py restart
```

Il runner rigenera `ventwise-lab.zip` dal checkout, sostituisce esclusivamente
`custom_components/ventwise` nel profilo del Lab e controlla che la versione
installata corrisponda al manifest del pacchetto. Il profilo e l'utente restano
invariati.

Usa invece `reset` seguito da `up` quando devi verificare una prima installazione,
una migrazione di config entry oppure nuovi ID delle entità. Il reset è
distruttivo per il solo Lab; rifai l'onboarding dell'utente locale dopo l'avvio.

## Entità e stabilità degli ID

Le entità VentWise hanno ID tecnici deterministici e inglesi; la lingua cambia
solo le etichette visibili. Nel Lab, alcuni esempi sono:

- `button.ventwise_test_lab_request_recommendation`
- `switch.ventwise_test_lab_master_enable`
- `sensor.camera_test_recommendation`
- `sensor.living_room_recommendation`
- `binary_sensor.camera_test_active`

Questo permette di creare dashboard e automazioni di test senza dipendere dalla
lingua dell'interfaccia.

## Dove sono i dati

Su Windows il profilo è in `%LOCALAPPDATA%\VentWise-HA-Test`; su macOS e Linux
è in `~/.ventwise-ha-test`. Contiene il profilo Home Assistant e gli artefatti
del Lab, ma non viene incluso nel repository.

Non modificare manualmente `.storage` nel profilo: usa i comandi sopra oppure
l'interfaccia di Home Assistant. Il runner gestisce packaging e installazione
dell'integrazione in modo ripetibile.

## Problemi comuni

| Problema | Soluzione |
| --- | --- |
| Docker non parte | Avvia Docker Desktop e verifica con `docker info`. |
| La porta 8123 è occupata | Avvia con `--port 8124` e apri `http://localhost:8124`. |
| Modifiche non visibili | Esegui `restart`; il runner ricrea sempre lo ZIP. |
| `Entity not found` dopo modifiche agli ID | Esegui `reset`, poi `up`, e completa di nuovo l'onboarding. |
| Il Lab non completa l'avvio | Leggi `python scripts/ha-local-docker-test.py logs`. |

## Docker Lab e CI

Il Lab è per verifiche manuali e visuali. Non sostituisce la CI: i test unitari
e di integrazione Home Assistant devono passare prima di una release. Consulta
[Testing](testing.md) per la matrice automatizzata e
[Development workflow](development.md) per il flusso di sviluppo.
