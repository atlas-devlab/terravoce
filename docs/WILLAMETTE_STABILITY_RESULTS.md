# Willamette a un'ora: risultato della prova con dati nuovi

[English explanation](WILLAMETTE_STABILITY_RESULTS_EN.md).

**La regola riduce l'errore della regressione, ma non supera la persistenza.**
Il risultato del test congelato è `no-overall-improvement`: non soddisfa i
criteri concordati e non viene promosso nell'Oracle operativo.

## 1. La domanda e la regola

Prevediamo l'ossigeno disciolto un'ora dopo l'origine alla stazione
USGS-14211720, Willamette River at Portland, Oregon. Riutilizziamo il ridge
a otto ingressi, alpha=100, già appreso su 2.559 coppie del 2024. Pesi, medie
e scale rimangono identici. Questo test non contiene un nuovo addestramento.

La sola modifica, fissata nel [protocollo](WILLAMETTE_STABILITY_PROTOCOL.md),
annulla l'intera correzione del ridge se tutte le dodici misure precedenti
di ossigeno, distanziate di 30 minuti, sono numericamente uguali. Altrimenti
usa la stessa previsione completa. La decisione non riceve il valore futuro.
L'uguaglianza riguarda la precisione pubblicata, non la stabilità fisica del fiume.

## 2. Cosa è stato fissato prima di leggere i risultati

Protocollo e calendario erano nel commit `14a7603`. Raccoglitore, valutatore,
dipendenze e test sono stati salvati e inviati su GitHub nel commit
`e8b4e133aa81ecda548480991584239a8ed142ea` prima delle nuove richieste USGS.
I manifesti legano le catture a quel commit, a un inventario di 14 file,
all'impronta del protocollo e all'impronta dei pesi. Il protocollo JSON
conserva la fase originaria pre-acquisizione: non è stato riscritto dopo il test.

Il raccoglitore crea un marcatore esclusivo persistente prima della prima
richiesta. Un secondo avvio o una ripartenza dopo un'interruzione non può
riscaricare silenziosamente le finestre. Conserva le risposte originali
compresse e le loro SHA-256; conserverebbe anche risposte parzialmente riuscite
o corpi completi di errori HTTP. Le dodici richieste di questa prova sono riuscite.

Questa sequenza è verificabile nel repository; Git e le impronte locali non
costituiscono una marcatura temporale esterna fidata o una prova della verità
fisica del sensore. Non è stata pubblicata una nuova attestazione blockchain.

## 3. Dati reali e completezza

Le quattro finestre storiche del 2025 erano distinte dagli undici periodi già
acquisiti. Ogni periodo comprende 28 giorni e 1.332 possibili origini, considerando
la storia iniziale e il target a un'ora. Tutti gli orari sono UTC e gli estremi
delle query sono inclusi. Usiamo dati USGS approvati, senza qualificatori,
con identità, serie, unità e tempi controllati. Non interpoliamo i vuoti.

| Stagione e intervallo UTC | Coppie accettate | Copertura | Storie invarianti |
| --- | ---: | ---: | ---: |
| Inverno, 1 febbraio–1 marzo | 1.276 / 1.332 | 95,80% | 439 |
| Primavera, 1–29 maggio | 1.320 / 1.332 | 99,10% | 42 |
| Estate, 1–29 giugno | 1.298 / 1.332 | 97,45% | 0 |
| Autunno, 1–29 novembre | 1.319 / 1.332 | 99,02% | 52 |

Tutte le finestre superano il filtro del 90% e di almeno 1.000 coppie.
Sono utilizzate 5.213 coppie su 5.328 origini teoriche; 115 non sono utilizzabili
per l'allineamento completo delle misure richieste. Gli orari assenti restano
nel denominatore. Le 42.983 osservazioni nelle dodici risposte superano i
controlli di qualità sui singoli record; questo non elimina i vuoti temporali.
La portata con segno viene conservata per la selezione e la diagnosi, pur
non entrando negli otto ingressi del modello.

## 4. Il confronto sugli stessi orari

La MAE è la media degli errori assoluti in mg/L: più bassa è, meglio è.
La riga finale è la media delle quattro MAE stagionali, con uguale peso alle
stagioni, come stabilito prima del test.

| Periodo | Ultima misura invariata | Ridge originale | Ridge con regola |
| --- | ---: | ---: | ---: |
| Inverno | 0,017085 | 0,028469 | 0,024586 |
| Primavera | 0,083333 | 0,089813 | 0,089723 |
| Estate | 0,201695 | 0,193600 | 0,193600 |
| Autunno | 0,053980 | 0,062337 | 0,061973 |
| **Media stagionale** | **0,089023** | **0,093555** | **0,092470** |

La candidata migliora il ridge di 0,001084 mg/L, pari all'1,1591%, ma peggiora
la persistenza di 0,003447 mg/L, pari al 3,8720%. Tre stagioni rimangono peggiori
della persistenza. L'estate migliora rispetto alla persistenza del 4,0135% circa,
ma non contiene storie invarianti: lì la nuova regola non è esercitata e la
previsione rimane esattamente quella del ridge.

La RMSE, una metrica secondaria che pesa maggiormente gli errori grandi,
è invece inferiore alla persistenza in tutte e quattro le finestre:

| Stagione | RMSE persistenza, mg/L | RMSE candidata, mg/L |
| --- | ---: | ---: |
| Inverno | 0,041334 | 0,040482 |
| Primavera | 0,149848 | 0,139865 |
| Estate | 0,338969 | 0,303065 |
| Autunno | 0,089646 | 0,085858 |

Questo indica un compromesso descrittivo tra le due misure dell'errore;
non rende positivo il test primario. Non abbiamo calcolato intervalli sulla
RMSE né sostituito il criterio MAE dopo aver visto i risultati.

## 5. Quanto regge il risultato

Il bootstrap appaiato ricampiona gli stessi blocchi per tutti e tre i metodi,
all'interno di ciascuna stagione, con 5.000 ripetizioni e seme fissato. Il
vantaggio è l'errore del riferimento meno l'errore della candidata: positivo
significa che la candidata fa meglio.

| Blocco | Intervallo esplorativo 95% del vantaggio sulla persistenza, mg/L | Sul ridge, mg/L |
| --- | ---: | ---: |
| 48 ore, principale | [-0,005432; -0,001667] | [0,000785; 0,001375] |
| 24 ore | [-0,005008; -0,001943] | [0,000779; 0,001425] |
| 72 ore | [-0,005191; -0,001722] | [0,000765; 0,001390] |

Nei limiti di queste finestre e del metodo di ricampionamento, la conclusione
rimane la stessa: miglioramento sul ridge, peggioramento sulla persistenza.
Questi intervalli non sono fasce predittive per la prossima misura e non
garantiscono una copertura congiunta del 95% o un'utilità ecologica.

## 6. Cosa impariamo e quali limiti restano

La regola interviene su 533 storie invarianti; in 99 di queste il target
successivo cambia. Riduce alcune correzioni inutili, ma la storia invariata
non garantisce che l'ossigeno rimanga invariato nell'ora seguente. Non abbiamo
scelto una soglia nuova o riaddestrato sui risultati appena osservati.

Il 29,47% dei casi invernali contiene una temperatura fuori dall'intervallo
di addestramento. È una diagnosi di extrapolazione, non una causa dimostrata
dell'errore. Il rapporto conserva anche RMSE, bias, 95° percentile, risultati
giornalieri, grandi errori e ogni storia completa. Non ci sono previsioni
negative o non finite. Non compaiono target sotto la soglia illustrativa di
5 mg/L: questa prova non valida allerte di ipossia.

Sono archivi finalizzati e revisionati nel 2026, non valori che abbiamo
pubblicato prima dell'ora osservata nel 2025. Non dimostrano disponibilità
storica degli ingressi in tempo reale, capacità su tutto il bacino, attribuzione
di inquinamento o benefici sul campo. Queste finestre sono ora materiale
osservato: una nuova regola richiederà una verifica separata.

La persistenza resta il riferimento da superare. Prima di ampliare l'orizzonte
a 24 ore o tre mesi, conviene studiare dove la correzione aiuta e dove introduce
errore, e fissare un nuovo esperimento. Le prove trasparenti supportano le
decisioni di comunità e giovani; questa prova di ricerca non autorizza spese
né modifica governance, quorum o tesoreria.

## 7. Riprodurre e controllare il risultato

Con Python 3.10+ e Git, dalla radice del repository, senza rete:

```sh
python scripts/evaluate_stability.py verify --report docs/evidence/willamette-stability/evaluation.json.gz
python scripts/audit_stability_evidence.py .
python -m unittest discover -s scripts -p 'test_*.py' -q
node --test scripts/test-capture-stability.mjs
```

La verifica del rapporto ricostruisce il risultato con i pesi congelati e ha
ottenuto differenza massima 0,0. Un secondo programma, scritto dopo la valutazione
per controllarne l'aritmetica, ricostruisce tutte le origini e le previsioni dai
JSON originali senza importare i moduli dell'esperimento: coincide entro 1e-9,
con differenza osservata 0,0. È un controllo indipendente del codice e del
calcolo, non una seconda misura indipendente del fiume. La suite passa 63 test
Python e 5 test Node, inclusi leakage temporale, manomissioni e doppio avvio.

Il [riepilogo JSON](evidence/willamette-stability/summary.json) contiene
conteggi, metriche e impronte; il [rapporto completo compresso](evidence/willamette-stability/evaluation.json.gz)
contiene tutte le righe. Il [notebook](notebooks/willamette-stability.ipynb)
accompagna la spiegazione senza nuovi download o fit.

Riferimenti: [misure continue USGS](https://api.waterdata.usgs.gov/docs/ogcapi/migration/),
[stazione](https://waterdata.usgs.gov/monitoring-location/USGS-14211720/),
[valutazione temporale delle previsioni](https://otexts.com/fpp3/tscv.html).
