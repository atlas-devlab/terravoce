# Willamette: esperimento numerico reversibile

Questo incremento verifica una domanda limitata: temperatura e portata aiutano
a prevedere l'ossigeno disciolto **un'ora dopo**? Rimane in modalità osservazione.
Il percorso operativo dell'Oracle, il bridge, TerraLex, la governance delle
comunità e dei giovani e i finanziamenti rimangono quelli precedenti.

TerraVoce conserva la missione di coordinamento ambientale globale: analisi
distribuita, evidenze pubbliche resilienti e interventi finanziati e verificabili.
Il Willamette è un banco di prova di un componente riutilizzabile. Il modello
numerico sperimentale non autorizza proposte, pagamenti o attuatori fisici.

## In parole semplici

1. Carichiamo misure pubbliche reali di ossigeno, temperatura e portata.
2. Usiamo una prima parte dei dati per stimare una relazione matematica.
3. Con una seconda parte scegliamo quale variante confrontare definitivamente.
4. Con una terza parte stimiamo un intervallo di errore.
5. Sugli ultimi tre giorni misuriamo quanto sbaglia, senza cambiare il modello.

Non stiamo ancora simulando nuovi scarichi, interventi o il futuro ecologico del
bacino. Quelli richiedono dati e modelli fisici aggiuntivi. Il LLM non esegue
questi calcoli e non è stato richiamato durante l'esperimento.

## Fonti e controlli

Stazione USGS `14211720`, Willamette River at Portland. Intervallo archivistico:
1–15 agosto 2025, UTC, estremi inclusi. Le risposte HTTP originali di temperatura
e portata sono conservate in gzip senza modificare il JSON decompresso; il
manifest contiene URL, serie, unità, data di cattura locale e hash SHA-256.
L'ossigeno e i metadati della stazione restano lo snapshot del primo caso reale.

| Variabile | Parametro / serie | Valori approvati | Unità |
| --- | --- | ---: | --- |
| Ossigeno | `00300` / `1ccd1e712b6b4cb69fdcfbf407f7358b` | 673 | mg/L |
| Temperatura | `00010` / `78520072e15541dea31a430cc3a72b93` | 673 | °C |
| Portata istantanea | `00060` / `25161ce7dc08491389080de10c85fd9e` | 4034 | ft³/s → m³/s |

Conversione della portata: moltiplicazione per `0.028316846592`. I valori
negativi della portata sono conservati: la stazione è in un tratto soggetto alle
maree. Un record autentico ha un orario irregolare; lo conserviamo ma non lo
usiamo per inventare un valore su un altro orario. Non utilizziamo la serie di
portata filtrata dalle maree, il cui filtro potrebbe richiedere misure future.

Accettiamo solo valori finiti, `Approved`, senza qualificatori. Serie, stazione,
statistica `00011`, unità, intervallo, duplicati, paginazione e hash sono
controllati. Ogni previsione richiede 12 misure consecutive per tutte e tre le
variabili agli stessi orari dell'ossigeno e un bersaglio esatto un'ora dopo.
Nessuna interpolazione: dati assenti o esclusi fanno saltare la coppia.

Questi sono dati finalizzati retrospettivi. Approvazioni e revisioni possono
essere successive all'origine simulata: non dimostriamo che un servizio in
tempo reale avrebbe avuto allora questi stessi dati.

## Protocollo e modello

Split, candidati e penalizzazioni sono stati fissati nel manifest prima del fit.
Questo è un esperimento esplorativo, non una preregistrazione indipendente.

| Fase | Origini / bersagli | Coppie |
| --- | --- | ---: |
| Addestramento | Bersagli fino all'8 agosto 00:00 | 324 |
| Scelta | Origini dall'8; bersagli fino al 10 agosto 00:00 | 95 |
| Calibrazione dell'intervallo | Origini dal 10; bersagli fino al 12 agosto 00:00 | 95 |
| Verifica finale | Origini dal 12; bersagli fino al 15 agosto 00:00 | 143 |

Tre coppie attraversano i confini e sono escluse. Ci sono 660 coppie complete e
nessuna origine saltata per dati mancanti. Gli orizzonti sovrapposti e la
dipendenza temporale riducono il numero effettivo di osservazioni indipendenti.

La regressione ridge predice la variazione rispetto all'ossigeno corrente:
`min ||y - Xw||² + alpha ||w||²`. Centratura e standardizzazione sono calcolate
esclusivamente sull'addestramento; l'intercetta non è penalizzata.
Le penalizzazioni confrontate sono `0.1, 1, 10, 100`.

Le varianti aggiungono progressivamente:

- Ossigeno corrente e differenze a 30 minuti, 2 ore e 5,5 ore; seno/coseno
  dell'ora UTC come indicatore del ciclo giornaliero.
- Temperatura corrente e differenza a 2 ore.
- Portata istantanea con segno e differenza a 2 ore.

Le baseline sono l'ultima misura (persistenza) e `terravoce-linear-risk-v1`.
La scelta minimizza il MAE sulla fase di scelta; in caso di parità prevale il
candidato precedente, iniziando dalla persistenza. Non rifittiamo il modello e
non lo scegliamo in base ai risultati finali. Il report conserva tutte le
varianti e i coefficienti, evitando di mostrare soltanto un risultato favorevole.

## Risultato e decisione

Scelto sulla fase di scelta: **ossigeno + ciclo giornaliero + temperatura,
ridge alpha 100**. Le righe sotto usano lo stesso alpha per confrontare le
variabili; il report completo contiene tutte le penalizzazioni.

| Metodo | MAE di scelta (mg/L) | MAE finale (mg/L) |
| --- | ---: | ---: |
| Ultima misura | 0.149474 | 0.267832 |
| Regressione Oracle esistente | 0.178254 | 0.303325 |
| Ossigeno + ciclo giornaliero | 0.131665 | 0.265881 |
| Aggiunta della temperatura, selezionato | 0.129804 | 0.263681 |
| Aggiunta anche della portata | 0.132787 | 0.265250 |

La riduzione del MAE finale rispetto alla persistenza è **1,55%**, troppo poco
e su una finestra troppo breve per sostenere una superiorità generale. La
portata non aggiunge un vantaggio a questa particolare rappresentazione del
modello; non significa che sia irrilevante per il fiume.

Il 90° percentile degli errori assoluti di calibrazione dà una semilarghezza di
**0,406962 mg/L**. L'intervallo contiene il **76,92%** dei valori finali. Questo
scostamento segnala un limite della trasferibilità tra periodi. È un intervallo
empirico, senza garanzia di copertura nominale per dati dipendenti nel tempo.
Non ci sono eventi finali sotto la soglia illustrativa di 5 mg/L, quindi la
capacità di prevedere eventi critici rimane non valutata.

**Decisione: conservare l'esperimento in osservazione. Nessuna sostituzione del
modello operativo, nessuna autorizzazione di spesa.** Il piccolo miglioramento
non costituisce prova di efficacia ecologica o di causalità.

## Riproduzione e ritorno al percorso precedente

Dalla radice, con Node.js 24 e pnpm 11.7.0:

```sh
pnpm install --frozen-lockfile
pnpm build
pnpm check
pnpm test
pnpm forecast:replay
pnpm forecast:verify
```

Per riprodurre il rapporto pubblicato, passando un percorso assoluto:

```sh
pnpm forecast:verify /absolute/path/to/terravoce/docs/evidence/willamette-forecast
```

Il primo comando scrive `outputs/willamette-forecast/forecast.json`. La verifica
ricalcola ogni campo e l'hash dell'intero rapporto dal dataset fissato. Un file
diverso non viene sovrascritto: occorre indicare una nuova cartella. Gli hash
sono impegni del nostro importatore e del rapporto, non firme USGS.

L'esperimento è su una branch e una PR dedicate, impilate sul primo caso reale.
Per rinunciarvi basta non integrare questa PR. I comandi `case:replay`,
`case:verify`, `case:e2e` e l'Oracle non dipendono dai nuovi file. Dopo una futura
integrazione, il commit può essere annullato con un normale revert. Non ci sono
migrazioni, risorse remote, chiavi aggiuntive o modifiche on-chain da rimuovere.

## Test e prossima verifica

I nuovi test controllano una soluzione ridge nota, baseline perfetta, portata
negativa e conversione, qualità dei dati, duplicati/paginazione, hash e query,
assenza di interpolazione, split cronologici e rapporto alterato. Un test cambia
le misure future della verifica finale e accerta che coefficienti, scelta,
intervallo calibrato e previsione precedente restino invariati.

Build/check, 83 test TypeScript/Solidity e 7 test Python sono passati localmente.
Il caso reale sulla blockchain locale riproduce i precedenti caseHash/resultHash
e verifica ancora il blocco del pagamento prima delle due revisioni. Le identità,
i token e il certificato 3-su-4 di quel comando restano fixture locali; il cluster
ABCI con guasti non è stato rilanciato per questo incremento.

Prima di estendere il modello: fissare un esperimento su stagioni e condizioni
diverse, con criteri di errore e copertura dichiarati prima dell'esecuzione.
Successivamente potranno entrare meteo, carichi inquinanti documentati e un
modello fisico calibrato per il tratto pertinente. Una nuova ricerca deve avere
un nuovo manifest e rapporto, senza ritoccare questa verifica finale.

Riferimenti metodologici:

- [Ridge, documentazione scikit-learn](https://scikit-learn.org/stable/modules/linear_model.html#ridge-regression-and-classification).
- [Validazione temporale e variabili ritardate](https://scikit-learn.org/stable/auto_examples/applications/plot_time_series_lagged_features.html).
- [Modelli USGS CE-QUAL-W2 per il Willamette](https://www.usgs.gov/data/ce-qual-w2-models-willamette-river-and-major-tributaries-downstream-us-army-corps-engineers): individuati per gli scenari, non installati o eseguiti in questo incremento. Il dominio fluviale del rapporto 2022 termina alle Willamette Falls; non trasferire automaticamente la calibrazione alla stazione di Portland.
