# Correzione del blocco causato dal primo attestatore

[English version for international contributors](FIRST_ATTESTOR_FIX_EN.md).

Il contratto di TerraVoce ora permette a tre attestatori concordi di registrare
la propria prova anche quando una quarta identità autorizzata arriva per prima
con metadati diversi. È una correzione del registro delle evidenze, verificata
sulla EVM locale; non è una dimostrazione di resistenza generale a uno Stato.

## 1. Abbiamo prima riprodotto il problema

Nella revisione `9b6ced1add86e34aa08480d2f1c8d135ba7deb5b`, il primo voto fissava
territorio, hash dei metadati, data osservata, tipo di evidenza e URI dell'archivio
per un certo `evidenceHash`. Un voto successivo con un campo diverso veniva
rifiutato con `EvidenceMismatch`, anche prima del quorum. Una sola chiave
autorizzata poteva quindi bloccare la pubblicazione corretta.

Il primo test di regressione è stato eseguito sul contratto originale e ha
fallito proprio con `EvidenceMismatch`. Il controllo ordinario con tre identità
concordi riusciva. Il
[resoconto precedente](evidence/autonomous-source/chain-run-before-first-attestor-fix.json)
conserva il comportamento iniziale; non è il resoconto del contratto corretto.

## 2. Ogni versione completa raccoglie i propri voti

In `TerraEvidenceRegistry.sol`, ciascuna busta dei metadati è ora una candidata
separata. L'impegno SHA-256 delle 97 osservazioni USGS resta identico; non viene
sostituito dall'identificativo della candidata.

```text
Lotto ambientale: stessa impronta dei dati
  versione dell'attaccante -> 1 voto -> non accettata
  versione concordata      -> 3 voti -> accettata
```

L'identificativo della candidata è:

```text
keccak256(abi.encode(
  keccak256("TerraVoce.EvidenceCandidate.v1"),
  chainId, indirizzoDelRegistro, evidenceHash,
  regionId, metadataHash, observedAt, kind, uri
))
```

La codifica ABI comprende tutti i campi, compresi i byte UTF-8 dell'URI, e
lega la candidata alla versione della regola, alla rete e a quel registro.
Non usa una concatenazione ambigua di stringhe. Due URI testualmente diversi
restano candidati diversi: i verificatori devono concordare sulla stessa busta.

## 3. Un'identità conserva un solo voto per lotto

`hasAttested[evidenceHash][address]` resta globale fra le candidate. Un indirizzo
non può votare una versione e poi un'altra, né moltiplicare i voti ripetendo
la transazione. Revocare e riattribuire il ruolo non azzera questo vincolo.
Un'altra impronta di dati rappresenta invece un altro lotto.

Ruolo richiesto, controlli su campi non vuoti, soglia configurata e firma delle
transazioni restano necessari. Il contratto non aumenta il peso di un voto in
base al denaro o al possesso di token.

## 4. Il risultato finale è una sola busta coerente

Al quorum, il registro copia insieme territorio, metadati, data, tipo, URI e
conteggio della candidata vincente. Non somma voti di buste diverse.
Una volta accettata, la busta non può essere sostituita da una candidata diversa.
Ulteriori identità che non hanno già votato possono attestare la stessa busta,
come nel comportamento precedente.

L'interfaccia usata da TerraAct, `isAcceptedForRegion`, non cambia. Il getter
`evidence(hash)` mantiene la prima candidata visibile durante l'attesa:
è **provvisoria**, con `accepted = false`, e non autorizza azioni. Quando vince
un'altra candidata, viene sostituita integralmente. Per leggere tutti i
conteggi si usano `candidate` e l'evento `EvidenceCandidateAttested`.
`acceptedCandidateId` identifica la vincitrice; prima del quorum è zero.
L'evento precedente `EvidenceAttested` rimane disponibile, ma il suo conteggio
è quello della candidata votata, non il totale del lotto.

La revisione ha inoltre rilevato che copiare la prima busta nel risultato
provvisorio faceva pagare agli onesti la riscrittura di un URI malevolo lungo.
Un test ha riprodotto l'aumento del costo di finalizzazione da 141.150 unità di
gas con 32 byte a 1.354.685 con 10.000 byte. Il getter provvisorio ora legge la
candidata senza copiarla nello spazio del risultato finale: quest'ultimo riceve
soltanto la busta vincente. Non imponiamo un nuovo limite arbitrario agli URI;
il nodo malevolo paga il proprio inserimento, ma non quel costo aggiuntivo
di riscrittura per gli onesti.
Con la correzione, lo stesso test usa 231.918 unità di gas in entrambi i casi.
La scrittura finale separata costa di più nel caso dell'URI corto, ma rende
questo costo indipendente dalla lunghezza dell'URI inserito dall'attaccante.
Questi numeri riguardano questa configurazione di test, non una tariffa in euro
o una previsione del costo di una rete pubblica.

## 5. Abbiamo ripetuto l'attacco sulle 97 osservazioni reali

Il test `source:e2e` riusa l'acquisizione USGS originale, senza nuove richieste
ambientali. Tre processi Node separati verificano il lotto. Nel nuovo registro
locale, la quarta identità firma per prima una busta con territorio, metadati,
data, tipo e URI alterati. Le altre tre identità attestano la busta riprodotta.

Il [nuovo resoconto](evidence/autonomous-source/chain-run.json) conserva la
transazione malevola, le tre transazioni oneste, identificativi delle candidate
e risultati delle verifiche sullo stato del contratto:

| Controllo | Esito atteso e verificato |
| --- | --- |
| Prima candidata malevola | Un voto, non accettata |
| Primo e secondo voto onesto | Nessuna accettazione anticipata |
| Terzo voto onesto | Busta onesta accettata con tre voti |
| Tutti i campi del risultato | Coincidono con la busta onesta |
| Territorio inventato dall'attaccante | Non risulta accettato |
| Secondo voto della stessa identità malevola | Rifiutato come duplicato |
| Sostituzione dopo la finalizzazione | Rifiutata |

È una prova con una **identità attestatrice malevola**. Il programma di test
controlla tutte le chiavi e firma le transazioni; i processi di verifica non
sono operatori indipendenti e non custodiscono autonomamente quelle chiavi.
Non è stato avviato un cluster ABCI/Open Autonomy o un nodo remoto compromesso.
La rete EVM termina con il comando; le ricevute conservate non sono una prova
di consenso pubblico verificata tramite explorer.

## 6. Abbiamo cercato varianti e regressioni

Il file `packages/contracts/test/TerraEvidenceRegistry.ts` aggiunge 15 test:
copre separatamente ciascuno dei cinque campi alterabili, tutte le 24 sequenze
di arrivo con una identità malevola e tre oneste, voti divisi fra candidate,
duplicati anche dopo riattribuzione del ruolo, autorizzazione, input invalidi,
codifica completa, isolamento fra registri e immutabilità del risultato.
Un test aggiuntivo confronta il costo della finalizzazione onesta dopo URI
malevoli di 32 e 10.000 byte, per impedire la regressione appena descritta.
Le 24 sequenze sono casi eseguiti sul contratto Solidity, all'interno di un test;
non sono 24 operatori né una probabilità di attacco.

Il modello Python continua a confrontare 120 sequenze astratte con la regola
precedente. È una spiegazione distinta dai test EVM, non una prova di consenso
distribuito. I controlli esistenti su governance, tesoreria, escrow e casi
ambientali restano parte della verifica di compatibilità.

## 7. Abbiamo aggiornato le prove senza cancellare la storia

Il resoconto corrente passa alla versione `autonomous-source-local-chain-test-v2`.
Il verificatore offline controlla anche l'esito della correzione e le impronte
di 13 file: aggiunge il programma della dimostrazione alla lista precedente.
Il nuovo hash dei metadati riflette il nuovo codice; l'impronta del lotto
ambientale e le misure originali non cambiano.

Il resoconto è vincolato alla revisione Git. Dopo una modifica del contratto,
`source:verify` deve rifiutare il vecchio resoconto: occorre eseguire la nuova
prova, conservarla e fissarla in Git. Non abbiamo disattivato questa protezione
per fare passare i controlli. La verifica offline controlla coerenza interna e
impronte; non riaccede alla blockchain effimera ormai terminata.

## 8. Cosa resta fuori dalla correzione

- Tre identità catturate possono ancora attestare una falsità; l'amministratore
  può ancora aggiungere operatori. Il contratto non impone una popolazione fissa
  di quattro operatori, e non dimostra la loro indipendenza.
- Una fonte iniziale falsa o incompleta può ingannare tutte le repliche oneste.
  Una maggioranza concorde non dimostra calibrazione o verità ambientale.
- Un malevolo e un onesto assente lasciano solo due voti onesti: la soglia di tre
  impedisce l'accettazione. Non abbiamo abbassato il quorum per simulare progresso.
- Una revoca non cancella automaticamente prove già accettate. Contestazioni,
  correzioni e conservazione distribuita restano lavoro successivo.
- Il contratto non è aggiornabile tramite proxy e il Governor conserva un
  riferimento immutabile al registro. Questa patch vale per nuove istanze;
  non ripara automaticamente un contratto già distribuito. Una migrazione reale
  richiederebbe un piano separato e la verifica delle autorizzazioni.

Questa modifica serve alla missione originale di TerraVoce: ridurre il potere
di una singola identità di censurare le prove ambientali. Non modifica il modello
Willamette, il caso Awash, TerraLex, le camere civiche o i limiti della tesoreria.
Non attiva un intervento, un LLM, una spesa reale o una pubblicazione su rete pubblica.

## Riproduzione

Dalla radice, con Node.js 24, pnpm 11.7.0 e le dipendenze bloccate:

```sh
pnpm build
pnpm check
pnpm contracts:test
pnpm source:verify
pnpm source:e2e
pnpm e2e
pnpm case:e2e
python scripts/audit_autonomous_source.py
python scripts/explore_evidence_quorum.py
```

`source:verify` richiede il resoconto aggiornato già presente in Git. Le prove
usano archivi conservati e identità locali di test; non richiedono wallet reali,
nuove credenziali, Docker o modifiche al servizio USGS.
