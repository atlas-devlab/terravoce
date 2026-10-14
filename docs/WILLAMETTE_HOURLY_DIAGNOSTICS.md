# Willamette a un'ora: capire gli errori prima del prossimo modello

[English explanation](WILLAMETTE_HOURLY_DIAGNOSTICS_EN.md)

Virdacora deve offrire previsioni verificabili alle comunità. Il risultato
precedente non basta: il ridge a otto ingressi migliora la media stagionale
dello 0,84%, ma peggiora in inverno, primavera e autunno. Gli intervalli
esplorativi del vantaggio comprendono zero. L'esito rimane
`observed-seasonal-tradeoff`, come nel
[test originale](WILLAMETTE_MULTISEASON_EXPERIMENT.md).

Questo incremento implementa una diagnosi offline del modello congelato.
Usa gli stessi archivi USGS e le stesse 2.591 coppie, senza nuovi download o
addestramento. Le finestre 2025 erano già state esaminate: la
[specifica diagnostica](datasets/willamette-hourly-diagnostics/protocol.json)
è dichiarata dopo quell'esame, non è una preregistrazione o un nuovo test finale.

## Cosa cambia nel codice

`scripts/forecast_diagnostics.py` controlla 38 impronte dei file di ingresso,
poi ripete la verifica già esistente del report multistagionale. Ricostruisce
la storia di dodici misure fino all'origine, controlla gli ID dei record e
scompone ogni previsione nella somma degli otto contributi standardizzati
più l'intercetta. Questi contributi descrivono il calcolo della regressione:
non sono cause fisiche né una graduatoria universale dei fattori importanti.

Il [report](evidence/willamette-hourly-diagnostics/report.json) divide gli errori
in tre modi: target futuro uguale/diverso dall'ultima misura; dodici misure
passate tutte uguali/in cambiamento; incrocio dei due gruppi. Ogni divisione
conserva tutte le coppie e ricompone la MAE originale. I gruppi vuoti hanno
metriche `null`, senza inventare un errore zero.

**Il target futuro serve soltanto alla diagnosi.** Non si può decidere di
usare la persistenza sapendo già che il target sarà uguale all'ultima misura.
Il controllo della storia passata è diverso e non usa il target.

## Cosa abbiamo trovato

| Finestra | Target uguali all'ultima misura | Storie con dodici misure tutte uguali | Di queste, target poi cambiati |
| --- | ---: | ---: | ---: |
| Inverno | 555 / 637 | 371 | 19 |
| Primavera | 482 / 647 | 124 | 26 |
| Estate | 149 / 647 | 0 | 0 |
| Autunno | 354 / 660 | 30 | 11 |

In inverno la persistenza ha errore zero sui 555 target invariati; la
regressione introduce una MAE di 0,015532 mg/L. Quando invece il target cambia,
la sua MAE è 0,083478 contro 0,100000 della persistenza. Il beneficio su una
parte dei casi viene quindi superato dal costo delle correzioni negli altri.
È una decomposizione aritmetica, senza dimostrare perché il fiume si comporti così.

Anche una storia completamente piatta non garantisce un target invariato:
19 delle 371 storie invernali piatte hanno un cambiamento successivo. In estate
non ci sono storie piatte secondo questa definizione precisa. I numeri riguardano
valori registrati, non la perfetta costanza fisica dell'ossigeno.

## I due cali estivi

| Origine UTC | Ultima misura mg/L | Previsione a un'ora mg/L | Target UTC | Target registrato mg/L |
| --- | ---: | ---: | --- | ---: |
| 18 luglio 2025, 05:00 | 8,5 | 8,535660 | 06:00 | 3,5 |
| 20 luglio 2025, 06:30 | 8,3 | 8,293159 | 07:30 | 3,8 |

Il report conserva 20 punti per episodio, dall'origine meno 5,5 ore al target
più 3 ore, con ossigeno, temperatura e portata. I punti successivi all'origine
sono marcati `future-diagnostic-only`. Per esempio, la misura delle 05:30
del 18 luglio è già futura per una previsione emessa alle 05:00, anche se
precede il target delle 06:00. Il test verifica che questi dati non entrino
negli ingressi della previsione emessa all'origine.

Le serie vicine mostrano 8,5 → 8,1 → 3,5 → 6,4 → 6,9 mg/L il 18 luglio,
e 8,3 → 7,2 → 3,8 → 5,7 → 5,2 mg/L il 20 luglio. Nelle serie conservate la
portata passa da negativa a positiva vicino ai cali. È un'associazione
temporale: non stabilisce una causa o la verità fisica della misura.

La portata conserva il segno: `value` e `valueUnit` rappresentano m³/s,
`sourceValue` e `sourceUnit` conservano il valore originale in ft³/s.
Non sostituiamo dati mancanti o esclusi con zero o interpolazioni.
La portata è nel contesto diagnostico e nell'allineamento, ma non negli
otto ingressi della regressione congelata. Vento, nuvole, umidità, inquinanti
e attività umane non sono ancora ingressi di questo modello.

I target originali sono `c80b70af-704b-4edc-8636-d6cf49410efc` e
`fba3b442-adce-4f3e-86ba-090b56f550f9`, `Approved` e senza qualificatori
nella cattura. La modifica riportata dalla fonte è del 29 aprile 2026:
non prova quale dato fosse disponibile online nel luglio 2025. Conserviamo
ID, qualità e `lastModified` per rendere questo limite controllabile.
Il filtro illustrativo sotto 5 mg/L seleziona questi due esempi; non è una
soglia ecologica/legale validata né una prova di capacità delle allerte.
Entrambi restano nel punteggio originale.

## Ripetere la verifica

Dalla radice del repository, con Python 3.10 o successivo:

```sh
python scripts/forecast_diagnostics.py verify
python -m unittest discover -s scripts -p 'test_forecast_diagnostics.py' -v
```

Per creare una nuova copia del report, senza sovrascrivere quella conservata:

```sh
python scripts/forecast_diagnostics.py run --output outputs/willamette-hourly-diagnostics/report.json
```

Lo stesso percorso è disponibile come `pnpm forecast:diagnose` e
`pnpm forecast:diagnose:verify`, con Python nel PATH. Su Linux può essere
necessario sostituire `python` con `python3` nei comandi diretti. La CI usa
`python3` e riproduce il report senza rete. `run` rifiuta un file già esistente;
`verify` controlla struttura, testi, conteggi, impronte e numeri entro 1e-9.
La tolleranza è aritmetica, non ambientale.

Otto nuovi test controllano gruppi e denominatori, storia completa, numeri
non finiti, ricostruzione dei contributi, dati mancanti, portata con segno,
impronte alterate rifiutate prima del replay e assenza di addestramento.
Un test cambia soltanto misure successive all'origine e verifica che gli
ingressi e la previsione congelata rimangano identici, mentre il target cambia.

## Il prossimo esperimento da concordare

Una candidata ragionevole è ridurre la correzione della regressione, o tornare
alla persistenza, quando un criterio definito sui soli dati passati suggerisce
che correggere sia poco utile. È un'ipotesi da verificare, non un miglioramento
dimostrato. Non abbiamo applicato una nuova regola o scelto una soglia sui due cali.

Prima del prossimo fit vanno congelati ricetta, periodi di sviluppo/scelta,
un ulteriore periodo di verifica non usato per quelle scelte, confronto con
persistenza, metriche stagionali e calcolo dell'incertezza. Le finestre già
esaminate possono aiutare lo sviluppo, senza diventare il nuovo esame finale.
Se includeremo la portata o il meteo, serviranno identità, unità, orari di
pubblicazione e disponibilità di ciascun ingresso al momento della previsione.

Restiamo sulla previsione di ossigeno a un'ora: questa diagnosi non cambia
l'Oracle operativo, il voto delle comunità e dei giovani, il quorum o i fondi.
Non produce un LLM, nuove previsioni live o una fascia predittiva calibrata.
Le prove e i limiti restano visibili, come richiesto dalla missione di Virdacora.

Riferimenti: [valutazione temporale delle previsioni](https://otexts.com/fpp3/toolbox.html#time-series-cross-validation)
e [API ufficiali USGS](https://api.waterdata.usgs.gov/docs/ogcapi/).
