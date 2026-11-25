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
profilo del Lab (incluso il core standalone vendorizzato) e avvia Home
Assistant su [http://localhost:8123](http://localhost:8123).

Il profilo del Lab configura il server Home Assistant in italiano prima di
creare le entità VentWise. Questo è importante perché Home Assistant
memorizza il nome tradotto dell'entità quando viene registrata per la prima
volta. Dopo aver cambiato la lingua del server, usa `reset` e `up` per
ricreare le entità con i nomi nella nuova lingua.

## Primo accesso

Un profilo appena creato non ha utenti registrati. Apri
[http://localhost:8123](http://localhost:8123) e completa l'onboarding di
Home Assistant creando un utente locale dedicato al Lab.

Poi apri dalla barra laterale **VentWise Test Lab**. VentWise è già configurato
con due pagine e due istanze:

- **VentWise Core Lab**: una sola stanza, senza finestre e senza delivery;
  mostra esclusivamente il risultato del motore deterministico.
- **VentWise Test Lab**: Camera e Soggiorno, contatti finestra, notifiche,
  quiet hours, cooldown e stabilità.

### Headless Chrome authentication

Headless dashboard checks must use a dedicated Chrome profile, never a personal
browser profile. Bootstrap it once with:

```powershell
python scripts/ha-headless-browser.py bootstrap
```

Complete the local Home Assistant login manually in the opened browser, close
that window, and verify the session before every headless check:

```powershell
python scripts/ha-headless-browser.py check
```

The profile is stored outside the repository under
`%LOCALAPPDATA%\\VentWise-HA-Headless-Chrome`. The helper never stores or logs
credentials and exits non-zero if the Lab redirects to the authorization page.
Use `VENTWISE_HEADLESS_PROFILE` only when an equivalent dedicated profile is
stored outside the repository.

If `check` reports that the profile is still in use, close the dedicated Chrome
window completely and retry. Chrome must not have a background process holding
the profile lock while the headless check runs.

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

La pagina **VentWise Core Lab** usa gli stessi preset ma mostra solo il
risultato della config entry core. Confronta `sensor.core_engine_room_*` con
`sensor.camera_test_*` nella pagina completa per verificare che l'azione core
non venga modificata dalla delivery HA.

### Headless result interpretation

The authenticated headless harness compares the authoritative
`sensor.camera_test_core_recommendation` state. The delivery sensor may remain
`none` because stability, cooldown, quiet-hours, or notification availability
filters affect delivery only. The `Open recommendation` and `Humidity exchange`
presets may therefore produce either `open` or `ventilate` in the core result;
the CO2 threshold preset is inclusive, so `1000 ppm` produces `ventilate`.

### Scenario finestre consigliato

1. Lascia chiusi tutti i contatti.
2. Imposta la Camera più calda dell'esterno.
3. Premi **Ricevi consiglio ora**: dovrebbe comparire un consiglio di apertura.
4. Apri il contatto sinistro o destro della Camera.
5. Premi di nuovo il pulsante: VentWise non deve suggerire di riaprire una
   finestra già aperta.

La Camera ha due contatti: l'apertura di uno qualunque produce lo stato
aggregato `open`.

## v0.18 preset buttons

The dashboard includes preset buttons. Select a preset, press **Receive
recommendation now**, and inspect the room result cards. The presets are
deterministic and use these values:

| Preset | Main values | Expected check |
| --- | --- | --- |
| Reset neutral | Room 22 °C / 50% RH / 700 ppm; outside 22 °C / 50% RH / 2 m/s; sunny; windows closed | Neutral baseline |
| Open recommendation | Bedroom 28 °C / 55% RH; outside 18 °C / 45% RH / 2 m/s; sunny; windows closed | Opening advice for the bedroom |
| Humidity exchange | Rooms 24 °C / 75% RH; outside 20 °C / 35% RH / 2 m/s; sunny; windows closed | Moisture-exchange influence |
| CO2 influence | Bedroom 23 °C / 50% RH / 1800 ppm; outside 22 °C / 45% RH / 2 m/s; sunny | Bounded CO₂ influence |
| Weather block | Bedroom 28 °C; outside 18 °C / 2 m/s; lightning-rainy; windows closed | No opening advice under severe weather |
| Wind block | Bedroom 28 °C; outside 18 °C / 15 m/s; sunny; windows closed | No opening advice under high wind |
| Gust block | Bedroom 28 °C; outside 18 °C / 2 m/s with 15 m/s gust; sunny | Gust threshold uses the restrictive value |
| Urgent close | Bedroom 23 °C; outside 5 °C / 15 m/s; lightning-rainy; left bedroom window open | Urgent close advice is not suppressed |
| Multi-room split | Bedroom 28 °C, living room 18 °C; outside 22 °C / 2 m/s; sunny; windows closed | Independent room recommendations |
| Close recommendation | Bedroom 20 °C; outside 30 °C; bedroom window open | Closing advice when indoor air is better |
| Ventilate recommendation | Bedroom 25 °C; outside 18 °C | Brief ventilation action |
| Winter symmetry | Bedroom 16 °C; outside 22 °C | Winter-side comfort symmetry |
| Marginal benefit | Bedroom 22.3 °C; outside 22 °C | No meaningful recommendation |
| CO₂ threshold | Bedroom CO₂ 1000 ppm | Threshold boundary |
| Window already open | Open scenario plus one bedroom contact open | No repeated opening advice |
| Multiple contacts | Open scenario plus both bedroom contacts open | Deterministic aggregate window state |

The buttons only change the isolated Lab helpers. They do not control real
devices or the user's Home Assistant instance. The **Reset neutral** preset is
safe to use between scenarios.

The **Delivery filter checks** card explains how to test quiet hours,
stability, cooldown, duplicate suppression, and unavailable notification
channels. These checks must change only notification delivery; the raw
`core_result` card must remain unchanged.

## Comandi

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
`custom_components/ventwise` nel profilo del Lab, incluso il package runtime
incluso nel pacchetto release sotto `ventwise_core/`. Controlla inoltre che
la versione installata corrisponda al manifest del pacchetto. Il profilo e
l'utente restano invariati.

Usa invece `reset` seguito da `up` quando devi verificare una prima installazione,
una migrazione di config entry oppure nuovi ID delle entità. Il reset è
distruttivo per il solo Lab; rifai l'onboarding dell'utente locale dopo l'avvio.

Se i log riportano che la config entry del Lab ha una versione maggiore di
quella supportata dall'integrazione, il profilo contiene dati di una vecchia
baseline incompatibile. Esegui `reset` seguito da `up`; non modificare il
profilo `.storage` manualmente.

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
