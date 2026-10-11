# Awash: primo test osservativo e gioco delle previsioni

Il primo turno storico è completato: TerraVoce ha previsto **2,98 mm/giorno** di
evapotraspirazione e intercettazione; FAO WaPOR stima **3,04 mm/giorno** per il
periodo 1–10 marzo 2024. L'errore assoluto è **0,0603 mm/giorno**, circa il 2% del
valore FAO di riferimento. Il metodo è la persistenza: ripetere l'ultimo valore.
Questa è la base semplice che un futuro modello dovrà battere. Non è un nuovo
modello addestrato, né un risultato ottenuto dall'LLM.

È un singolo esercizio storico, non una validazione della capacità di prevedere
l'irrigazione. Abbiamo implementato la raccolta di un indicatore, la previsione
salvata prima dell'acquisizione del riferimento e la verifica riproducibile.
Quantità d'acqua prelevata, attribuzione all'irrigazione e beneficio ecologico
restano sconosciuti. Il test sull'ossigeno del Willamette conserva i suoi risultati
e la sua separazione dal sistema operativo.

## La domanda che possiamo verificare adesso

Possiamo seguire una stima aperta dell'acqua persa verso l'atmosfera in un piccolo
riquadro dell'Awash e verificare una previsione semplice del periodo successivo?
Il riquadro è `[39.20, 8.47, 39.22, 8.49]` in longitudine/latitudine WGS84,
vicino a Wonji. È una scelta dimostrativa, non un confine aziendale verificato,
una mappa aggiornata dei campi irrigati o una rappresentazione di tutto il bacino.

La scelta di Wonji ha un contesto documentato: FAO descrive uno studio di
validazione dei prodotti WaPOR nel sistema irriguo Wonji Shoa nell'alto Awash.
Quel precedente non valida il nostro riquadro, la nostra previsione o queste
versioni dei dati. [Scheda FAO dello studio](https://www.fao.org/in-action/remote-sensing-for-water-productivity/applications-and-uses/applications-catalogue/product-detail/Validation-of-FAO-frame-remote-sensing-based-agricultural-water-productivity-estimates-in-the-upper-Awash-river-basin-Ethiopia/en).

## Dati usati e significato

| Periodo | Evapotraspirazione e intercettazione | Pioggia |
| --- | ---: | ---: |
| 1–10 febbraio 2024 | 1,8825 mm/giorno | 0,4000 mm/giorno |
| 11–20 febbraio 2024 | 2,2023 mm/giorno | 0,6000 mm/giorno |
| 21–29 febbraio 2024 | 2,9814 mm/giorno | 2,7999 mm/giorno |
| 1–10 marzo 2024, acquisito dopo la previsione | 3,0417 mm/giorno | 7,9998 mm/giorno |

AETI somma evaporazione dal suolo, traspirazione della vegetazione ed evaporazione
dell'acqua intercettata dalle foglie. La pioggia deriva dal prodotto CHIRPS
distribuito da FAO. Sono stime, non letture di contatori, campioni d'acqua o
misure di portata del fiume. Le descrizioni, unità e fattori di scala delle due
[serie FAO](https://data.apps.fao.org/gismgr/api/v2/catalog/workspaces/WAPOR-3/mapsets/L2-AETI-D)
[sono archiviate](https://data.apps.fao.org/gismgr/api/v2/catalog/workspaces/WAPOR-3/mapsets/L1-PCP-D).

Entrambe le serie sono medie giornaliere su una decade di calendario: giorni
1–10, 11–20 e 21–fine mese. L'ultimo periodo di febbraio 2024 dura **9 giorni**,
non 10. Il totale del periodo si calcola moltiplicando la media per i giorni.
Per marzo la previsione corrisponde a 29,8137 mm in dieci giorni, contro la stima
FAO di 30,4169 mm: differenza di circa 0,6033 mm.

La griglia AETI è nominalmente circa 100 m; quella della pioggia circa 5 km.
Nel nostro riquadro intersecano **462 celle AETI e 2 celle di pioggia** per
periodo. Calcoliamo medie ponderate per la superficie di sovrapposizione delle
celle native, senza creare dettagli meteorologici a 100 m. I pesi usano una
superficie sferica; non calcoliamo qui volumi irrigui. Tutti gli otto ritagli
hanno copertura valida completa. Nessuna cella mancante viene sostituita con zero.

## Come funziona il turno

1. Il protocollo fissa area, periodi, fonti e metodo prima della raccolta.
2. Acquisiamo soltanto i tre periodi di febbraio.
3. Salviamo la previsione di marzo: l'ultima media AETI di febbraio.
4. Solo dopo acquisiamo marzo e calcoliamo la differenza.
5. Python riproduce le medie dagli estratti nativi; TypeScript ricontrolla
   il riferimento AETI, l'errore e i collegamenti crittografici.

Il protocollo è nel commit `819a076`; dati storici e previsione nel commit
`a3615e6`, pubblicato prima dell'acquisizione dei ritagli di marzo. Non abbiamo
selezionato il periodo sulla base dell'errore e non abbiamo modificato la
previsione dopo aver scoperto il riferimento. La tolleranza numerica di
ricomputazione è 1e-10; i confronti degli hash restano esatti.

Usiamo **revisioni attualmente disponibili** di dati del 2024: i raster AETI
riportano aggiornamenti nel maggio 2026 e quelli della pioggia nel novembre 2025.
Non abbiamo ricostruito quando quelle stime fossero disponibili nel 2024.
Questo limita il test a un gioco retrospettivo: non dimostra il funzionamento
di una previsione emessa davvero in quelle date. Un solo turno non consente
di valutare stagioni, eventi estremi, intervalli d'incertezza o abilità generale.
La vicinanza al riferimento riguarda una stima FAO, non una verità misurata sul campo.

## Collegamento con TerraVoce

```mermaid
flowchart LR
  A[Dati aperti FAO] --> B[Copie, unità e controlli]
  B --> C[Previsione salvata e riferimento successivo]
  C --> D[Rapporto di ricerca verificabile]
  D -. passo futuro .-> E[Esame scientifico e comunità locale]
  E -. dopo una verifica sul campo .-> F[Proposta di intervento e verifica dei risultati]
```

Il modulo ambientale produce un rapporto identificato da hash e classificato
come **ricerca storica su stime satellitari**. Non lo trasforma in una misura
firmata da un sensore, in un allarme dell'Oracle o in un beneficio ecologico
certificato. `operationalEligible`, `fundingRelease` e
`ecologicalImprovementVerified` restano falsi. Il prelievo irriguo resta `null`.

Questo mantiene la missione originaria: evidenze controllabili, analisi
distribuita, decisioni delle comunità e dei giovani e finanziamenti collegati
a risultati verificati. In questo turno il ponte Open Autonomy, le regole
TerraLex, il voto e i contratti di finanziamento non ricevono nuove azioni.
L'LLM non viene chiamato. Un hash permette di riconoscere una copia; non prova
che una stima descriva correttamente il territorio.

## Strumenti economici per il successivo confronto sul campo

Per trasformare questo indicatore in conoscenza sull'irrigazione servono un
partner locale e un'area agricola verificata. La scheda di raccolta deve
registrare codice del sito, periodo, metodo, unità, fonte e incertezza.
Si possono riutilizzare telefoni Android con
[ODK Collect](https://docs.getodk.org/collect-intro/), che raccoglie dati offline.
Una scheda cartacea equivalente evita di dipendere dalla connessione.

La prima grandezza da cercare è il volume effettivamente applicato o prelevato,
preferibilmente da un contatore esistente. Ore di pompa moltiplicate per una
portata verificata producono una **stima** quando le condizioni di funzionamento
lo permettono: non vanno etichettate come lettura del contatore. Un pluviometro
manuale può aiutare a verificare la pioggia locale; i registri di irrigazione
descrivono tempi e modalità dell'attività. Non abbiamo acquistato, installato
o validato questi strumenti nel territorio.

AETI meno pioggia **non è automaticamente acqua irrigata**: entrano in gioco
acqua già nel suolo, falda, apporti laterali, drenaggio, errori delle stime e
colture presenti. Nemmeno una diminuzione di AETI dimostra da sola un risparmio
idrico: potrebbe riflettere colture in sofferenza o una riduzione della produzione.
Il futuro confronto dovrà considerare acqua, condizioni delle colture e accesso
delle persone all'acqua, con scelta e interpretazione condivise localmente.

## Riproduzione

La verifica offline richiede Python standard e le dipendenze Node già usate
dal progetto; non richiede Rasterio, rete, chiavi API o un LLM:

```sh
python scripts/awash_irrigation.py verify
pnpm irrigation:verify
```

La raccolta iniziale richiede un ambiente Python separato e
`scripts/requirements-irrigation-capture.txt`. Lo script verifica che il server
supporti richieste per porzioni di file, poi legge piccole finestre dei GeoTIFF
FAO e blocca la generazione del file cloud durante l'acquisizione. Conserviamo
estratti nativi, metadati, unità e hash degli archivi: **non** una copia completa
o un hash calcolato sull'intero raster continentale.

L'API è documentata dalla [FAO](https://www.fao.org/in-action/remote-sensing-for-water-productivity/wapor-data-access/en).
Le condizioni dei dati rimangono quelle del fornitore, separate dalla licenza
del codice TerraVoce. La pioggia riporta `CC BY-NC-SA 4.0` nei metadati archiviati.
Il notebook accompagnatore esegue i controlli e distingue questa verifica
informatica da una validazione scientifica indipendente o da un test sul campo.
Vedi il [notebook eseguito](notebooks/awash-irrigation-game.ipynb): quattro celle
di codice eseguite in ordine con Python standard, con output salvati.
