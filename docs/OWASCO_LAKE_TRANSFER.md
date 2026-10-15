# Owasco Lake: primo test di trasferimento a un'ora

[English explanation](OWASCO_LAKE_TRANSFER_EN.md).

**Stato: protocollo preparato; acquisizione e risultati del lago ancora in attesa.**
Questo documento descrive la prova prima di leggere le osservazioni lacustri.
Non attribuisce ancora un vantaggio a nessuno dei quattro metodi.

## 1. La domanda che vogliamo verificare

Il modello sviluppato sul Willamette sa prevedere l'ossigeno un'ora dopo
anche presso una sonda di un lago, senza imparare dai risultati di quel lago?
È una prova rigorosa di trasferimento geografico e ambientale.
Non stiamo costruendo un modello ottimizzato localmente per Owasco.
Un insuccesso sarebbe un risultato da conservare, non un motivo per cambiare
il lago, il periodo o la soglia dopo aver visto gli errori.

## 2. Che cosa abbiamo scelto e perché

La fonte è la piattaforma **USGS-425327076313601, Owasco Lake, New York**.
Il lago naturale ha una profondità massima descritta di circa 50 metri.
Il bacino comprende attività agricole: non lo presentiamo come incontaminato.
La scelta usa metadati e documentazione strumentale, non valori o prestazioni.
Restiamo presso USGS: cambia l'ecosistema, non diventa una conferma da un ente
indipendente rispetto alla fonte del Willamette.

| Misura | Codice | Serie congelata | Collocazione di catalogo |
|---|---|---|---|
| Ossigeno, mg/L | `00300` | `b3904dc881b44599bc5f7eeb63da5a40` | EXO 1; Depth at 3 feet |
| Temperatura, °C | `00010` | `d584a0bd0b6f4e979451c8498c85a192` | EXO 1; Depth at 3 feet |

Sono due parametri della **stessa sonda EXO 1**, con serie primarie istantanee.
Il rapporto USGS descrive campionamenti ogni 15 minuti. La soglia di rilevamento
dei vuoti `data_gap_interval: PT1H12M` non è la frequenza di campionamento.
C'è una differenza documentale da mantenere visibile: il catalogo dice
**3 piedi**, mentre la tabella del rapporto indica **0,76 m** per la sonda
superficiale di Owasco. Conserviamo entrambe le descrizioni; non affermiamo
di avere verificato indipendentemente una profondità esatta. Non mescoliamo
EXO 2, EXO 3 o sensori di temperatura della catena verticale.

Abbiamo considerato Lake Suggs della rete NEON, ma l'accesso all'elenco dei file
richiede autenticazione e la temperatura alla stessa profondità non era ancora
verificata. Lake Houston pubblica una sequenza di profondità con una misura
oraria per profondità: non la interpoliamo per creare la storia a 30 minuti.

## 3. Il filtro scelto sul Willamette

Lo [sviluppo archiviato](evidence/willamette-threshold-development/evaluation.json)
ha scelto **τ = 0,10 mg/L** usando esclusivamente finestre già studiate sul
Willamette. I pesi della regressione sono rimasti invariati.

| Parte dello sviluppo | MAE persistenza | MAE filtro |
|---|---:|---:|
| Selezione A, media di quattro finestre | 0,08488555 mg/L | 0,08191451 mg/L |
| Controllo temporale interno B, stessa media | 0,09348669 mg/L | 0,08802214 mg/L |

Il miglioramento descrittivo su B è circa **5,845%**. Entrambe le parti erano
già state osservate: **non è una nuova validazione indipendente** e non prova
ancora che la soglia funzioni su Owasco. Su B non sono state provate altre soglie.

## 4. Quattro metodi sullo stesso identico insieme di orari

- **P, persistenza:** ripete l'ultima misura di ossigeno.
- **R, regressione congelata:** applica integralmente la correzione originale.
- **C, vecchio fallback:** usa P se le dodici misure storiche sono tutte uguali;
  negli altri casi usa R.
- **F, filtro delle piccole correzioni:** usa P se `abs(R - P) <= 0,10 mg/L`;
  negli altri casi usa R. Questa è una regola separata da C.

Gli otto ingressi e il loro ordine restano invariati: ossigeno attuale,
variazioni a 30 minuti, 2 ore e 5 ore e 30 minuti, seno/coseno dell'ora UTC,
temperatura attuale e sua variazione a 2 ore. Manteniamo coefficienti,
standardizzazione e orologio UTC: nessun adattamento all'ora locale,
riaddestramento, nuova variabile o scelta di soglia sui dati del lago.

## 5. Periodo e qualità, fissati prima dei valori

Il [protocollo](datasets/owasco-lake-transfer/protocol.json) fissa **1–29 luglio
2020, ore 00:00 UTC, estremi della richiesta inclusi**: una finestra di 28 giorni.
Per ogni origine esatta `:00` o `:30` servono dodici misure consecutive a
mezz'ora di ossigeno e temperatura, più l'ossigeno esattamente un'ora dopo.
La storia termina all'origine e copre cinque ore e trenta minuti.
Non interpoliamo, mediamo o riempiamo i vuoti; i quarti d'ora non utilizzati
rimangono nell'archivio grezzo. Accettiamo valori approvati, senza qualificatori,
finiti, con ossigeno non negativo, identità di serie e unità corrette.
Duplicati, paginazione e troncamenti devono essere rilevati.

La portata non è uno degli otto ingressi della regressione. Sul Willamette
era richiesta per costruire il campione; sul lago l'ammissibilità richiede
esplicitamente solo ossigeno e temperatura. È una differenza del campione,
non una portata mancante riempita con zero.

Sono previste **1.332 origini possibili**. Il controllo pratico richiede almeno
1.000 coppie e il 90% delle origini attese: non è un calcolo di potenza
statistica, un'accuratezza strumentale o una certificazione ecologica.

## 6. Come giudicheremo il risultato

La **MAE in mg/L** sul medesimo campione è il criterio principale.
F deve avere MAE inferiore a P, oltre la tolleranza numerica di `1e-9 mg/L`,
con completezza sufficiente e previsioni finite e non negative.
Il bootstrap appaiato a blocchi di calendario di 48, 24 e 72 ore, 5.000
ricampionamenti ciascuno, deve dare un limite inferiore positivo per il
guadagno `errore assoluto P - errore assoluto F` in tutti e tre i casi.
Sono intervalli esplorativi condizionati a questa finestra, non intervalli
di previsione né tre conferme indipendenti. RMSE, bias, errori estremi,
confronti giornalieri e uscite dai range di addestramento restano diagnostici.

## 7. Tracciabilità, limiti e risultati in attesa

Il protocollo impone di committare e pubblicare codice, metadati, soglia e
calendario prima della prima richiesta di misure del lago. L'acquisizione
consente un solo tentativo esclusivo, conserva i corpi grezzi e i fallimenti,
e vieta retry automatici o sostituzione della finestra. Gli hash collegano
gli archivi al codice; non autenticano da soli la verità fisica del sensore.

Il modello è stato addestrato su dati Willamette del **2024**, mentre questa
prova usa un archivio lacustre del **2020**: non simula ciò che il sistema
avrebbe potuto sapere nel 2020. Una sonda e un'estate non dimostrano capacità
su tutto il lago, i fondali, quattro stagioni, altri laghi o previsioni live.
Non sono definiti benefici ambientali pratici né autorizzazioni operative.

**Risultati: in attesa.** Sono previsti `docs/evidence/owasco-lake-transfer/evaluation.json`
e `docs/notebooks/owasco-lake-transfer.ipynb`; non sono ancora presentati come
artefatti completati. Questa prova non cambia Oracle operativo, quorum,
governance, tesoreria, token o spese: serve a produrre prove ambientali
comprensibili e verificabili a sostegno delle comunità e dei giovani.

## Fonti primarie

- [Scheda ufficiale della piattaforma Owasco](https://waterdata.usgs.gov/monitoring-location/USGS-425327076313601/).
- [USGS SIR 2024-5010: strumenti, profondità, frequenza e qualità](https://pubs.usgs.gov/publication/sir20245010/full).
- [Catalogo API ufficiale, sonda EXO 1](https://api.waterdata.usgs.gov/ogcapi/v1/collections/time-series-metadata/items?monitoring_location_id=USGS-425327076313601&sublocation_identifier=EXO%201&limit=50&f=json).
