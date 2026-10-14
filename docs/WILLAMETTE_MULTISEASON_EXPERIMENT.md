# Prova Willamette a un'ora con quattro stagioni

Il protocollo è dichiarato prima del fit e prima di acquisire le quattro nuove
finestre di verifica. La priorità concordata è controllare se il nuovo
apprendimento riduce l'errore in modo credibile e regge nelle quattro stagioni.
Il 10% resta un obiettivo indicativo, non la soglia automatica di successo.

Si mantiene una sola ricetta: regressione ridge, otto ingressi già usati,
penalizzazione alpha=100. Si apprendono nuovi pesi su tutte le coppie complete
delle quattro finestre 2024. Nessuna variante viene scelta in base al test.
Con questa funzione di perdita, la forza relativa della penalizzazione dipende
anche dal numero di esempi: la prova valuta l'intero nuovo fit, senza attribuire
causalmente il risultato alla sola diversità stagionale.

La ricetta deriva dalla selezione precedente su dati del 2025. Questa è una
verifica retrospettiva su nuove finestre tenute separate dal fit corrente,
non la simulazione di un metodo già definito e disponibile nel 2024.

Le finestre di esame sono 15–29 gennaio, aprile, luglio e ottobre 2025, in UTC.
Sono periodi successivi al training, diversi da quelli già usati dal progetto.
La qualità e disponibilità vengono verificate dopo il congelamento. Una finestra insufficiente
o indisponibile rimane tale; non viene sostituita dopo aver visto i risultati.

Il confronto principale è con l'ultima misura invariata, sugli stessi orari.
Si riportano MAE, RMSE, bias e grandi errori per stagione e per giorno. La media
complessiva assegna lo stesso peso alle quattro stagioni. I periodi devono
avere almeno 500 coppie e 90% di copertura della griglia UTC per superare il
filtro pratico dei dati. Questo filtro non dimostra validità o potenza statistica.

L'incertezza esplorativa del vantaggio è stimata ricampionando blocchi di
48 ore dentro ciascuna stagione, con controlli anticipati a 24 e 72 ore, 5.000
repliche e seme fissato. Un vantaggio medio senza intervallo positivo oppure
con peggioramenti stagionali osservati non supera la regola dichiarata.
La precisione numerica 1e-9 non è una tolleranza ecologica. L'assenza di aumento
della MAE puntuale in una stagione non prova noninferiorità statistica.

Nessun risultato entra automaticamente nell'Oracle o nei finanziamenti.
Non si ricalibra né riusa la fascia estiva fallita. Questa prima prova misura
il valore previsto, non la qualità di un nuovo intervallo di previsione.
LLM, governance delle comunità e dei giovani e contratti restano quelli attuali.

Il protocollo completo è in
[`datasets/usgs-willamette-multiseason/protocol.json`](datasets/usgs-willamette-multiseason/protocol.json).
Il protocollo è stato pubblicato nel commit `eaebc10` prima del fit.
Il modello congelato è in
[`evidence/willamette-multiseason/frozen-model.json`](evidence/willamette-multiseason/frozen-model.json).
È stato appreso da 2.559 coppie complete del 2024. Il solver TypeScript già
presente è controllato con Cholesky Decimal a 50 cifre in Python: differenza
massima tra parametri 5,51e-14, sotto la tolleranza 1e-9. Questo è un controllo
aritmetico fra due implementazioni, non una validazione scientifica esterna.

Il comando di fit rifiuta orari del test, duplicati, ingressi non finiti,
ricette modificate e orizzonti diversi da un'ora. La valutazione usa i pesi
salvati e non chiama nessuno dei due solver. Il comando di acquisizione richiede
che protocollo e file dei pesi coincidano esattamente con quelli già nel commit
locale; ogni manifest lega i dati al loro hash e a quel commit.

Il fit è stato pubblicato nel commit `b895049` prima di acquisire qualsiasi
valore delle nuove finestre. I manifest riportano il suo SHA completo.
Comandi dalla radice del repo,
dopo aver installato le dipendenze Node con `pnpm install --frozen-lockfile`:

```text
python scripts/experiment_multiseason.py verify-fit
node scripts/capture-willamette-multiseason.mjs
python scripts/experiment_multiseason.py evaluate
python scripts/experiment_multiseason.py verify
```

`fit` è disponibile per una nuova copia senza il file congelato. I comandi
di fit, acquisizione e valutazione rifiutano di sovrascrivere gli artefatti.
Per il normale controllo offline si usano soltanto `verify-fit` e `verify`.

## Risultato: non supera il criterio concordato

L'esito salvato è `observed-seasonal-tradeoff`. Il modello migliora la media
di poco, ma peggiora in tre stagioni. Anche tutti gli intervalli esplorativi
del vantaggio includono zero. Il risultato rimane un esperimento da studiare;
non viene scelto un nuovo modello dopo aver visto il test.

| Finestra 2025 | Coppie | Copertura griglia | MAE persistenza mg/L | MAE nuovo mg/L | Vantaggio relativo |
| --- | ---: | ---: | ---: | ---: | ---: |
| Inverno, 15–29 gennaio | 637 | 96,52% | 0,012873 | 0,024278 | -88,60% |
| Primavera, 15–29 aprile | 647 | 98,03% | 0,027666 | 0,037157 | -34,30% |
| Estate, 15–29 luglio | 647 | 98,03% | 0,334776 | 0,308014 | +7,99% |
| Autunno, 15–29 ottobre | 660 | 100,00% | 0,068182 | 0,070332 | -3,15% |
| Media delle quattro MAE | 2.591 totali | — | 0,110874 | 0,109945 | +0,84% |

Un valore negativo nell'ultima colonna indica un peggioramento. Il quasi
raddoppio relativo invernale corrisponde a un aumento assoluto di circa
0,011406 mg/L: il riferimento di partenza ha già un errore molto basso.
La media è per stagione, non una media indistinta di tutti gli orari.
Il vantaggio assoluto complessivo è soltanto 0,000929 mg/L. Non è stata
definita né verificata una sua utilità ambientale pratica.

Tutte le finestre superano il filtro pratico dei dati. Su 2.640 origini attese
sono utilizzabili 2.591 coppie; i 49 orari esclusi restano nel denominatore:
14 origini senza ossigeno approvato e 35 con storia/target incompleti.
Non ci sono previsioni negative. I diagnostici di RMSE, bias, p95 e i risultati
giornalieri sono nel report, anche quando danno un quadro diverso dalla MAE.
Per esempio, in inverno la RMSE passa da 0,035879 a 0,035680 mg/L, ma la MAE
peggiora: il criterio principale dichiarato resta la MAE.

| Blocchi | Blocchi non vuoti per stagione | Intervallo esplorativo 95% del vantaggio MAE mg/L |
| --- | ---: | ---: |
| 48 ore, principale | 7 | [-0,003821; +0,005414] |
| 24 ore, sensibilità | 14 | [-0,002845; +0,004437] |
| 72 ore, sensibilità | 5 | [-0,005161; +0,006190] |

Qui il vantaggio è errore della persistenza meno errore del modello. Un
intervallo interamente positivo avrebbe sostenuto un vantaggio sotto le
assunzioni del metodo; questi intervalli consentono anche un peggioramento.
I blocchi cercano di conservare una parte della dipendenza temporale. Con
finestre brevi, 5–14 blocchi per stagione e blocchi scelti a priori, non
dimostrano copertura statistica universale. Non sono intervalli dei singoli
valori futuri dell'ossigeno. Il 10% indicativo non determina questo esito:
il test non passerebbe neppure eliminando completamente quel numero.

## Problemi osservati e loro significato

In inverno 555 target su 637 (87,13%) sono identici all'ultima misura
registrata. Su questi esempi la persistenza ha errore zero; le piccole
correzioni della regressione hanno MAE 0,015532 mg/L. In primavera sono
identici 482/647 target, in estate 149/647, in autunno 354/660. Questa
decomposizione descrive un meccanismo dell'errore osservato, senza dimostrare
una causa fisica del comportamento del fiume. Valori archiviati uguali non
dimostrano che la concentrazione fisica sia rimasta perfettamente costante.

Il controllo dei singoli intervalli di ingresso segnala 247 coppie invernali
e 266 estive fuori da almeno un intervallo del training; nessuna in primavera
o autunno. Tutte restano nel punteggio. Questo controllo non è una probabilità
di errore né un dominio scientifico di applicabilità. Quattro quindicine
offrono stagioni diverse, ma non rappresentano tutte le condizioni del bacino.

Due target estivi sono sotto i 5 mg/L illustrativi:

| Origine UTC | Target UTC | Ultima misura | Valore registrato | Nuova previsione |
| --- | --- | ---: | ---: | ---: |
| 18 luglio 2025, 05:00 | 06:00 | 8,5 | 3,5 | 8,535660 |
| 20 luglio 2025, 06:30 | 07:30 | 8,3 | 3,8 | 8,293159 |

I record target originali sono rispettivamente
`c80b70af-704b-4edc-8636-d6cf49410efc` e
`fba3b442-adce-4f3e-86ba-090b56f550f9`, con stato Approved e senza qualifier
nella cattura. Il modello non anticipa questi due valori. Non vengono rimossi
per rendere migliore il risultato. La presenza nell'archivio non dimostra
la causa, la durata, l'impatto ecologico né l'assenza di problemi di misura.
Due target e una soglia illustrativa non sono una validazione delle allerte.
Occorre un'analisi dedicata delle serie originali prima di attribuire loro
un significato ambientale o introdurre una regola di allerta.

Il modello estivo precedente è riportato soltanto come confronto diagnostico.
La sua media MAE in queste finestre è 0,804597 mg/L, mentre la regressione
lineare già esistente ottiene 0,137760 mg/L. Il vecchio ridge è stato appreso
e scelto su agosto 2025: usa quindi osservazioni successive alle finestre
invernale, primaverile ed estiva di questo test. Non è un riferimento
storicamente disponibile per quelle tre finestre. La persistenza è il
confronto principale; il nuovo training usa soltanto il 2024.

## Modifiche, verifiche e confini

- Aggiunti protocollo, pesi congelati, catture originali, manifest e report
  completo con tutte le coppie. Gli esperimenti precedenti sono conservati.
- Aggiunto un comando TypeScript ristretto al fit 2024 e un orchestratore
  Python che controlla provenienza, allineamento, calcolo e bootstrap.
- La cattura rifiuta file del modello non ancora in Git; fit, cattura e
  valutazione rifiutano sovrascritture. La verifica offline riproduce i numeri
  entro 1e-9, con hash e identificativi confrontati esattamente.
- I test coprono dati futuri, orizzonte, griglia, duplicati, ricetta alterata,
  numeri non finiti, pesi incoerenti, legame cattura/modello, pesi uguali fra
  stagioni nel bootstrap, casi noti e assenza di fit durante la valutazione.
- La CI riproduce il fit congelato e la verifica usando gli archivi locali,
  senza chiamare USGS o un LLM. Il notebook eseguito rende leggibili i controlli.

In locale sono passati build, controlli TypeScript, 86 test TypeScript/Solidity,
18 test degli audit Python e 7 test del bridge Python: 111 test in totale.
La riproduzione offline del fit e del report coincide con gli artefatti entro
la tolleranza dichiarata. La prova Docker con una replica spenta non è stata
ripetuta in questo incremento numerico; il suo esito precedente rimane separato.

Le modifiche implementano un esperimento numerico isolato e reversibile.
La regressione non è un LLM e non apprende da notizie, bandi o inquinanti.
Non sono stati introdotti nuovi collegamenti dell'advisor, modifiche a
TerraLex, quorum, voto, budget, escrow o autorizzazioni di spesa. Il percorso
originale di Virdacora conserva il controllo delle comunità e dei giovani
e la richiesta di risultati verificabili prima dei finanziamenti.

Non passiamo automaticamente alle 24 ore o ai tre mesi. Il passo da discutere
è studiare la difficoltà sui periodi stabili e sui bruschi cali, e poi
definire un nuovo protocollo con dati di verifica ancora separati. Queste
finestre ormai esaminate possono servire alla diagnosi; non potranno essere
presentate come test finale mai osservato di una nuova variante.

Artefatti:
[sintesi numerica](evidence/willamette-multiseason/summary.json),
[report completo compresso](evidence/willamette-multiseason/evaluation.json.gz),
[notebook eseguito](notebooks/willamette-multiseason.ipynb).

Riferimenti metodologici:
[ridge](https://scikit-learn.org/stable/modules/linear_model.html#ridge-regression-and-classification),
[valutazione temporale e riferimenti](https://otexts.com/fpp3/toolbox.html),
[bootstrap a blocchi per dipendenza temporale](https://otexts.com/fpp3/advanced.html#bootstrapping-time-series).
