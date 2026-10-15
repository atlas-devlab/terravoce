# Willamette a un'ora: dove la regressione aiuta e dove sbaglia

[English explanation](WILLAMETTE_ERROR_MECHANISMS_EN.md).

**La regressione corregge utilmente una parte dei cambiamenti, ma introduce
troppo errore quando il valore registrato rimane uguale.** In inverno,
primavera e autunno questo costo supera il beneficio. In estate prevale il
beneficio. È una scomposizione degli errori osservati, non una spiegazione
fisica di ciò che accade nel fiume.

Questo documento accompagna il [rapporto diagnostico](evidence/willamette-error-mechanisms/diagnostic.json)
e il [notebook](notebooks/willamette-error-mechanisms.ipynb). La base è il
[test già concluso](WILLAMETTE_STABILITY_RESULTS.md): stazione USGS-14211720,
ossigeno disciolto a un'ora, 5.213 coppie del 2025. Restiamo sullo stesso
problema, con gli stessi dati e lo stesso modello congelato. Non eseguiamo
un nuovo addestramento o una nuova verifica indipendente.

## 1. Prima separiamo ciò che sappiamo prima e dopo

All'origine della previsione conosciamo le misure precedenti e la correzione
proposta dalla regressione. Il target, un'ora dopo, serve alla valutazione.
Solo dopo averlo osservato possiamo suddividere i casi in:

- valore registrato invariato rispetto all'ultima misura;
- valore registrato in salita;
- valore registrato in discesa.

**Questi gruppi futuri sono una lente diagnostica, non un selettore operativo.**
Una regola non può decidere di mantenere l'ultima misura sapendo già che il
target sarà invariato. Anche le misure intermedie successive all'origine
restano future e non possono diventare ingressi di quella previsione.

Il confronto usa gli stessi orari per persistenza, ridge completo e ridge con
il fallback già provato: quando tutte le dodici misure passate di ossigeno
sono uguali, il fallback annulla la correzione; altrimenti usa il ridge.
Nelle tabelle seguenti «candidata» indica questa regola già provata, non una
nuova variante.

## 2. Il bilancio fra correzioni utili e inutili

La tabella confronta la candidata con l'ultima misura invariata. MAE significa
media degli errori assoluti; l'unità è mg/L e un valore più piccolo è migliore.

| Finestra | Target rispetto all'ultima misura | Coppie | MAE persistenza | MAE candidata |
| --- | --- | ---: | ---: | ---: |
| Inverno | Invariato | 1.058 | 0,000000 | 0,011724 |
| Inverno | In salita | 106 | 0,100000 | 0,081257 |
| Inverno | In discesa | 112 | 0,100000 | 0,092451 |
| Primavera | Invariato | 645 | 0,000000 | 0,026336 |
| Primavera | In salita | 332 | 0,163855 | 0,140814 |
| Primavera | In discesa | 343 | 0,162099 | 0,159467 |
| Estate | Invariato | 346 | 0,000000 | 0,045556 |
| Estate | In salita | 477 | 0,278197 | 0,241904 |
| Estate | In discesa | 475 | 0,271789 | 0,252931 |
| Autunno | Invariato | 747 | 0,000000 | 0,024384 |
| Autunno | In salita | 285 | 0,125263 | 0,099033 |
| Autunno | In discesa | 287 | 0,123693 | 0,123006 |

Nei quattro periodi la candidata ha una MAE inferiore alla persistenza sia
sui rialzi sia sui ribassi. Questo non significa che anticipi ogni rialzo o
ribasso: è una media dei rispettivi gruppi. Nei gruppi invariati qualsiasi
correzione diversa da zero introduce invece errore, perché il riferimento
è già esatto rispetto al valore pubblicato.

Per ricostruire la MAE stagionale, ciascuna MAE di gruppo va moltiplicata per
la sua quota di casi, poi le tre parti vanno sommate. Non si fa la media
semplice di tre gruppi di dimensione diversa. In inverno, per esempio, i
1.058 casi invariati sono l'82,92% dei 1.276 casi: il loro costo supera il
beneficio nei 218 casi che cambiano. In estate cambia una quota molto maggiore
dei target e il bilancio si inverte.

Le quattro MAE stagionali conservano uguale peso nel risultato principale.
Non sostituiamo questa media con una media aggregata più favorevole.
Il risultato precedente rimane invariato:

| Metodo | Media delle quattro MAE, mg/L |
| --- | ---: |
| Ultima misura invariata | 0,089023 |
| Ridge completo | 0,093555 |
| Ridge con fallback | 0,092470 |

«Invariato» descrive la precisione dei valori pubblicati. Non dimostra che
l'ossigeno fisico sia stato esattamente costante, né che un cambiamento più
piccolo fosse assente. Non abbiamo accertato qui l'accuratezza strumentale o
una risoluzione scientificamente utilizzabile come soglia del modello.

## 3. Perché MAE e RMSE danno segnali diversi

La MAE conta l'errore in proporzione alla sua grandezza. La MSE eleva gli
errori al quadrato; la RMSE è la radice della MSE e torna nell'unità mg/L.
Perciò la RMSE attribuisce un peso maggiore agli errori grandi.

In ciascuna delle quattro finestre la candidata ha una RMSE inferiore alla
persistenza, mentre la MAE è peggiore in tre finestre. È possibile quando
alcuni benefici sugli errori grandi compensano, nel punteggio quadratico,
molte piccole correzioni dannose. Il rapporto ne verifica il bilancio
aritmetico: non è una prova di capacità di allerta o di utilità ecologica.

| Gruppo del target | Contributo al vantaggio MAE, mg/L | Contributo al vantaggio MSE, (mg/L)² |
| --- | ---: | ---: |
| Invariato | −0,012136 | −0,000665 |
| In salita | +0,006589 | +0,007002 |
| In discesa | +0,002099 | +0,000332 |
| **Somma** | **−0,003447** | **+0,006670** |

Il vantaggio è errore della persistenza meno errore della candidata:
positivo significa un beneficio. Ogni contributo conserva il denominatore
completo della rispettiva stagione e poi l'uguale peso delle quattro
stagioni. I valori sono arrotondati; il JSON conserva la precisione completa.
Il beneficio sui rialzi domina il bilancio quadratico di questa diagnosi;
non equivale ad aver ridotto tutti i grandi errori o i rischi ecologici.

La MSE si può scomporre sommando i contributi dei gruppi pesati per il loro
numero di casi. Le RMSE dei gruppi non si sommano per ricostruire la RMSE
complessiva. Anche la media delle RMSE stagionali e la radice della media
delle MSE stagionali sono quantità diverse e vanno nominate correttamente.

La MAE resta il criterio principale già concordato. Non promuoviamo il test
scegliendo dopo i risultati la metrica più favorevole. Possiamo decidere
insieme un diverso obiettivo per un esperimento futuro, ma dovremo dichiararlo
prima e motivarlo rispetto all'uso delle comunità. Una soglia ecologica, un
costo di mancata allerta e una prestazione di allerta non sono ancora validati.

## 4. Due esempi agli estremi del confronto

Questi esempi sono selezionati retrospettivamente per il maggiore vantaggio
e il maggiore danno in errore assoluto della candidata rispetto alla
persistenza, fra tutte le 5.213 coppie. Sono esempi diagnostici, non eventi
scelti con una soglia ecologica. Tutti gli orari sono UTC.

| Origine → target | Ultima misura | Target registrato | Previsione candidata | Errore persistenza → candidata |
| --- | ---: | ---: | ---: | ---: |
| 2 giugno 2025, 06:00 → 07:00 | 7,0 | 9,5 | 7,768627 | 2,500000 → 1,731373 |
| 3 giugno 2025, 07:30 → 08:30 | 9,3 | 9,6 | 8,825073 | 0,300000 → 0,774927 |

Concentrazioni, previsioni ed errori assoluti sono in mg/L. Nel primo caso il
modello propone una salita e il target sale molto: riduce l'errore assoluto
di 0,768627 mg/L, ma la previsione rimane lontana dal target. Nel secondo
propone una discesa mentre il target registrato sale: aumenta l'errore
assoluto di 0,474927 mg/L.

Il rapporto ricostruisce anche la somma dei contributi numerici della
regressione. Nel caso dannoso, il cambiamento di ossigeno nelle due ore
precedenti contribuisce circa −0,346651 mg/L e quello nell'ultima mezz'ora
circa −0,108046 mg/L alla correzione finale. Nel caso utile gli stessi due
contributi sono circa +0,470238 e +0,303107 mg/L. Questo spiega il calcolo
della previsione; non dimostra che quelle variabili siano cause fisiche
dell'ossigeno futuro o che il modello abbia individuato un meccanismo del fiume.

Il target delle 07:00 del primo esempio non è un ingresso della previsione
calcolata con origine alle 06:00. Si tratta di una ricostruzione retrospettiva,
non di una previsione effettivamente emessa nel 2025. Lo stesso confine temporale vale per il secondo esempio.
Queste osservazioni non stabiliscono una causa fisica, la durata dell'episodio, l'impatto
sull'ecosistema o l'assenza di problemi di misura.

## 5. Perché «usiamo sempre metà correzione» non basta qui

Possiamo verificare questa idea senza riaddestrare il modello. Indichiamo con
`r` il cambiamento registrato nell'ora e con `d` la correzione già proposta
dal modello. Un peso costante `lambda` produce:

```text
previsione(lambda) = ultima misura + lambda × d
errore assoluto(lambda) = |r − lambda × d|
lambda = 0: persistenza; lambda = 1: modello completo considerato
```

La media di questi errori è una funzione convessa del peso. La sua pendenza
subito a destra di zero è `|d|` quando `r = 0`, altrimenti `−segno(r) × d`.
Conserviamo prima la media entro ciascuna stagione e poi l'uguale peso delle
quattro stagioni, come nel test originale.

| Correzione attenuata | Pendenza della MAE media a peso zero |
| --- | ---: |
| Ridge completo, senza fallback | +0,003327639 mg/L per unità di peso |
| Ridge con fallback | +0,002243274 mg/L per unità di peso |

Entrambe le pendenze sono positive. Per convessità, su queste quattro finestre
**nessun peso costante positivo fra zero e uno può battere la persistenza
sulla MAE media**. Il risultato riguarda questa famiglia di previsioni, gli
stessi dati, lo stesso riferimento e questa metrica. Non è un'impossibilità
generale di prevedere il fiume o di migliorare su dati futuri. Né esclude
regole condizionali basate su informazioni già disponibili all'origine.

Questo controllo non cerca il peso più favorevole, non riaddestra la
regressione e non presenta un nuovo test indipendente.

## 6. Una sola ipotesi da discutere per il prossimo test

Una candidata semplice è non intervenire quando la correzione del modello
è molto piccola:

```text
se |correzione completa| <= soglia: previsione = ultima misura
altrimenti: previsione = previsione del ridge completo
```

La grandezza della correzione è calcolabile all'origine senza leggere il
target. La regola non sa se il fiume rimarrà invariato. Una correzione piccola
può essere utile, e una grande può essere sbagliata: l'ipotesi può fallire.
Non abbiamo scelto una soglia, misurato il risultato di questa variante o
congelato un nuovo protocollo.

La diagnosi offre un indizio: dividendo retrospettivamente i casi secondo
la correzione del ridge completo, i piccoli interventi concentrano una
parte del costo. Il taglio descrittivo di 0,05 mg/L qui sotto è stato
introdotto dopo aver osservato i dati; non è una soglia scelta o validata
per una nuova previsione.

| Correzione assoluta del ridge completo | Coppie | Contributo al vantaggio MAE della candidata sulla persistenza, mg/L |
| --- | ---: | ---: |
| Al massimo 0,05 mg/L | 4.140 | −0,006605 |
| Oltre 0,05 mg/L | 1.073 | +0,003158 |

Questi sono contributi alla media stagionale, quindi si sommano: il saldo
è circa −0,003447 mg/L, coerente con il test fallito. Non sono le MAE
condizionali dei due gruppi. Nel gruppo oltre 0,05 mg/L il vantaggio
invernale rimane negativo: il taglio non risolve automaticamente il
requisito di non peggiorare nessuna stagione.

La soglia sarebbe un parametro statistico, non l'accuratezza del sensore o
un limite ecologico. Non la fissiamo automaticamente a 0,1 mg/L. Non
aggiungiamo contemporaneamente portata, meteo, un LLM o un nuovo orizzonte:
altrimenti non sapremmo quale modifica abbia aiutato.

Se concordiamo questa direzione, prima di nuovi dati di verifica servirà:

1. Usare le finestre ormai osservate soltanto come sviluppo, con una piccola
   ricerca della soglia e separazioni temporali interne dichiarate prima
   della scelta. Registrare anche i tentativi falliti.
2. Congelare una sola candidata, pesi esistenti, calendario su periodi
   successivi e mai consultati, controllo dei periodi già osservati, regole
   di qualità e codice del valutatore prima
   di acquisire i nuovi target. Un periodo insufficiente va segnalato,
   senza sostituirlo dopo aver visto il risultato.
3. Confrontare sui medesimi orari persistenza, ridge completo, fallback già
   provato e nuova candidata. Mantenere denominatori, vuoti, segno della
   portata, intervalli esplorativi a blocchi e uguale peso delle stagioni.
4. Concordare prima il successo: MAE principale, nessun peggioramento
   stagionale, incertezza del vantaggio e controlli secondari sui grandi
   errori. I requisiti precisi, compresa l'eventuale utilità ambientale
   pratica, devono essere dichiarati prima della verifica.
5. Separare la prova retrospettiva su archivi revisionati da una prova online.
   Per quest'ultima servono catture e previsioni conservate prima del target,
   con prova di quali ingressi fossero allora disponibili. L'archivio finale
   da solo non ricostruisce questa disponibilità storica.

**Decisione da discutere: vogliamo sviluppare questa sola regola sulle piccole
correzioni, mantenendo la MAE come obiettivo principale e il requisito di non
peggiorare nessuna delle quattro stagioni?**

## 7. Cosa significa per Virdacora

Virdacora deve rendere le prove ambientali verificabili e comprensibili alle
comunità. Pubblicare un test fallito, distinguere beneficio medio e rischio
di errori grandi e conservare le misure originali fanno parte di quel lavoro.
Questa diagnosi non attribuisce responsabilità per inquinamento e non prova
benefici sul campo. Impronte e provenienza rendono controllabili gli archivi;
non certificano da sole la verità fisica del sensore.

Non cambiamo l'Oracle operativo, il quorum, il voto delle comunità e dei
giovani o la tesoreria. Non autorizziamo automaticamente interventi o spese.
Restiamo sull'ossigeno a un'ora, prima di studiare 24 ore o tre mesi.

## 8. Riprodurre la diagnosi

Dalla radice del repository, con Python 3.10+ e Git, senza rete:

```sh
python scripts/diagnose_stability_errors.py verify
python -m unittest discover -s scripts -p 'test_*.py'
```

Il verificatore controlla gli hash fissati, riproduce la valutazione già
conclusa dagli archivi e ricostruisce la decomposizione. Rifiuta modifiche ai
conteggi, alle prove discrete o ai numeri oltre la tolleranza aritmetica di
1e-9. Questa tolleranza non è una soglia del sensore o di previsione.
