# Willamette a un'ora: come svilupperemo il filtro

[English explanation](WILLAMETTE_THRESHOLD_DEVELOPMENT_EN.md).

**Prima fissiamo come scegliere la soglia; poi faremo i conti sui dati già
studiati. Oggi nessuna soglia è stata scelta o dimostrata migliore.**
La MAE, cioè la media degli errori assoluti in mg/L, resta il criterio principale.

## 1. Un esempio semplice

L'ultima misura dell'ossigeno è 8,00 mg/L. La regressione propone 8,04.
Con una soglia illustrativa di 0,05 mg/L scartiamo la correzione di 0,04
e prevediamo 8,00. Se propone 8,30, conserviamo la previsione 8,30.
Se il valore reale futuro fosse 8,04, scartare la prima correzione sarebbe
uno svantaggio: il filtro può anche perdere. Lo verificheremo senza presumere
che tutte le correzioni piccole siano inutili.

La regola usa soltanto ultima misura e previsione della regressione:

```text
d = previsione_ridge - ultima_misura
se abs(d) <= soglia: previsione_filtrata = ultima_misura
altrimenti: previsione_filtrata = previsione_ridge
```

Il valore futuro serve a calcolare l'errore, mai a decidere se correggere.
I pesi del ridge rimangono congelati. Il vecchio fallback delle dodici misure
uguali resta un confronto: non lo sommiamo implicitamente al nuovo filtro.

## 2. Cinque soglie e un'opzione semplice

La griglia dichiarata è **0; 0,025; 0,05; 0,10; 0,20 mg/L**.
Con soglia zero la previsione coincide con il ridge completo.
Aggiungiamo separatamente la persistenza: ripetere sempre l'ultima misura.
Se nessun filtro dà un vantaggio, questa rimane la scelta.

Sono cinque candidate ingegneristiche, non soglie scientifiche universali,
accuratezze del sensore o limiti ecologici. Il valore 0,05 è già comparso
nella [diagnosi](WILLAMETTE_ERROR_MECHANISMS.md): questa ricerca è successiva
all'osservazione dei risultati e sarà dichiarata come sviluppo esplorativo.
Sceglieremo una sola soglia comune alle quattro finestre, senza adattarla
separatamente a ciascuna stagione.

## 3. Dividere gli esempi senza mescolare passato e futuro

Usiamo le quattro finestre di 28 giorni del 2025 già archiviate, alla stazione
USGS-14211720. Sono campioni di periodi stagionali, non quattro stagioni intere.
Per ciascuna finestra il confine è `inizio + 14 giorni`, in UTC.

- **Selezione:** il target a un'ora deve precedere strettamente il confine.
- **Controllo interno:** la prima delle dodici misure storiche deve essere
  al confine o successiva. La storia copre cinque ore e trenta minuti.
- **Intermezzo:** le origini che non soddisfano nessuna condizione sono escluse.

Il preflight verifica che l'ultimo target di selezione preceda la prima
misura storica del controllo e che le rispettive origini siano distanti
almeno sette ore. Riporta date, conteggi ed esclusioni per ogni finestra.
Richiede dati presenti in entrambi i gruppi; un conteggio positivo non dimostra
che il campione abbia potenza statistica sufficiente.
Questo evita la sovrapposizione delle prove al confine, ma non rende
indipendenti misure vicine di un fiume. Non interpoliamo i vuoti.

**Entrambe le metà sono già state osservate.** Il controllo è una diagnosi
temporale interna allo sviluppo, non un nuovo test cieco. La scelta comune
usa anche una finestra di novembre mentre altri controlli sono di febbraio:
non è una simulazione globalmente prospettica. Un test su dati mai usati
richiederà una fase successiva con calendario e codice fissati prima dei target.

## 4. La regola di selezione, prima dei calcoli reali

Calcoleremo la MAE di ogni candidata sugli stessi orari della selezione.
La MAE principale sarà la media delle quattro MAE, con uguale peso per finestra.
Una candidata sarà ammissibile soltanto se:

1. migliora la MAE principale della persistenza di oltre `1e-9 mg/L`;
2. non peggiora la MAE di nessuna finestra di oltre `1e-9 mg/L`;
3. produce zero previsioni invalide, comprese quelle non finite o negative.

Fra le ammissibili scegliamo la MAE principale minore. Per pareggi entro
`1e-9 mg/L`, preferiamo meno correzioni applicate; a ulteriore parità, la
soglia maggiore. Un pareggio con la persistenza favorisce la persistenza.
Se nessuna candidata è ammissibile, conserviamo la persistenza.
La tolleranza `1e-9` gestisce l'aritmetica: non esprime utilità ambientale,
incertezza statistica o un miglioramento pratico minimo dimostrato.

Sul controllo interno esamineremo soltanto la soglia selezionata, confrontata
con la persistenza e con i metodi precedenti sugli stessi orari. Richiederemo
lo stesso vantaggio medio, nessun peggioramento di finestra e zero previsioni
invalide. Se fallisce, registriamo il fallimento senza cercare un'altra soglia.
RMSE e grandi errori saranno descrittivi, senza sostituire la MAE principale.

## 5. Cosa viene preparato adesso

Il [protocollo](datasets/willamette-threshold-development/protocol.json) e lo
[script](../scripts/threshold_development.py) rendono controllabili regola,
separazione temporale e criteri. I test sintetici controllano i casi limite.
Il preflight può leggere l'archivio esistente per verificarne integrità e
divisione temporale; non calcola gli errori reali delle cinque candidate.
Il selettore viene provato su riepiloghi inventati nei test; il runner che
calcola le MAE reali non è ancora implementato o eseguito. Questa fase non
seleziona una soglia, non riaddestra, non acquisisce nuovi target e non
definisce il calendario del nuovo test a un'ora. Dalla radice della repository:

```sh
python scripts/threshold_development.py preflight
python -m unittest discover -s scripts -p 'test_threshold_development.py'
```

Il principio di rispettare l'ordine temporale è spiegato in
[Forecasting: Principles and Practice, §5.10](https://otexts.com/fpp3/toolbox.html#time-series-cross-validation).
La nostra griglia, divisione a metà e separazione di sette ore sono scelte
ingegneristiche dichiarate: non sono uno standard prescritto dal libro,
né questo controllo unico equivale alla cross-validation a origini mobili.

Virdacora conserva prove ambientali verificabili e comprensibili, utili alle
comunità. Un filtro numerico sperimentale non certifica la verità fisica dei
sensori e non attiva Oracle, governance, interventi o spese automatiche.
