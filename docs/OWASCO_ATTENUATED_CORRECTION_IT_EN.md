# Owasco: correzione attenuata / attenuated correction

## Italiano

**Esito: questa candidata non supera il criterio concordato.** Ad agosto riduce
la MAE rispetto all'ultima misura; a luglio la aumenta. Serviva un miglioramento
in entrambi i mesi. Conserviamo il risultato e fermiamo questa candidata, senza
modificare la regressione o aprire settembre.

### 1. Che cosa abbiamo provato

Prevediamo l'ossigeno disciolto un'ora dopo, nella stessa postazione USGS del
lago Owasco, `USGS-425327076313601`. Sono le finestre archiviate dal 1° luglio
alle 00:00 UTC del 29 luglio e dal 1° agosto alle 00:00 UTC del 29 agosto 2020,
non due mesi interi. `P` ripete l'ultima misura; `R` è la previsione della regressione
Willamette già salvata. I pesi, gli otto ingressi, le previsioni R e i dati
originali restano identici. Il vecchio filtro `F` usa R soltanto quando la
correzione `c=R-P` supera 0,100 mg/L in valore assoluto; altrimenti usa P.

La sola nuova candidata `Q` attenua quella correzione:

- Se `abs(c) <= 0,100`, mantiene P.
- Altrimenti sottrae 0,100 all'ampiezza della correzione, ne mantiene il segno e
  aggiunge a P soltanto la parte restante.

Esempio **inventato**: ultima misura 10,00 e regressione 10,18 diventano 10,08.
La nuova regola riduce l'ampiezza, non il numero delle correzioni ammesse dal
vecchio filtro. Non usa la precedente regola direzionale delle due ore.
0,100 è il parametro ereditato dal precedente lavoro di sviluppo, non una
misura dell'accuratezza del sensore o una soglia ecologica. Non abbiamo cercato
altri valori.

### 2. Come abbiamo evitato di adattare la regola al risultato

Protocollo, codice e test sintetici sono stati congelati e pubblicati nel commit
`c69f63ca3f5a8d2dad322cad53e3d1dcb32f7ac2` prima del primo score di Q.
La verifica del commit remoto è delle **17:02:38 UTC del 16 ottobre 2026**;
il primo risultato salvato è delle **17:02:41 UTC**. La ricevuta non sostiene
che questi mesi fossero nuovi: erano già stati studiati. È un controllo di
sviluppo retrospettivo, non una nuova validazione alla cieca.

La MAE è la media di `abs(previsione - misura osservata dopo un'ora)`: più bassa
è, meglio è. Il criterio fissato prima dello score richiede Q valido su tutte
le righe e `MAE(P)-MAE(Q) > 0,000000001 mg/L` **separatamente in entrambi i mesi**.
Questa tolleranza numerica non certifica significatività statistica o utilità
ambientale. Nessuna riga è stata eliminata per migliorare il risultato.

### 3. Risultato completo: MAE in mg/L

| Metodo | Luglio: 1.275 casi | Agosto: 1.306 casi |
|---|---:|---:|
| P: ultima misura | 0,038666666667 | 0,055513016845 |
| R: regressione invariata | 0,048165907157 | 0,066183549661 |
| F: vecchio filtro | 0,038692359932 | 0,055453386176 |
| Q: correzione attenuata | 0,038692359932 | 0,055435990071 |
| Guadagno di Q su P, positivo = meglio | −0,000025693266 | +0,000077026774 |

Luglio fallisce il criterio; agosto lo supera. L'esito congiunto è quindi
**negativo**. Tutte le 2.581 previsioni Q sono finite e non negative.

Q cambia 4 previsioni a luglio: 2 migliorano P, 2 lo peggiorano, 1.271 restano
uguali. Ad agosto ne cambia 16: 8 migliorano P, 8 lo peggiorano, 1.290 restano
uguali. Sono gli stessi istanti ammessi da F; in questi dati non ci sono gate
attivi con Q arrotondato a P. Le correzioni sono distribuite su 3 giorni UTC a
luglio e 7 ad agosto: non vanno trattate come eventi tutti indipendenti.

Contare vittorie e sconfitte non basta per la MAE. A luglio i benefici di Q
sommano a 0,003937426722 mg/L, i danni a 0,036696340239: prevalgono i danni.
Ad agosto i benefici sommano a 0,354870982635, i danni a 0,254274015600:
prevalgono i benefici. Sono somme descrittive di differenze di errore per riga,
non un effetto ambientale fisico.

### 4. Quando aiuta e quando sbaglia: quattro esempi reali

Sono i primi casi cronologici delle categorie definite prima dello score,
identificati **dopo** aver osservato il valore futuro, solo per spiegare.
Tutti gli orari sono UTC; numeri arrotondati qui a sei decimali.

| Origine → verifica un'ora dopo | P | F (= R in questi casi) | Q | Osservato |
|---|---:|---:|---:|---:|
| 1 luglio 09:30 → 10:30, riga 8 | 10,000000 | 9,896630 | 9,996630 | 9,800000 |
| 4 luglio 08:00 → 09:00, riga 149 | 10,200000 | 10,070540 | 10,170540 | 10,200000 |
| 1 agosto 07:30 → 08:30, riga 4 | 9,400000 | 9,287036 | 9,387036 | 9,400000 |
| 1 agosto 19:30 → 20:30, riga 28 | 9,400000 | 9,504143 | 9,404143 | 9,500000 |

**1 luglio: Q aiuta appena rispetto a P, ma attenuare peggiora F.** Il valore
pubblicato scende da 10,0 a 9,8. P sbaglia di 0,200000, F di 0,096630, Q di
0,196630. La regressione proponeva una discesa utile; ridurla quasi a zero
rinuncia a gran parte del beneficio.

**4 luglio: attenuare aiuta F, ma Q continua a sbagliare rispetto a P.** Il
valore pubblicato resta 10,2. P ha errore zero; F ha errore 0,129460; Q riduce
l'errore a 0,029460. Abbiamo limitato il danno della correzione, senza eliminarlo.

**1 agosto, mattina: lo stesso tipo di errore residuo.** Il valore pubblicato
resta 9,4. L'errore passa da 0,112964 con F a 0,012964 con Q; P aveva errore zero.
Ridurre una correzione inutile non equivale a riconoscere quando evitarla.

**1 agosto, sera: Q aiuta P, ma attenua una previsione F già molto buona.** Il
valore sale da 9,4 a 9,5. P sbaglia di 0,100000; F di 0,004143; Q di 0,095857.
La riduzione dell'ampiezza toglie quasi tutto il beneficio di F.

Le categorie si sovrappongono: i primi esempi di Q migliore/peggiore di P sono
anche i primi esempi di attenuazione peggiore/migliore di F. Non sono otto eventi
distinti. Il valore futuro non entra nella previsione e non può diventare una
regola utilizzabile in anticipo.

### 5. Perché a luglio Q e F hanno la stessa MAE

Non sono previsioni identiche. Nei due casi dove attenuare aiuta F, l'errore
totale si riduce di circa 0,200000 mg/L. Nei due casi dove lo danneggia,
l'errore aumenta della stessa quantità. La somma delle differenze Q–F è zero
con i valori binary64 archiviati, quindi le MAE coincidono esattamente.
Ad agosto la riduzione totale rispetto a F è 0,022719313308 mg/L, che divisa
per 1.306 dà un vantaggio MAE di appena 0,000017396105 mg/L.

### 6. Modifiche, verifiche e limite della conclusione

Sono nuovi soltanto il protocollo Q, il diagnostico offline, 17 test sintetici,
il rapporto per riga, un controllo aritmetico separato e la documentazione
IT/EN. La CI verifica i risultati senza sovrascriverli. La suite Python ha
superato 169 test. Il replay controlla esattamente input, codice, cronologia,
previsioni, gruppi e risultato. Il controllo aritmetico separato ricostruisce Q
dai P/R salvati, senza importare il diagnostico e senza ricalcolare R.
È una seconda implementazione della stessa famiglia Codex, non una fonte
ambientale o una validazione scientifica indipendente.

I dati restano archivi USGS finalizzati del 2020, in una sola postazione vicino
alla superficie; non dimostrano disponibilità in tempo reale. Letture pubblicate
uguali non dimostrano stabilità fisica e i decimali non certificano accuratezza.
Luglio/agosto sono già aperti e le correzioni attive sono poche e raggruppate
nel tempo. Il piccolo vantaggio di agosto non prova generalizzazione, sicurezza
ecologica o capacità di anticipare eventi critici.

**Decisione: fermare questa specifica Q.** Prima di un altro esperimento,
discutere insieme quale informazione disponibile al momento della previsione
potrebbe distinguere correzioni utili e inutili. Non proponiamo qui una nuova
regola, soglia o un nuovo modello. Settembre resta chiuso. Oracle, blockchain,
consenso, governance e fondi restano fuori da questo esperimento. Virdacora
mantiene l'obiettivo di prove ambientali comprensibili e verificabili al
servizio delle comunità, conservando anche gli esiti negativi.

## English

**Outcome: this candidate fails the adopted development screen.** Attenuated
correction Q improves full-cohort MAE over persistence P in August but worsens
it in July. Both months had to improve separately. Preserve the negative joint
result and stop this candidate; do not change the frozen regression or open
September.

### Rule and prerecording

P is the last observation; R is the exact archived frozen Willamette ridge
prediction. Old F uses R only for `abs(R-P)>0.100 mg/L`, otherwise P. Q retains
P when `abs(c)<=0.100`; otherwise it subtracts 0.100 from `abs(c)`, restores
the sign of c and adds this smaller correction to P. The implementation fixes
that binary64 operation order; algebraic rewrites, rounding, clipping and
epsilon-based routing are forbidden. Q does not use the failed two-hour gate.
An **invented** P=10.00, R=10.18 gives Q approximately 10.08.

The archived windows at `USGS-425327076313601` run from July 1 to July 29
00:00 UTC and August 1 to August 29 00:00 UTC, 2020; these are not full months.

Protocol, implementation and synthetic tests were committed and pushed at
`c69f63ca3f5a8d2dad322cad53e3d1dcb32f7ac2`, verified remotely at 17:02:38 UTC
on 16 October 2026, before the first Q report at 17:02:41 UTC. These months
had already been inspected: this is retrospective development, not new blind
validation. The inherited 0.100 is neither sensor accuracy nor an ecological
threshold. No other parameter was tried.

The adopted screen requires valid nonnegative finite Q on every original row
and `MAE(P)-MAE(Q)>1e-9 mg/L` in **both** months. That numerical tolerance is
not statistical significance. No row is removed or silently rescued.

### Full-cohort results, mg/L

| Method | July, N=1,275 | August, N=1,306 |
|---|---:|---:|
| Persistence P | 0.038666666667 | 0.055513016845 |
| Unchanged ridge R | 0.048165907157 | 0.066183549661 |
| Old hard filter F | 0.038692359932 | 0.055453386176 |
| Attenuated correction Q | 0.038692359932 | 0.055435990071 |
| MAE gain of Q over P, positive is better | -0.000025693266 | +0.000077026774 |

July fails; August passes; the joint screen fails. All 2,581 Q values are valid.
July changes 4 predictions: 2 improve P, 2 worsen it and 1,271 tie. August
changes 16: 8 improve, 8 worsen and 1,290 tie. The gate-active origins equal
old F's; no activated Q rounds back to P in these real rows. Q reduces
amplitudes rather than the number of old F interventions. Active origins occupy
3 UTC days in July and 7 in August; do not assume independent events.

Equal win/loss counts do not imply equal MAE. July Q gains total 0.003937426722
against P while losses total 0.036696340239. August gains total 0.354870982635
and losses 0.254274015600. These are sums of paired error differences, not
physical environmental effects.

### Four real illustrations

The Italian table above provides the exact source-row indices and UTC times
for four unique cases, rounded to six decimals for display only:

- **July 1, 09:30 → 10:30 (row 8):** P=10.0, observed=9.8, F=9.896630,
  Q=9.996630. Errors are P=0.200000, F=0.096630, Q=0.196630. Q barely helps
  P while attenuation damages an originally useful F correction.
- **July 4, 08:00 → 09:00 (row 149):** P=observed=10.2, F=10.070540,
  Q=10.170540. Attenuation cuts F's error from 0.129460 to 0.029460, but P
  had zero error. Improving F does not guarantee beating P.
- **August 1, 07:30 → 08:30 (row 4):** P=observed=9.4, F=9.287036,
  Q=9.387036. Error falls from F's 0.112964 to Q's 0.012964, still worse
  than P's zero error.
- **August 1, 19:30 → 20:30 (row 28):** P=9.4, observed=9.5, F=9.504143,
  Q=9.404143. Errors are P=0.100000, F=0.004143, Q=0.095857. Q helps P but
  removes most of the benefit of F.

These are the first chronological matches of four fixed explanatory categories
in each month; the categories overlap. They were labelled after the target was
observed and never entered prediction routing. All active rows retain their
original history/features in the machine-readable report.

July's identical Q/F MAE is real cancellation: attenuation reduces summed
error by approximately 0.2 on two rows and increases it by the same amount on
two other rows. The archived binary64 paired sum is exactly zero. August's
summed improvement over F is 0.022719313308; divided by 1,306 this is a MAE
gain of only 0.000017396105.

### Verification, limitations and decision

New files add the Q protocol, offline diagnostic, 17 synthetic tests, saved
row-level evidence, a separate arithmetic audit and IT/EN documentation.
The Python suite passes 169 tests. CI replays rather than rewrites the evidence.
The separate implementation reconstructs Q directly from saved original P/R
and targets without importing production routing or recomputing R. It is an
internal same-Codex-family check, not independent environmental validation.

Finalized 2020 USGS records at one near-surface site do not establish real-time
availability, sensor accuracy or physical invariance when published values
match. These already-open months and few clustered active cases do not
establish generalization, ecological safety or reliable critical-event warnings.
Original inputs, model, P/R/F, previous results and the failed directional
diagnostic are preserved. There is no refit, threshold search, new observation,
September acquisition or operational Oracle/blockchain/governance change.

**Stop this Q candidate.** Discuss what origin-available evidence could
distinguish useful from unnecessary corrections before adopting another test;
no new selector or parameter is chosen here. Preserving an unfavourable result
supports Virdacora's mission: understandable, verifiable environmental evidence
serving communities.

## Evidence and offline replay / Prove e riproduzione offline

- [Adopted protocol](datasets/owasco-attenuation-diagnostic/protocol.json)
- [Row-level diagnostic](evidence/owasco-attenuation-diagnostic/diagnostic.json)
- [Freeze before score](evidence/owasco-attenuation-diagnostic/freeze-before-score.json)
- [Pre-score static review](evidence/owasco-attenuation-diagnostic/pre-score-static-review.json)
- [Tests and preservation](evidence/owasco-attenuation-diagnostic/pre-score-tests-and-preservation.json)
- [Explanation review](evidence/owasco-attenuation-diagnostic/explanation-review.json)
- [Separate arithmetic audit](evidence/owasco-attenuation-diagnostic/independent-arithmetic-review.json)

Run from the repository root; these commands do not acquire observations or
overwrite the saved result:

```sh
python -B -m unittest discover -s scripts -p 'test_*.py'
python -B scripts/owasco_attenuation_diagnostic.py --protocol docs/datasets/owasco-attenuation-diagnostic/protocol.json --verify-report docs/evidence/owasco-attenuation-diagnostic/diagnostic.json
python -B scripts/audit_owasco_attenuation.py
```

First diagnostic SHA-256:
`0a5dad4d240073028fc05d5671a86a36fe567e0b79a0a888e70f34c7d270974c`.
