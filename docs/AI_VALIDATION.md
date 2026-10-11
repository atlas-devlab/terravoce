# Verifica del primo AI advisor

Prova eseguita l'11 ottobre 2026. L'advisor usa un vero LLM locale, ma le
osservazioni sono sintetiche e l'analisi numerica resta dimostrativa. L'advisory
non è ancora collegato a Open Autonomy o alle proposte del Governor.

## Ambiente misurato

- Windows, Node.js 24.18.0, pnpm 11.7.0 e TypeScript 5.9.3.
- 64 GB di RAM e NVIDIA Quadro RTX 3000 con 6144 MiB di VRAM.
- Runtime portabile Ollama 0.40.3; archivio ufficiale Windows SHA-256
  `e5ecff02dfc7cae8ddf6d6b7a7ac5f727ffeedf4491f44ae75ff5b0820dbbbd5`.
- Inferenza locale con `think=false`, temperatura 0, seed 42, contesto 4096
  e massimo 512 token di risposta. Modelli Q4_K_M. Il modello 1.7B è stato
  osservato interamente caricato in VRAM, con circa 1,7 GB occupati nel runtime.

## Confronto osservato

Otto casi pubblici, due ripetizioni per modello. Due serie in calo e una serie
stabile arrivano al LLM; cinque casi controllano rifiuti prima dell'inferenza.

| Modello | Casi dell'applicazione superati | Casi con inferenza superati | Latenza media inferenza | Massimo |
| --- | --- | --- | --- | --- |
| Qwen3 0.6B | 10/16 | 0/6 | 2076 ms | 4898 ms |
| Qwen3 1.7B | 16/16 | 6/6 | 2824 ms | 5660 ms |

Il digest approvato per il primo advisor è
`sha256:8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7`.
Quello del modello 0.6B è
`sha256:7df6b6e09427a769808717c0a93cadc4ae99ed4eb8bf5ca557c90846becea435`.

Il modello 0.6B si astiene nei casi di calo e seleziona un fatto non presente
nel caso stabile. Il validatore rifiuta quest'ultimo output. Il modello 1.7B
seleziona il campionamento nei due cali e si astiene sulla serie stabile, con
citazioni esatte e limiti espliciti in tutte le sei inferenze accettate.

La latenza include metadati, inferenza, salvataggio della traccia e il primo
caricamento del modello. Le ripetizioni hanno stesso seed: non sono sei
osservazioni statisticamente indipendenti. La suite è stata usata nello sviluppo
del protocollo e non costituisce un insieme di test scientifico tenuto separato.

Rapporto completo: [benchmark v2](evidence/ai-benchmark-v2.json).
La prima versione del prompt/schema aveva campi ridondanti e produceva
contraddizioni tra scelta e motivazione con entrambi i modelli. Tutti i sei casi
di inferenza per modello fallivano e il sistema si asteneva. Quel risultato è
conservato nel [benchmark iniziale](evidence/ai-benchmark-initial.json). Lo schema
v2 usa una sola scelta di azione e rende la spiegazione dai fatti verificati.

## Verifiche applicative

Il workspace supera build e controllo TypeScript. Sono verificati schema
rigoroso, firme e snapshot, policy negata, citazioni inventate, documenti
alterati, unità sbagliate, replay, tentativi di cambiare policy, timeout anche
con provider che ignora la cancellazione, output troncato, risposta troppo
grande, redirect, cambio del modello e digest non approvato. La scrittura
rifiuta la sostituzione di un artefatto già alterato.

Il nuovo modulo ha 26 test con provider etichettati come fixture. Le chiamate
HTTP dei test usano server locali fittizi. Le prove LLM riportate sopra e la
demo usano invece il runtime reale. La CI ordinaria esegue i test del modulo,
senza scaricare pesi e senza presentare una fixture come inferenza reale.

Controlli complessivi passati localmente: build e check del workspace,
47 test TypeScript/Solidity (inclusi i 26 nuovi) e sette test Python del bridge.

La demo registra dodici osservazioni sintetiche attraverso le API dell'Oracle
in memoria, ottiene un assessment e genera un advisory citato con Qwen3 1.7B.
Sono disponibili uno [snapshot congelato](evidence/ai-input-example.json) e la
[configurazione pubblica dei sensori di prova](evidence/ai-fixture-config.json)
per ripetere il percorso. Le chiavi private di prova non vengono conservate.
Un [advisory reale di esempio](evidence/ai-advisory-example.json) conserva anche
digest del modello, versione del runtime e hash dell'input e del rapporto.

## Limiti della conclusione

Questa verifica dimostra il funzionamento locale di un advisor limitato e dei
suoi controlli. Non dimostra accuratezza ambientale su dati reali, qualità della
generazione libera in italiano, retrieval scientifico generale, resistenza a
ogni prompt injection, disponibilità geografica o autorizzazione di fondi reali.
Il caso di documento ostile viene rifiutato tramite il corpus fissato e i suoi
hash prima di entrare nel prompt. Le citazioni sono vincoli del progetto, non
prove scientifiche di un fenomeno ambientale.

Il prossimo collegamento deve rendere disponibili evidenze e advisory ai nodi
e legarne provenienza e hash al protocollo, conservando contestazione pubblica,
diritti civici e limiti della tesoreria. Il replay numerico su dati reali resta
un lavoro distinto, richiesto prima di attribuire validità scientifica al modello.

Comandi: [guida dell'advisor](../services/ai-advisor/README.md).
