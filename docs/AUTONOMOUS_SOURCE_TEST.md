# Primo test di scoperta autonoma e prove ambientali

TerraVoce ha trovato una stazione prima non collegata, acquisito le risposte
pubbliche USGS, riprodotto le osservazioni in processi locali separati e
registrato il loro impegno crittografico nel contratto `TerraEvidenceRegistry`
su una blockchain EVM locale. Il test dimostra anche due fallimenti importanti:
una fonte inizialmente falsa può essere perfettamente riproducibile, e un quorum
di identità autorizzate controllate dall'attaccante può accettare prove false.

Questo è un primo componente della missione originale: evidenze ambientali
tracciabili, coordinamento distribuito e potere delle comunità. Una registrazione
di dati non è un miglioramento ecologico, un diritto di spesa o una previsione
validata. I modelli Willamette e il caso Awash non sono modificati.

## Passo 1: le regole sono state fissate prima della ricerca

Il commit `8de9b64af94907b5de0fc6a303fa2972a025308a` contiene il
[protocollo](datasets/autonomous-source/protocol.json), prima dell'acquisizione.
Il programma riceve il territorio, una grandezza e un catalogo iniziale:

- rettangolo geografico `[-123.2, 44.5, -122.4, 45.7]` e prefisso idrologico
  `170900`, nel bacino del Willamette;
- ossigeno disciolto, parametro USGS `00300`, unità `mg/L`;
- osservazioni dal 1 luglio 2025 alle 00:00 UTC al 2 luglio alle 00:00 UTC;
- la stazione già collegata `USGS-14211720` viene esclusa;
- i candidati ammissibili sono ordinati per stazione e serie; viene scelto il
  primo con metadati coerenti e almeno due osservazioni approvate senza qualificatori.

L'identificativo della nuova stazione non compare nelle regole di selezione.
L'ordine è una regola riproducibile di questo esperimento; non significa che la
stazione sia la più rappresentativa o la più affidabile del territorio.
La finestra storica verifica il percorso informatico, senza addestrare modelli.

## Passo 2: il programma trova la stazione

Interrogando il catalogo, il programma ha ricevuto 34 serie e identificato
16 candidati ammissibili. Ha selezionato autonomamente:

| Campo | Risultato |
| --- | --- |
| Stazione | `USGS-14182500` |
| Nome della fonte | LITTLE NORTH SANTIAM RIVER NEAR MEHAMA, OR |
| Serie | `3f0bf45ec4454119a93f0aa935c88336` |
| Unità idrologica | `170900050505` |
| Coordinate | longitudine -122.578973849527, latitudine 44.7915108355795 |
| Osservazioni ricevute e ammissibili | 97; nessuna esclusione in questo campione |
| Richieste e corpi acquisiti | 3 richieste; 138.252 byte di risposta |

La novità è una **stazione all'interno di un pubblicatore già configurato**.
Non è la scoperta di un ente indipendente da USGS o di un dispositivo privato.
Il limite è importante: altre stazioni della stessa agenzia non rappresentano
automaticamente altre fonti indipendenti.

## Passo 3: vengono conservati dati e provenienza

Sono conservati il catalogo, i metadati della stazione e tutte le osservazioni
ricevute. Il [manifesto](datasets/autonomous-source/manifest.json) registra URL,
momento locale di recupero, byte e SHA-256 di ogni risposta. La data del recupero
è un'informazione del raccoglitore; non è una firma dell'orologio del sensore.

Il programma verifica identità della stazione e della serie, territorio, unità,
finestra temporale, duplicati, paginazione e campi di qualità. Le osservazioni
provvisorie, qualificate o mancanti vengono escluse con il motivo conservato.
Un valore mancante non diventa zero. Non viene inventata una cadenza attesa dal
solo numero di righe: eventuali omissioni già presenti nella fonte richiedono
informazioni esterne per essere dimostrate.

Sono ammessi soltanto gli endpoint HTTPS USGS previsti, senza reindirizzamenti.
Ogni risposta ha un limite di byte e tempo; ricerca e tentativi hanno un limite
di pagine/candidati. Un catalogo incompleto, un errore di rete o l'assenza di una
fonte ammissibile fermano il percorso, senza produrre un giudizio di buona salute.
Non c'è un LLM che interpreta istruzioni inserite nei metadati.

HTTPS identifica l'endpoint del pubblicatore nel modello di fiducia adottato.
Queste risposte **non sono firmate dal sensore USGS**. Una eventuale firma del
raccoglitore attesterebbe ciò che ha ricevuto, non la calibrazione sul campo.

## Passo 4: viene sigillato il risultato

Il commit `655c694` conserva acquisizione, manifesto e
[sigillo](evidence/autonomous-source/seal.json). La verifica offline riceve
l'impegno atteso da una fonte esterna al file modificabile: nella CLI è il
sigillo della revisione Git; nei processi di verifica è un argomento separato.
Se l'attaccante controlla anche quel riferimento iniziale, manca la protezione
contro una riscrittura coerente dell'intero archivio.

Impegno dell'evidenza:

```text
0x51eb495031dc75a12e4de5d1fe69165aaaf900b30d2d1d019ea88a0af21ba5df
```

Esso lega protocollo, manifesto, selezione, osservazioni normalizzate e limiti
delle affermazioni. I metadati registrati in blockchain legano anche le impronte
del codice di verifica e del contratto. I dati completi restano fuori dalla
blockchain; questo campione usa un impegno SHA-256 dell'intero lotto, senza
implementare ancora prove Merkle per singole osservazioni.

## Passo 5: tre processi verificano, poi il contratto registra

Il test avvia tre processi Node distinti che leggono l'archivio e ricostruiscono
la stessa evidenza. Quattro indirizzi sono autorizzati nel registro; il quorum
è tre. La quarta identità non partecipa alla registrazione autentica.
L'identità amministrativa viene rimossa dal ruolo di attestatore ordinario.

Il contratto è quello esistente, senza modifiche Solidity. Riceve l'impegno,
territorio, metadati, ultima data osservata, tipo di evidenza e URI. Le tre
attestazioni producono transazioni e stato `accepted = true`.
Il [resoconto della catena](evidence/autonomous-source/chain-run.json) conserva
indirizzi, hash delle transazioni, blocchi, risultati e scenari avversari.
La verifica offline controlla anche il resoconto conservato: deve corrispondere
alla revisione Git, al lotto riprodotto, all'impronta dei metadati e alle impronte
dei file di verifica. È una verifica di coerenza delle prove conservate; non
interroga un explorer né dimostra da sola le ricevute di una rete pubblica.

È una vera esecuzione del contratto su una EVM locale **effimera**. Lo stato della
catena termina con il comando; gli hash non sono link a un explorer pubblico.
Le ricevute conservate sono un resoconto del test, non una prova di consenso
pubblico indipendente. Tutte le identità restano controllate dallo stesso host.
Il cluster ABCI/Open Autonomy non viene lanciato da questo nuovo test; Docker
non era disponibile durante la prova locale. Non è una prova di resistenza
di operatori distribuiti in paesi diversi.

## Passo 6: simuliamo uno Stato che cerca una narrazione favorevole

Gli attacchi si svolgono su copie locali. Non alteriamo il servizio USGS e non
attribuiamo a USGS alcun comportamento malevolo.

| Capacità dell'attaccante | Cosa abbiamo provato | Risultato |
| --- | --- | --- |
| Modificare una misura dopo la raccolta | Sostituzione di un valore con 9,9 mg/L | L'impronta della risposta non coincide: verifica rifiutata |
| Riscrivere dati e relativo manifesto | Ricalcolo degli hash locali dei dati falsi | Il riferimento esterno originale non coincide: verifica rifiutata |
| Sostituire unità, serie, date o URL | Test negativi del raccoglitore e dell'archivio | Verifica rifiutata |
| Essere il primo attestatore di un impegno noto | Prima attestazione con metadati sbagliati, poi attestazione onesta | Il registro blocca i metadati corretti: rischio di censura dimostrato anche con una sola identità autorizzata |
| Pubblicare falsità coerenti fin dall'inizio | Tutte le 97 misure impostate a 9,9 con un nuovo impegno iniziale | Riproducibilità accettata; verità fisica non dimostrata |
| Votare molte volte con la stessa identità | Doppia attestazione | Contratto rifiuta il duplicato |
| Usare un'identità non autorizzata | Tentativo di attestazione esterna | Contratto rifiuta il ruolo mancante |
| Controllare soltanto due attestatori | Due attestazioni alla prova falsa | Il quorum di tre non viene raggiunto |
| Rendere indisponibili due attestatori | Due attestazioni autentiche in un nuovo registro | Il contratto rimane a due, evidenza non accettata |
| Controllare tre attestatori autorizzati | Terza attestazione alla prova falsa | Il contratto accetta: fallimento dimostrato della veridicità sotto cattura del quorum |
| Catturare l'amministratore delle iscrizioni | Aggiunta di tre nuove identità controllate | Il contratto accetta la prova falsa: l'ammissione degli operatori è una radice di fiducia |
| Revocare le chiavi dopo un'accettazione falsa | Revoca dei tre ruoli | L'accettazione già registrata rimane; serve una contestazione/correzione esplicita |
| Censurare la fonte | Errore simulato di acquisizione | Il percorso si ferma; non trasforma il silenzio in ambiente sano |

Una catena può rendere riconoscibile una modifica successiva a un dato
conservato. Non garantisce che il dato iniziale fosse vero o completo.
Anche un attaccante senza tre chiavi può ingannare verificatori onesti se tutti
dipendono dalla stessa fonte iniziale falsificata. Il risultato "due chiavi
non bastano" riguarda due attestazioni isolate, non una garanzia universale
contro due nodi bizantini o contro la falsificazione del pubblicatore.
La prova con una quarta identità assente non dimostra la resistenza a una
quarta identità che agisce malevolmente per prima: il registro attuale conserva
i metadati della prima attestazione e può bloccare quelle corrette successive.

## Passo 7: le conseguenze per TerraVoce

I risultati suggeriscono quattro requisiti prima di una rete reale:

1. Operatori e chiavi amministrative sotto controlli effettivamente separati.
   Quattro indirizzi della stessa organizzazione non stabiliscono indipendenza.
2. Ammissione degli operatori governata e verificabile. Denaro o quantità di
   identità non devono comprare potere sulle decisioni ambientali.
3. Confronti tra strumenti/pubblicatori con provenienza e dipendenze note;
   fonti indipendenti possono ridurre il rischio comune, senza garantirne
   automaticamente l'assenza. Misure di ossigeno non diventano verificate
   semplicemente perché un satellite osserva temperatura o vegetazione.
4. Copie indipendenti delle evidenze, gestione delle revisioni, contestazioni e
   conservazione dei dati mancanti/indisponibili come tali.

La prima correzione tecnica da discutere riguarda il blocco dei metadati da
parte del primo attestatore: un futuro registro dovrà legare crittograficamente
l'identificativo a tutta la busta dei metadati, o finalizzarla soltanto con un
quorum coerente, senza assegnare quell'autorità al primo nodo. Questo test
conserva il contratto originale e ne rende riproducibile il limite.

Questi requisiti non sono già implementati da questo test. Non introduciamo
un punteggio arbitrario che trasformi una misura plausibile in verità.
Il registro non recupera i file né esamina la realtà fisica: controlla ruoli,
coerenza dei metadati e quorum. L'accettazione di un lotto non attiva il ponte
delle azioni, TerraLex, la tesoreria o una decisione delle comunità.

## Passo 8: ripetere e verificare

Con le dipendenze bloccate e Node.js 24, dalla radice del repository:

```sh
pnpm install --frozen-lockfile
pnpm build
pnpm source:verify
pnpm source:e2e
```

Non servono API key, wallet reali, Docker o un LLM per riprodurre l'esperimento.
Il comando `source:e2e` usa l'archivio, senza richieste ambientali nuove, e scrive
`outputs/autonomous-source/chain-run.json`. La CI ripete entrambe le verifiche
offline. Il report di ogni dimostrazione locale viene sostituito; il resoconto
pubblicato in `docs/evidence` è una copia conservata di una specifica esecuzione.

La cattura iniziale usa `pnpm source:capture`; richiede che il protocollo sia
già in Git e rifiuta di sovrascrivere un'acquisizione esistente. Questo è un
singolo ciclo avviato da comando. Un servizio ricorrente con code, recupero dopo
interruzioni, nuove finestre e gestione delle revisioni rimane lavoro successivo.
Non eliminare l'acquisizione conservata per rilanciare la demo.

## Fonti e attribuzione

- [Documentazione ufficiale delle API USGS](https://api.waterdata.usgs.gov/docs/).
- [Migrazione e significato delle misure continue](https://api.waterdata.usgs.gov/docs/ogcapi/migration/).
- [Stazione trovata dal programma](https://waterdata.usgs.gov/monitoring-location/USGS-14182500/).
- [Metadati delle serie](https://api.waterdata.usgs.gov/ogcapi/v1/collections/time-series-metadata/queryables?f=json).

Dati: U.S. Geological Survey, Water Data for the Nation; risposte acquisite il
12 ottobre 2026, timestamp e URL esatti nel manifesto. Sono dati pubblicati e
rivisti dalla fonte; non ricostruiscono necessariamente ciò che era disponibile
in tempo reale nel luglio 2025. Nessuna validazione scientifica indipendente,
misura fisica nuova, miglioramento ecologico o trasferimento di fondi è avvenuto.
