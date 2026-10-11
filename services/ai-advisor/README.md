# TerraVoce AI advisor

Assistente locale in **modalità osservazione**. Legge uno snapshot firmato e un
assessment dell'Oracle, seleziona fatti e citazioni con un vero modello
linguistico e suggerisce `EXTRA_SAMPLING` oppure si astiene. Non presenta
proposte al bridge e non dispone di strumenti per votare, modificare policy,
gestire chiavi Ethereum o trasferire fondi.

## Percorso dei dati

1. L'operatore configura registrazioni dei sensori fidate e la policy TerraLex.
2. Il servizio verifica firme Ed25519, sequenze non duplicate, regione, metrica
   e unità. Ricalcola l'assessment con l'Oracle e ne confronta l'intero contenuto.
3. Verifica testo e hash contro il piccolo [corpus pubblico approvato](SOURCES.md),
   poi applica TerraLex al catalogo dimostrativo: `EXTRA_SAMPLING`, 40 USDC.
   Questo importo è una richiesta di verifica della policy, non una spesa.
4. Solo i fatti ricavati dall'assessment e le fonti approvate entrano nel prompt.
   Il modello sceglie l'azione, i fatti da citare e gli estratti in JSON.
5. Il validatore verifica schema rigoroso, ID assessment, supporto al calo,
   presenza dei limiti, fonte e citazione esatta. La spiegazione italiana viene
   composta da frasi controllate: il modello non introduce affermazioni libere.
6. Input e advisory sono conservati con nomi derivati dall'hash e creazione
   esclusiva. Gli hash rendono rilevabile una modifica; non sono un'attestazione
   blockchain né impediscono la cancellazione dei file sul computer.

Un formato valido può contenere una scelta errata: il servizio la rifiuta.
Policy negata, dati alterati o fonte non approvata portano ad astensione prima
dell'inferenza. Timeout, server indisponibile, risposta troncata e citazioni
inventate portano ad astensione dopo il tentativo. Non esiste un fallback che
fabbrica una raccomandazione al posto del modello.

## Avvio della demo

Requisiti: Node.js 24, pnpm 11.7.0 e Ollama locale. La prova verificata usa
Ollama **0.40.3**, due modelli Qwen3 Q4_K_M e GPU Quadro RTX 3000 con 6 GB.
Scaricare runtime e modelli richiede Internet; l'inferenza usa solo loopback.
Non sono necessarie API key. Non esiste un server HTTP dell'advisor: questa
versione espone `runAdvisor` come libreria e comandi batch locali.

Avviare Ollama in una prima shell PowerShell:

```powershell
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_CONTEXT_LENGTH = '4096'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_NUM_PARALLEL = '1'
ollama serve
```

Da una seconda shell, nella radice del repository:

```powershell
$env:OLLAMA_HOST = '127.0.0.1:11434'
ollama pull qwen3:1.7b
pnpm install --frozen-lockfile
pnpm build
$env:ADVISOR_MODEL = 'qwen3:1.7b'
$env:ADVISOR_MODEL_DIGEST = 'sha256:8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7'
pnpm --filter @terravoce/ai-advisor demo
```

Se il tag ora punta a un digest diverso, il servizio si astiene: occorre
valutare quella nuova versione prima di aggiornare il digest configurato.
`OLLAMA_URL` può cambiare la porta, ma deve usare `http://127.0.0.1` oppure
loopback IPv6. Redirect, credenziali nell'URL e host remoti vengono rifiutati.
Endpoint, tag e registrazioni sono configurazione dell'operatore, mai del LLM.

La demo genera osservazioni **sintetiche**, le invia alle API reali dell'Oracle
in memoria attraverso Fastify `inject`, e usa l'assessment restituito. Non
legge sensori sul territorio. Salva input e rapporto in `.runtime/demo` del
pacchetto. `ADVISOR_OUTPUT` consente di scegliere un'altra cartella.

Per riesaminare uno snapshot già salvato, mantenere separata la configurazione
dei sensori approvata dall'operatore. L'esempio pubblico contiene solo dati
sintetici e registrazioni di prova:

```powershell
pnpm --filter @terravoce/ai-advisor replay ../../docs/evidence/ai-input-example.json ../../docs/evidence/ai-fixture-config.json
```

Questo replay non è il replay scientifico su un dataset ambientale reale: è la
riesecuzione dell'advisor sullo stesso input congelato.

## Confronto dei modelli

```powershell
ollama pull qwen3:0.6b
ollama pull qwen3:1.7b
$env:ADVISOR_MODELS = 'qwen3:0.6b,qwen3:1.7b'
$env:ADVISOR_REPETITIONS = '2'
pnpm --filter @terravoce/ai-advisor benchmark
```

La suite pubblica in `src/fixtures.ts` contiene due cali dell'ossigeno, una serie
stabile con policy ammessa, una policy negata, un assessment alterato, un
documento ostile con hash non approvato, unità sbagliate e una firma falsa.
Tre casi per ripetizione arrivano al LLM; gli altri cinque misurano i controlli
deterministici. Non vanno sommati per dichiarare l'accuratezza del modello.

Il benchmark conserva input, registrazioni pubbliche, advisory, richieste e
risposte del modello. Riporta anche i fallimenti. Tra i modelli che superano
tutti i casi sceglie quello con latenza media minore, includendo il primo
caricamento. Non è un benchmark generale della comprensione ambientale.
Risultati osservati e limiti sono in [AI_VALIDATION.md](../../docs/AI_VALIDATION.md).

## Limiti e collegamento alla missione

- Solo `water.oxygen.mg_l` e `terravoce-linear-risk-v1` sono supportati. Le soglie
  e la confidence restano illustrative. Il replay su dati reali è ancora da fare.
- La fiducia nel registro sensori e nella policy è esterna al modello: una
  firma valida identifica il firmatario, non dimostra la verità della misura.
- Le due fonti descrivono il progetto; non costituiscono letteratura scientifica
  o retrieval generale. Il caso ostile verifica la chiusura del corpus contro
  documenti alterati, non una resistenza universale alla prompt injection.
- Il modello seleziona evidenze e una sola azione reversibile; il linguaggio
  finale è controllato. La gestione di spiegazioni libere richiederà altri
  criteri di verifica.
- Il rapporto non è ancora vincolato all'evidenza del bridge e non viene votato
  dalle quattro repliche. Quel collegamento richiede un protocollo separato.
- Il servizio non gestisce incarichi continui, identità civiche o reti
  geografiche. Questi incrementi devono conservare diritti di comunità e giovani,
  disponibilità delle evidenze e verificabilità degli interventi finanziati.

Riferimenti: [API Ollama](https://docs.ollama.com/api/chat),
[output strutturati](https://docs.ollama.com/capabilities/structured-outputs),
[modello Qwen3-1.7B](https://huggingface.co/Qwen/Qwen3-1.7B).
