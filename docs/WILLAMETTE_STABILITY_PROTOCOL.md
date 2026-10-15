# Willamette a un'ora: protocollo prima della nuova verifica

[English explanation](WILLAMETTE_STABILITY_PROTOCOL_EN.md).

**Aggiornamento:** il protocollo storico sotto è rimasto invariato nella sua
definizione. Raccolta e valutazione sono ora state eseguite: consulta
[risultati, verifiche e limiti](WILLAMETTE_STABILITY_RESULTS.md).

La domanda è precisa: **annullare le piccole correzioni quando tutta la storia
recente dell'ossigeno è invariata migliora la previsione su periodi nuovi?**
Restiamo sull'ossigeno disciolto a un'ora, alla stazione USGS-14211720.

La [diagnosi precedente](WILLAMETTE_HOURLY_DIAGNOSTICS.md) ha suggerito la regola.
Quelle finestre sono ormai materiale di sviluppo: non le riusiamo come nuovo
esame finale. La [nuova definizione leggibile dal programma](datasets/usgs-willamette-stability/protocol.json)
fissa regola, calendario e criteri prima di acquisire i nuovi valori.

## La regola, con un esempio

Guardiamo le dodici misure approvate di ossigeno distanziate di 30 minuti,
dall'origine meno 5 ore e 30 minuti fino all'origine. Non guardiamo il target
futuro, neppure la misura di mezz'ora successiva.

- Se sono **tutte esattamente uguali**, la previsione a un'ora è l'ultima misura.
  Si annullano insieme intercetta e tutti gli otto contributi della regressione.
- Se almeno una è diversa, usiamo la previsione completa della stessa regressione.

Esempio inventato per spiegare la regola: dodici valori pari a 9,0 mg/L;
la regressione proporrebbe 9,03 mg/L. La nuova regola restituisce 9,0 mg/L.
Se uno dei dodici valori fosse diverso, restituirebbe la previsione della
regressione. Questo esempio non è un risultato sui nuovi dati.

Non arrotondiamo ulteriormente e non introduciamo una soglia come 0,1 mg/L.
Un cambiamento in un punto intermedio conta anche se i tre delta usati dal
modello risultano zero. «Invariata» riguarda la precisione dei valori pubblicati:
non dimostra che il fiume o l'ecosistema siano fisicamente stabili. La temperatura
può cambiare anche quando l'ossigeno registrato è invariato; questo rende la
regola un'ipotesi da provare, non una legge fisica.

La formula è:

```text
previsione = ossigeno attuale + peso × correzione completa del ridge
peso = 0 se tutti i dodici valori precedenti sono uguali; altrimenti 1
```

## Perché manteniamo i pesi già congelati

Per isolare l'effetto di questa sola regola, riutilizziamo lo stesso ridge a
otto ingressi con alpha=100, già appreso da 2.559 coppie del 2024. Non rifacciamo
il fit, non cambiamo media o scala degli ingressi e non cerchiamo percentuali
alternative di correzione. Il protocollo lega i pesi alla loro impronta:

```text
0x72d7d14221c7b14c173dba59d69d2a1d36cbb27ee146378b9e046eea998762c9
```

Questo permette di chiedere se funziona la modifica, senza confonderla con
nuovi pesi o nuove variabili. Un eventuale riaddestramento sarà un esperimento
successivo, con un altro protocollo e dati di verifica separati.

## Nuovi periodi di verifica

| Finestra | Inizio UTC | Fine UTC | Durata |
| --- | --- | --- | ---: |
| Inverno | 1 febbraio 2025, 00:00 | 1 marzo 2025, 00:00 | 28 giorni |
| Primavera | 1 maggio 2025, 00:00 | 29 maggio 2025, 00:00 | 28 giorni |
| Estate | 1 giugno 2025, 00:00 | 29 giugno 2025, 00:00 | 28 giorni |
| Autunno | 1 novembre 2025, 00:00 | 29 novembre 2025, 00:00 | 28 giorni |

Sono dati storici nuovi per questa verifica, non misure che arriveranno in futuro.
Il controllo del calendario confronta le quattro finestre con gli undici periodi
già acquisiti per questa stazione, compresi i bordi inclusivi delle query USGS.
Non si sovrappongono. La regola è stata ideata dopo altri esperimenti sul 2025:
questa non simula un metodo già definito e disponibile al momento di quelle misure.

Non abbiamo ancora richiesto o letto i valori delle nuove finestre. La presenza
di misure approvate e la loro completezza restano da accertare. Il calendario
è scelto prima dei risultati; un periodo insufficiente o indisponibile sarà
segnalato, senza sostituirlo con uno più favorevole.

Le finestre da 28 giorni offrono circa quattordici blocchi principali di 48 ore,
contro i sette delle vecchie quindicine. Questa durata non dimostra
rappresentatività del bacino o una potenza statistica garantita.

## Come faremo il confronto

Sugli stessi orari confrontiamo tre previsioni: ultima misura invariata
(persistenza), ridge congelato completo e ridge con la nuova regola.
La persistenza risponde «serve una previsione più complessa?»; il ridge completo
risponde «la modifica aiuta rispetto a ciò che avevamo?».

Manteniamo le regole di qualità e allineamento precedenti: dodici misure
approvate, senza qualificatori e finite nelle tre serie, poi un target esatto
a un'ora. Conserviamo il segno della portata. La portata serve ancora per la
stessa selezione dei casi, pur non entrando negli otto ingressi: cambiare anche
questa selezione renderebbe meno isolato il confronto.

Ogni finestra ha **1.332 origini teoriche** utilizzabili dopo la storia iniziale.
Richiediamo almeno 1.000 coppie e il 90% di copertura di questa griglia. Il 90%
richiede in pratica almeno 1.199 coppie: gli orari assenti rimangono nel
denominatore. Non interpoliamo vuoti e non eliminiamo grandi errori.

## Criteri di successo fissati prima dei risultati

La metrica principale è la MAE: media degli errori assoluti in mg/L.
Calcoliamo una MAE per finestra e poi la media delle quattro, dando lo stesso
peso alle stagioni. Il successo di ricerca richiede **tutte** queste condizioni:

1. Tutte le quattro finestre superano il filtro di completezza e consentono
   il calcolo dell'incertezza. Previsioni non finite o negative fanno fallire
   la prova; non vengono nascoste con un taglio a zero.
2. La MAE media della candidata è inferiore sia alla persistenza sia al ridge
   completo. Se non compaiono casi con storia invariata, la regola non è stata
   messa alla prova e il risultato sarà `stability-rule-not-exercised`.
3. Nessuna delle quattro MAE stagionali peggiora rispetto a uno dei due
   confronti. La tolleranza 1e-9 mg/L serve soltanto agli arrotondamenti del
   calcolo, non a giustificare un peggioramento ambientale.
4. Il limite inferiore dell'intervallo esplorativo al 95% del vantaggio rimane
   positivo rispetto a entrambi i confronti. Questa condizione deve valere
   con blocchi principali di 48 ore e con le sensibilità a 24 e 72 ore.

Usiamo un bootstrap appaiato: ricampioniamo blocchi di orari, mantenendo
insieme osservazione e previsioni dei tre metodi. Facciamo 5.000 ricampionamenti
con seme fissato, dentro ciascuna stagione, poi ricomponiamo la media stagionale.
Non trattiamo migliaia di misure consecutive come migliaia di prove indipendenti.

Gli intervalli rimangono esplorativi e dipendono dalle finestre e dalla scelta
dei blocchi. Le sensibilità non sono conferme indipendenti; applicare più
criteri non dà automaticamente una garanzia congiunta del 95%. L'assenza di
peggioramento puntuale non prova noninferiorità statistica in ogni stagione.

Il **10% non è una soglia obbligatoria**. Riporteremo il vantaggio assoluto e
relativo; se il riferimento ha errore zero, la percentuale sarà `null`.
Non abbiamo ancora definito una soglia di utilità ecologica. RMSE, bias,
95° percentile degli errori, risultati giornalieri, conteggi del gruppo invariato
e cali registrati restano visibili anche se la MAE migliora. Un gruppo stagionale
invariato vuoto avrà metriche `null`, senza una conclusione su quel gruppo.

Se un intervallo comprende zero parleremo di vantaggio inconcludente; se una
stagione peggiora parleremo di compromesso stagionale; se i dati non bastano,
di dati insufficienti. Non cercheremo un'altra regola sugli stessi nuovi esami
per presentarla poi come già validata.

## Cosa è pronto e cosa verrà eseguito dopo

Questo incremento contiene il protocollo, il controllo del calendario e delle
impronte dei pesi, e una funzione sperimentale della regola verificata con dati
sintetici. Il comando seguente controlla la preparazione, senza acquisire nuovi
valori, addestrare o misurare la capacità predittiva:

```sh
python scripts/stability_protocol.py
python -m unittest discover -s scripts -p 'test_stability_protocol.py' -v
```

Prima di acquisire i nuovi valori, protocollo e codice vengono conservati in Git.
Anche i nuovi programmi di acquisizione e valutazione dovranno essere versionati
prima della lettura dei target di verifica.
Il futuro raccoglitore dovrà legare ogni manifesto a quel commit, all'impronta
del protocollo e a quella dei pesi. Poi conserveremo le risposte originali
e valuteremo una sola volta tutti e tre i metodi, senza fit o tuning.
Il nuovo raccoglitore e il valutatore specifico di queste finestre non sono
ancora implementati o eseguiti in questo incremento.

Una prova positiva supporterebbe soltanto questa previsione puntuale a un'ora
nelle condizioni studiate. Non dimostrerebbe previsioni live, disponibilità
storica dei dati all'origine, una fascia predittiva calibrata, inquinamento,
benefici sul campo o accuratezza a 24 ore o tre mesi. L'Oracle operativo,
le decisioni delle comunità e dei giovani e l'autorizzazione dei fondi rimangono
separati: il risultato di ricerca non li attiva automaticamente.

Riferimenti: [confronti e verifica temporale](https://otexts.com/fpp3/toolbox.html#time-series-cross-validation),
[documentazione delle misure USGS](https://api.waterdata.usgs.gov/docs/ogcapi/migration/).
