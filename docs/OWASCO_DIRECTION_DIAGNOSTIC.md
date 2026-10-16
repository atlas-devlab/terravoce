# Owasco: scegliere la correzione dalla direzione delle ultime due ore / Choosing a correction from the previous two hours

## Italiano

**La regola delle due ore peggiora la MAE in entrambi i mesi già studiati. La candidata si ferma a questo controllo di sviluppo: nessuna acquisizione di settembre e nessun cambiamento al modello.** Questo risultato riguarda una regola precisa applicata agli archivi di luglio e agosto 2020; non dimostra che sia impossibile costruire un altro selettore utile.

Virdacora mantiene il suo obiettivo: offrire alle comunità prove ambientali verificabili e comprensibili. Documentare un tentativo che non migliora il riferimento fa parte di questo obiettivo. Questo lavoro riguarda ricerca numerica retrospettiva sull'ossigeno disciolto a una posizione/profondità del lago Owasco, non una decisione ambientale operativa. L'LLM resta un consulente esterno al calcolo deterministico e al consenso operativo.

### 1. Che cosa abbiamo fissato prima del calcolo

Il [protocollo adottato](datasets/owasco-direction-diagnostic/protocol.json), lo [script](../scripts/owasco_direction_diagnostic.py) e i [test sintetici](../scripts/test_owasco_direction_diagnostic.py) sono stati congelati nel commit [`b8b350c6c92ecc15bbb6ccdffc449755f3ff92af`](https://github.com/atlas-devlab/virdacora/commit/b8b350c6c92ecc15bbb6ccdffc449755f3ff92af), prima del primo calcolo reale della candidata. Il [rapporto completo](evidence/owasco-direction-diagnostic/diagnostic.json) è stato creato il 16 ottobre 2026 alle 15:47:11 UTC, dopo l'adozione del protocollo alle 15:40:40 UTC.

Usiamo soltanto previsioni e storie già archiviate negli esiti originali di [luglio](evidence/owasco-lake-transfer/evaluation.json) e [agosto](evidence/owasco-temporal-validation/evaluation.json). I coefficienti del [modello congelato](evidence/willamette-multiseason/frozen-model.json) restano identici e la regressione non viene ricalcolata. Non abbiamo addestrato, cercato soglie, acquisito osservazioni o prodotto nuovi intervalli bootstrap.

La previsione resta **a un'ora**. Le **due ore** indicano soltanto il confronto con una misura passata per scegliere quale previsione usare:

```text
P = O(t)                         ultima misura mantenuta come previsione
R = regressione già salvata      previsione a t + 1 ora
d = O(t) - O(t - 2 ore)          cambiamento passato fra due estremi
c = R - P                       correzione proposta dalla regressione

S = R se d > 0 e c > 0, oppure se d < 0 e c < 0
S = P in tutti gli altri casi, compresi d == 0 oppure c == 0
```

Sono confronti esatti sul segno, senza epsilon, arrotondamenti, clipping o nuova soglia d'ampiezza. La scelta non riceve la misura futura. La misura a `t + 1 ora` serve successivamente a calcolare l'errore. `d == 0` significa che i due estremi pubblicati sono uguali; non significa che tutta la storia sia piatta o che il lago sia fisicamente immobile.

**S sostituisce il vecchio filtro:** non gli aggiunge un'altra condizione. Il vecchio filtro `oldF`, che usa R soltanto quando `abs(R-P) > 0.100 mg/L`, resta un confronto distinto e immutato.

### 2. Risultato principale: errore su tutti i casi

La MAE è la media degli errori assoluti, in mg/L: più bassa è, meglio è. Ogni metodo usa esattamente gli stessi **1.275 casi di luglio** e **1.306 casi di agosto**, compresi quelli in cui S mantiene P. Non usiamo la sola MAE dei casi corretti come risultato principale.

| Metodo | Luglio: MAE mg/L | Agosto: MAE mg/L |
|---|---:|---:|
| P: ultima misura | 0.038666666667 | 0.055513016845 |
| R: regressione senza filtro | 0.048165907157 | 0.066183549661 |
| oldF: vecchio filtro 0.100 mg/L | 0.038692359932 | 0.055453386176 |
| S: selettore delle due ore | **0.039046174884** | **0.055609990012** |
| Guadagno P − S, positivo se migliora | **−0.000379508217** | **−0.000096973166** |

Tutte le previsioni della candidata sono valide; non abbiamo rimosso righe. Il criterio fissato richiedeva previsioni valide e `MAE_P − MAE_S > 1e-9 mg/L` **in entrambi i mesi**. Entrambi i mesi falliscono il criterio perché il guadagno è negativo. È una regola prudente di sviluppo, non una soglia ecologica o un test di significatività.

I risultati originali di P, R e oldF sono stati ricostruiti entro la tolleranza di integrità `1e-9 mg/L` e conservati. Il piccolo vantaggio numerico del vecchio filtro ad agosto mantiene il precedente esito inconclusivo; questa diagnosi non lo trasforma in successo.

### 3. Quando scegliere R aiuta e quando sbaglia

| Esito di S rispetto a P | Luglio | Agosto |
|---|---:|---:|
| S sceglie R | 116 | 190 |
| Tra questi: errore minore | 21 | 75 |
| Tra questi: errore maggiore | 95 | 115 |
| Tra questi: stesso errore | 0 | 0 |
| S mantiene P, quindi pareggio con P | 1.159 | 1.116 |

La somma dei miglioramenti attivi è **0.144474** a luglio e **0.706893** ad agosto; la somma delle rispettive perdite è **0.628347** e **0.833540**. Sono somme di differenze di errore fra casi, non concentrazioni accumulate nel lago. Le perdite superano i benefici in entrambi i mesi. Il numero di vittorie da solo non determina la MAE: conta anche la loro ampiezza.

Un ulteriore conteggio **a posteriori**, leggendo i target delle sole righe già corrette, chiarisce gli errori osservati:

| Esito pubblicato dopo la scelta di R | Luglio | Agosto |
|---|---:|---:|
| Target uguale a P: correzione dannosa | 86 | 109 |
| Target si sposta nel verso opposto alla correzione: dannosa | 9 | 6 |
| Target si sposta nel verso della correzione, senza essere oltrepassato: utile | 21 | 75 |

In questi casi selezionati non vi sono pareggi o superamenti del target da parte della correzione. La [ricevuta del conteggio ex-post](evidence/owasco-direction-diagnostic/expost-error-mechanism.json) conserva definizioni e provenienza. La tabella usa il futuro già osservato per **spiegare**, non per decidere: non è una regola di previsione, una nuova condizione di successo o una dimostrazione causale. Target pubblicato invariato non significa ossigeno fisicamente costante.

Nei casi in cui S mantiene P, il confronto contro R mostra sia una protezione sia opportunità perse:

| Nei casi in cui S mantiene P | Luglio | Agosto |
|---|---:|---:|
| Evita un errore maggiore che R avrebbe introdotto | 882 | 854 |
| Rinuncia a un miglioramento che R avrebbe dato | 277 | 262 |
| Somma delle perdite di R evitate | 19.293067 | 22.219007 |
| Somma dei benefici di R persi | 7.665408 | 8.409938 |

Questa protezione è **rispetto alla regressione R**. Mantenere P non batte P: dà esattamente lo stesso errore. S migliora molto rispetto a usare sempre R, ma non migliora il riferimento principale P.

### 4. Che cosa cambia rispetto al vecchio filtro

| Scelta sulla stessa riga | Luglio | Agosto |
|---|---:|---:|
| S e oldF scelgono entrambi R | 0 | 0 |
| Solo S sceglie R: nuove piccole correzioni | 116 | 190 |
| Solo oldF sceglie R: correzioni ora rimosse | 4 | 16 |
| Entrambi mantengono P | 1.155 | 1.100 |

A luglio, S riattiva **115 correzioni sotto 0.025 mg/L** e una nella fascia `[0.025, 0.050)`. Il loro saldo totale contro P è **−0.483873**. Rimuove anche le quattro vecchie correzioni, che avevano saldo **−0.032759**: questa rimozione aiuta, ma non compensa le nuove perdite.

Ad agosto, S riattiva **185 correzioni sotto 0.025 mg/L** e cinque nella fascia `[0.025, 0.050)`. Il loro saldo totale è **−0.126647**. Rimuove inoltre le sedici vecchie correzioni, il cui saldo era **+0.077878**: qui rinuncia anche al piccolo beneficio numerico del vecchio filtro.

Questa è una descrizione dei gruppi fissati prima del calcolo. Non scegliamo adesso una nuova soglia o una fascia vincente per salvare la candidata. Il rapporto conserva tutte le fasce, compresi i gruppi vuoti con medie `null`.

### 5. Quattro episodi reali per luglio

Sono i **primi casi cronologici** delle quattro categorie stabilite nel codice, identificati dopo il calcolo degli errori. Gli indici sono a base zero nel rapporto. Sono esempi illustrativi scelti a posteriori, non casi rappresentativi delle frequenze, eventi indipendenti o spiegazioni causali. I valori della tabella sono arrotondati soltanto per la lettura; la scelta è stata eseguita sui valori esatti archiviati.

| Caso, indice | Origine → verifica, UTC | O due ore prima | P adesso | R | S scelto | Misura futura |
|---|---|---:|---:|---:|---:|---:|
| Corregge e aiuta, 54 | 02/07 08:30 → 09:30 | 10.0 | 9.9 | 9.899303 | 9.899303 | 9.8 |
| Corregge e sbaglia, 0 | 01/07 05:30 → 06:30 | 10.0 | 9.9 | 9.898364 | 9.898364 | 9.9 |
| Mantiene ed evita una perdita di R, 1 | 01/07 06:00 → 07:00 | 10.0 | 9.9 | 9.900416 | 9.9 | 9.9 |
| Mantiene e perde un beneficio di R, 3 | 01/07 07:00 → 08:00 | 9.9 | 9.9 | 9.882968 | 9.9 | 9.8 |

- **Caso 54:** gli estremi passati scendono e R propone ancora una discesa. La misura futura scende: l'errore passa da 0.100000 a 0.099303 mg/L, un piccolo miglioramento di 0.000697 mg/L.
- **Caso 0:** gli stessi segni autorizzano una correzione, ma la misura successiva pubblicata resta 9.9. P era esatto; S introduce 0.001636 mg/L di errore. La direzione passata non garantisce che il cambiamento continui nell'ora successiva.
- **Caso 1:** la variazione passata è negativa, mentre R propone una salita. S conserva 9.9, che coincide con la misura futura, evitando 0.000416 mg/L di errore rispetto a R.
- **Caso 3:** gli estremi a due ore sono uguali e S resta a 9.9. La misura successiva è 9.8: R avrebbe ridotto l'errore da 0.100000 a 0.082968 mg/L. La scelta prudente perde un beneficio di 0.017032 mg/L.

### 6. Quattro episodi reali per agosto

Si applica la stessa scelta cronologica e illustrativa, senza una nuova selezione discrezionale degli esempi.

| Caso, indice | Origine → verifica, UTC | O due ore prima | P adesso | R | S scelto | Misura futura |
|---|---|---:|---:|---:|---:|---:|
| Corregge e aiuta, 46 | 02/08 04:30 → 05:30 | 9.5 | 9.4 | 9.392145 | 9.392145 | 9.3 |
| Corregge e sbaglia, 0 | 01/08 05:30 → 06:30 | 9.3 | 9.2 | 9.191087 | 9.191087 | 9.2 |
| Mantiene ed evita una perdita di R, 1 | 01/08 06:00 → 07:00 | 9.2 | 9.2 | 9.168511 | 9.2 | 9.2 |
| Mantiene e perde un beneficio di R, 6 | 01/08 08:30 → 09:30 | 9.2 | 9.4 | 9.335266 | 9.4 | 9.3 |

- **Caso 46:** passato e correzione indicano discesa e la misura futura è inferiore. S riduce l'errore da 0.100000 a 0.092145 mg/L: beneficio di 0.007855 mg/L.
- **Caso 0:** la discesa passata autorizza una nuova discesa prevista, ma la lettura futura resta 9.2. L'errore passa da zero a 0.008913 mg/L.
- **Caso 1:** il confronto a due ore vale zero, quindi S mantiene P. La lettura futura coincide con P e S evita l'errore di R, pari a 0.031489 mg/L. La storia completa di 5,5 ore non era piatta: i due estremi uguali non bastano a definirla tale.
- **Caso 6:** gli estremi passati salgono da 9.2 a 9.4, ma R propone una discesa. S rifiuta la correzione; la lettura futura di 9.3 avrebbe invece favorito R. P e S sbagliano di 0.100000 mg/L, R di 0.035266: beneficio perso di 0.064734 mg/L.

Le dodici misure passate a intervalli di trenta minuti, tutte le otto feature, i valori esatti delle previsioni, i target e gli errori per questi esempi e per ogni altra riga sono nel [rapporto verificabile](evidence/owasco-direction-diagnostic/diagnostic.json).

### 7. Che cosa possiamo concludere

La concordanza dei due segni individua qualche correzione utile, ma in questi due mesi autorizza anche piccole correzioni il cui costo totale supera il beneficio. Blocca inoltre alcune correzioni che avrebbero anticipato un'inversione del cambiamento osservato. Sono confronti numerici con gli esiti archiviati, non prove di un meccanismo fisico.

I decimali delle previsioni esprimono precisione numerica del calcolo, non accuratezza fisica del sensore. Le misure qui pubblicate con un decimale non stabiliscono, da sole, risoluzione o accuratezza strumentale. Un guadagno inferiore a 0.1 mg/L può essere calcolato rispetto a quelle letture; non equivale automaticamente a un miglioramento ambientale fisicamente accertato. Non deduciamo rumore, deriva del sensore o stabilità del lago dalle sole uguaglianze dei valori.

Le righe e le finestre si sovrappongono nel tempo: i conteggi non sono osservazioni indipendenti. Gli archivi finalizzati non dimostrano che gli stessi dati fossero disponibili all'origine in tempo reale. I controlli verificano la storia dell'ossigeno e l'ordine delle otto feature; le righe salvate non contengono una storia della temperatura che consenta di ricostruire indipendentemente le ultime due feature. Il relativo archivio e i risultati restano vincolati dai loro hash.

**La decisione applicata è fermare questa candidata.** Non passiamo a settembre, non modifichiamo R, non sostituiamo la finestra e non proviamo automaticamente altre soglie o formule. Il risultato lascia aperta una discussione successiva sul modello o sulle misure, mantenendo distinti sviluppo e verifica.

### 8. Contributo di Gemini e controlli distinti

Prima dello score, Gemini nella modalità visibile **Argon / Alta** ha proposto di verificare la partizione fra interventi aggiunti e rimossi e la ricomposizione dei guadagni sul denominatore completo. Questi controlli sono stati verificati numericamente. Abbiamo invece ristretto una sua affermazione: una scomposizione algebrica non dimostra una causa fisica, ma neppure basta a falsificarla. Il confronto sui segni resta implementato senza moltiplicare `d*c`, evitando differenze da overflow o underflow.

Il turno successivo, con i risultati, ha restituito una non-risposta e un limite di quota Argon fino alle 21:03 locali. Dopo l'autorizzazione dell'utente, **Flash-Lite** ha ricevuto un compito didattico più breve. Ha spiegato correttamente che la direzione passata non garantisce la prosecuzione nell'ora seguente, precisando che un solo esempio non dimostra l'inefficacia generale della regola. Abbiamo corretto il linguaggio fisico: i dati provano uguaglianza della lettura pubblicata e variazione fra due estremi, non stabilità dell'acqua o discesa continua del lago. Un precedente tentativo Flash-Lite sul riepilogo più lungo aveva restituito soltanto una non-risposta.

Questa collaborazione aggiunge critica metodologica e una spiegazione, non una seconda misura ambientale o un audit scientifico indipendente. I replay deterministici e il controllo aritmetico separato della stessa famiglia Codex sostengono i numeri. L'etichetta Flash-Lite della chat non identifica da sola la versione API. La [documentazione ufficiale Google](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite) descrive compiti leggeri ed estrazione di dati per un modello API Flash-Lite: è un'indicazione per assegnare compiti circoscritti, non prova di superiorità o equivalenza con questa chat. Non è stato acquistato un abbonamento o integrato un LLM operativo.

In un secondo compito breve, Flash-Lite ha distinto utilmente il miglioramento rispetto a R dal confronto principale contro P, respinto la generalizzazione a tutti i laghi e separato i decimali dall'accuratezza. Le formulazioni finali restano quelle verificate sopra: P può comunque sbagliare una previsione, e molti decimali non certificano né escludono un cambiamento fisico. La [ricevuta dei contributi](evidence/owasco-direction-diagnostic/gemini-contribution.json) distingue tre risposte sostanziali e due non-risposte. Il tempo di sessione include attese e lavoro Codex; non indica ragionamento continuo di Gemini.

## English

**The two-hour direction rule worsens full-cohort MAE in both previously inspected months. This candidate stops at the development screen: no September acquisition and no model change.** This result concerns one precisely specified rule on the July/August 2020 archives. It does not establish that every possible selector must fail.

Virdacora's aim remains understandable, verifiable environmental evidence serving communities. Recording an unsuccessful attempt supports that aim. This is retrospective dissolved-oxygen research at one Owasco Lake location/depth, not an operational environmental decision. An LLM provides advice outside deterministic numerical calculation and operational consensus.

### Fixed rule and evidence

The [adopted protocol](datasets/owasco-direction-diagnostic/protocol.json), [implementation](../scripts/owasco_direction_diagnostic.py) and [synthetic tests](../scripts/test_owasco_direction_diagnostic.py) were frozen at commit [`b8b350c6c92ecc15bbb6ccdffc449755f3ff92af`](https://github.com/atlas-devlab/virdacora/commit/b8b350c6c92ecc15bbb6ccdffc449755f3ff92af) before the first actual candidate score. The [complete diagnostic](evidence/owasco-direction-diagnostic/diagnostic.json) was created on 16 October 2026 at 15:47:11 UTC, after protocol adoption at 15:40:40 UTC.

Inputs are the saved [July](evidence/owasco-lake-transfer/evaluation.json) and [August](evidence/owasco-temporal-validation/evaluation.json) forecasts and histories, bound by SHA-256. The [frozen model](evidence/willamette-multiseason/frozen-model.json) is unchanged; R is read, never recalculated. There is no fitting, new observation acquisition, threshold search or new bootstrap.

The forecast horizon remains **one hour**. Two hours refers only to a past endpoint contrast:

```text
P = O(t)                         latest measurement / persistence baseline
R = saved frozen ridge          prediction for t + 1 hour
d = O(t) - O(t - 2 hours)        past endpoint change
c = R - P                       proposed correction

S = R iff (d > 0 and c > 0) or (d < 0 and c < 0)
S = P otherwise, including d == 0 or c == 0
```

Exact sign comparisons use no epsilon, rounding, clipping or amplitude threshold. The future target is used only after routing to compute errors. Zero endpoint change is not proof of a flat history or physical stability. S **replaces**, rather than supplements, the old `abs(R-P) > 0.100 mg/L` gate; oldF remains an unchanged comparator.

### Full-cohort results

Lower MAE, in mg/L, is better. Every method uses all 1,275 identical accepted July pairs or all 1,306 August pairs, including rows on which S retains P.

| Method | July MAE mg/L | August MAE mg/L |
|---|---:|---:|
| P: persistence | 0.038666666667 | 0.055513016845 |
| R: unfiltered ridge | 0.048165907157 | 0.066183549661 |
| oldF: previous 0.100 mg/L filter | 0.038692359932 | 0.055453386176 |
| S: two-hour selector | **0.039046174884** | **0.055609990012** |
| Gain P − S; positive helps | **−0.000379508217** | **−0.000096973166** |

All candidate predictions are valid and no rows were dropped. The prespecified continuation screen required valid predictions and `MAE_P − MAE_S > 1e-9 mg/L` in **both** months. Both fail. This is a conservative development decision, not an ecological standard or significance test. Original P/R/oldF MAEs recompose within the `1e-9 mg/L` integrity tolerance; their historical outcomes are unchanged. The earlier August oldF result remains inconclusive despite its small numerical advantage.

| S compared with P | July | August |
|---|---:|---:|
| Selects R | 116 | 190 |
| Active improvements | 21 | 75 |
| Active worsenings | 95 | 115 |
| Active equal errors | 0 | 0 |
| Retains P: ties with P | 1,159 | 1,116 |
| Retained rows avoiding an R loss | 882 | 854 |
| Retained rows missing an R gain | 277 | 262 |

Active positive gains sum to 0.144474 / 0.706893, while active loss magnitudes sum to 0.628347 / 0.833540 for July/August. These are sums of paired error differences, not accumulated lake concentrations. Within retained rows, R loss magnitudes avoided sum to 19.293067 / 22.219007, while R benefits forgone sum to 7.665408 / 8.409938. These protections are **relative to R**: retaining P cannot improve on P itself. S improves substantially over always using R, but fails to beat the primary persistence baseline.

An additional **post-target descriptive** partition of already-selected R rows helps explain the recorded outcomes:

| Published outcome after selecting R | July | August |
|---|---:|---:|
| Target equals P: correction worsens error | 86 | 109 |
| Target displacement opposes correction: worsens error | 9 | 6 |
| Target displacement agrees with correction, without overshoot: improves error | 21 | 75 |

There are no ties or target overshoots among these selected cases. The [ex-post receipt](evidence/owasco-direction-diagnostic/expost-error-mechanism.json) records definitions and provenance. This partition uses observed future targets to explain outcomes; it is not an available forecast trigger, a new success condition or a causal explanation. An unchanged published target is not proof of physically constant oxygen.

### Accounting against oldF

| Routing on identical rows | July | August |
|---|---:|---:|
| Both S and oldF select R | 0 | 0 |
| S alone selects R: added corrections | 116 | 190 |
| oldF alone selects R: removed corrections | 4 | 16 |
| Both retain P | 1,155 | 1,100 |

July adds 115 corrections below 0.025 mg/L and one in `[0.025, 0.050)`, with total gain −0.483873 against P. It removes four old corrections with total gain −0.032759; that removal helps but does not offset the added losses. August adds 185 corrections below 0.025 and five in `[0.025, 0.050)`, with total gain −0.126647. It also removes sixteen old corrections whose total gain was +0.077878, giving up their small numerical benefit. These fixed-bin descriptions do not select a replacement threshold or a winning subgroup.

### Four July examples and four August examples

Examples are the **first chronological match** for each predefined category, selected retrospectively after scoring, with zero-based source row indices. They illustrate possibilities, not representative frequencies, independent events or causal mechanisms. Numbers below are rounded for presentation only; routing used exact saved values. All timestamps are UTC in 2020, and all oxygen numbers are mg/L.

| Month/category/index | Origin → target | O(t−2h) | P | R | S | Actual |
|---|---|---:|---:|---:|---:|---:|
| July: select/help, 54 | 02 Jul 08:30 → 09:30 | 10.0 | 9.9 | 9.899303 | 9.899303 | 9.8 |
| July: select/harm, 0 | 01 Jul 05:30 → 06:30 | 10.0 | 9.9 | 9.898364 | 9.898364 | 9.9 |
| July: retain/avoid loss, 1 | 01 Jul 06:00 → 07:00 | 10.0 | 9.9 | 9.900416 | 9.9 | 9.9 |
| July: retain/miss gain, 3 | 01 Jul 07:00 → 08:00 | 9.9 | 9.9 | 9.882968 | 9.9 | 9.8 |
| August: select/help, 46 | 02 Aug 04:30 → 05:30 | 9.5 | 9.4 | 9.392145 | 9.392145 | 9.3 |
| August: select/harm, 0 | 01 Aug 05:30 → 06:30 | 9.3 | 9.2 | 9.191087 | 9.191087 | 9.2 |
| August: retain/avoid loss, 1 | 01 Aug 06:00 → 07:00 | 9.2 | 9.2 | 9.168511 | 9.2 | 9.2 |
| August: retain/miss gain, 6 | 01 Aug 08:30 → 09:30 | 9.2 | 9.4 | 9.335266 | 9.4 | 9.3 |

- **July 54:** both contrasts are negative, and the target is lower. S error is 0.099303 versus P's 0.100000; gain 0.000697.
- **July 0:** both signs also agree, but the published future reading remains 9.9. S introduces 0.001636 error where P has none. Past direction does not guarantee continuation.
- **July 1:** the negative past contrast disagrees with a positive proposed correction. Retaining P avoids R's 0.000416 error.
- **July 3:** the two-hour endpoints are equal, so S retains P. The target falls; R would reduce error from 0.100000 to 0.082968. Forgone gain: 0.017032.
- **August 46:** same-direction correction reduces error from 0.100000 to 0.092145; gain 0.007855.
- **August 0:** same-direction correction worsens zero baseline error to 0.008913 because the future published reading is unchanged.
- **August 1:** zero two-hour endpoint change makes S retain P, avoiding R's 0.031489 error. The complete 5.5-hour history is not flat; equal endpoints do not establish a flat path.
- **August 6:** the past endpoint contrast is positive but R predicts a decrease. S rejects R; the actual decrease would favor R. P/S error is 0.100000 versus R's 0.035266, a forgone 0.064734 benefit.

The [machine-readable report](evidence/owasco-direction-diagnostic/diagnostic.json) contains every row's twelve half-hour oxygen samples, eight features, exact predictions, target, routing, errors and gains, including all examples above.

### Interpretation and limits

Directional agreement finds some useful corrections, but it also enables small corrections whose aggregate cost exceeds their benefit in both opened months. It can reject corrections that would anticipate a reversal of the observed endpoint change. These are numerical comparisons with archived outcomes, not established physical explanations.

Prediction decimals represent computational precision, not sensor accuracy. One-decimal published measurements alone do not establish instrumental resolution or accuracy. A sub-0.1 mg/L average gain is calculable against these readings; it does not automatically establish a physically verified environmental benefit. Equal published readings do not by themselves prove sensor noise, drift or lake stability.

Rows/history windows overlap, so counts are not independent observations. Finalized historical archives do not prove as-of-origin availability or live forecast performance. Integrity checks reconstruct oxygen history features and verify all eight feature names/order; saved rows lack temperature histories for an independent reconstruction of the last two features. Input hashes bind their exact archived contents.

**This candidate is stopped at Stage A.** No September data, replacement window, model change or automatic alternative rule/threshold follows from this result. Any later change requires a new, explicit development and verification decision. Original Oracle, blockchain, quorum, governance and funding behavior are unchanged.

### Gemini's bounded contribution

Before scoring, Gemini, visibly set to **Argon / High**, proposed checking added/removed interventions and full-denominator gain recomposition; these identities were numerically verified. We narrowed one overclaim: algebraic decomposition neither establishes a physical cause nor suffices to falsify one. Implementation compares signs directly rather than multiplying `d*c`, avoiding overflow/underflow differences.

The results-review turn returned a non-answer and an Argon quota limit until 21:03 local time. With user authorization, **Flash-Lite** received a shorter explanatory task. It correctly explained that past direction does not guarantee continuation during the next hour and that one example does not establish general ineffectiveness. We narrowed its physical wording: equal published readings and a decrease between past endpoints do not prove physically stable water or continuous lake decline. An earlier, longer Flash-Lite results prompt also received only a non-answer.

This is methodological criticism and explanation, not independent environmental measurement or external scientific validation. Deterministic replay and a separate Codex-family arithmetic implementation support the numerical results. The chat's Flash-Lite label does not identify an API version. [Google's official API documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite) describes lightweight tasks and data extraction for an API Flash-Lite model; this informs bounded task assignment without establishing general superiority or equivalence with this chat. No subscription purchase or operational LLM integration occurred.

In a second short task, Flash-Lite usefully separated improvement over R from the primary P comparison, rejected generalization to every lake, and distinguished decimals from accuracy. The checked wording above remains authoritative: P can still make forecast errors, and extra decimals neither certify nor rule out a physical change. The [contribution receipt](evidence/owasco-direction-diagnostic/gemini-contribution.json) distinguishes three substantive replies from two non-answers. Session duration includes waits and Codex work; it is not continuous Gemini reasoning.

## Reproduction / Riproduzione

Supporting receipts / Ricevute di supporto:

- [Freeze before scoring / Congelamento prima del calcolo](evidence/owasco-direction-diagnostic/freeze-before-score.json).
- [Separate arithmetic review / Controllo aritmetico separato](evidence/owasco-direction-diagnostic/arithmetic-review.json): another Codex-family perspective, not independent environmental measurements or external certification / prospettiva della stessa famiglia Codex, non nuove misure ambientali indipendenti o certificazione esterna.
- [Portable arithmetic audit / Controllo aritmetico portabile](../scripts/audit_owasco_direction.py) and its [receipt / ricevuta](evidence/owasco-direction-diagnostic/arithmetic-portable-review.json): added after scoring, without importing the selector or recomputing R / aggiunto dopo il calcolo, senza importare il selettore o ricalcolare R.
- [Post-target explanatory partition / Ripartizione esplicativa a posteriori](evidence/owasco-direction-diagnostic/expost-error-mechanism.json). The original review helpers remain local; the portable arithmetic audit and full public row-level report support rechecking / gli strumenti originari di revisione restano locali; il controllo portabile e il rapporto pubblico completo consentono la verifica dei conti.

From the repository root / dalla radice della repository:

```bash
python -B -m unittest discover -s scripts -p 'test_owasco_direction_diagnostic.py' -v
python scripts/owasco_direction_diagnostic.py --protocol docs/datasets/owasco-direction-diagnostic/protocol.json --verify-report docs/evidence/owasco-direction-diagnostic/diagnostic.json
python -B scripts/audit_owasco_direction.py
```

Verification uses saved artifacts only, performs no network call, does not run model prediction code and does not rewrite the report. Every deterministic output field, including input/protocol/implementation hashes, is checked. Creation-time metadata is checked for UTC format and adoption chronology, not independently authenticated by offline replay.

La verifica usa solo gli archivi, senza rete o ricalcolo della regressione, e non riscrive il rapporto. Controlla tutti i campi deterministici e i relativi hash. L'orario di creazione viene controllato per formato UTC e ordine rispetto all'adozione; il replay offline non ne autentica autonomamente l'istante.

| Evidence binding / Vincolo | SHA-256 |
|---|---|
| Adopted protocol / Protocollo | `438b66c99e1ed602ea572d15442e309c82be5972307619e1e63d37702c69d2bd` |
| July saved evaluation / Luglio | `7bd27ec609a7c4f471385498b61fff7b9d74546de13711559e84fcb16536ff85` |
| August saved evaluation / Agosto | `65e1b3793c78982e1496eaf9b3e56e8157d684b6df84343ed5f5b5e0abe98853` |
| Frozen model / Modello | `72d7d14221c7b14c173dba59d69d2a1d36cbb27ee146378b9e046eea998762c9` |
| First diagnostic / Prima diagnostica | `4820b19a9df12356721d5466bacc9c985ce54db162a9d73b68ee0459d9c0b93e` |
