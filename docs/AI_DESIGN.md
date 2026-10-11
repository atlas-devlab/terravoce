# AI per TerraVoce: decisione tecnica e prossimo incremento

Proposta di architettura aggiornata l'11 ottobre 2026. Questo documento descrive
il lavoro da implementare; non annuncia un modello AI già integrato o validato.

La missione resta il coordinamento ambientale globale: analisi distribuita,
evidenze pubbliche resilienti, finanziamento di interventi verificabili e diritti
decisionali delle comunità coinvolte e dei giovani. La prova sull'ossigeno è il
primo banco di verifica di componenti riutilizzabili, non il limite del progetto.

## Stato verificato

- L'Oracle usa `terravoce-linear-risk-v1`: regressione lineare, anomalie e soglie
  illustrative. Il campo `confidence` è un'euristica, non una probabilità calibrata.
- Azione, importo e asset arrivano nella richiesta all'Oracle. Il codice attuale
  valuta quella richiesta con TerraLex; non sceglie autonomamente l'intervento.
- Open Autonomy certifica un job immutabile attraverso tre repliche su quattro.
  Il bridge può presentare una proposta reversibile al Governor.
- Non sono presenti un LLM, addestramento ambientale, retrieval di documenti,
  validazione su dati reali o esecuzione AI continua. La prova usa un solo host.

## Due ruoli, un percorso verificabile

| Componente | Compito previsto | Controllo |
| --- | --- | --- |
| Analisi numerica | Misurare anomalie, prevedere una metrica e quantificare l'incertezza | Replay cronologico e confronto con una baseline |
| Assistente linguistico | Spiegare le evidenze e suggerire un'azione dal catalogo autorizzato | Output strutturato, fonti verificabili e possibilità di astensione |
| TerraLex e validatori | Verificare dati, schema, policy, destinatario, budget e reversibilità | Controlli deterministici prima del quorum |
| Open Autonomy e Governor | Certificare una proposta e governare l'intervento | Quorum, contestazione, camere civiche e limiti della tesoreria |

L'inferenza rimane fuori dalla blockchain. Il LLM non determina valori misurati,
probabilità scientifiche, chiavi degli operatori o autorizzazioni di spesa.
Una previsione numerica e una spiegazione linguistica hanno versioni e criteri
di qualità distinti. Le repliche verificano il rispetto dei vincoli; il loro
accordo non dimostra da solo la correttezza scientifica delle conclusioni.

## Scelta per il primo assistente

Proponiamo un servizio separato `services/ai-advisor`, in TypeScript, con un
adapter per **Ollama locale** e output JSON vincolato a schema. Il modello di
pesi aperti sarà scelto con un benchmark sull'hardware disponibile, verificando
licenza, memoria, qualità in italiano e latenza; non fissiamo oggi un modello
senza averlo misurato. L'interfaccia consentirà di cambiare backend senza
modificare Governor o bridge.

Input: snapshot delle osservazioni verificate, assessment, catalogo di azioni,
policy e fonti pubbliche approvate. Output proposto: `advisory-v1` con riferimento
all'assessment, azione suggerita o astensione, motivazione, limiti, riferimenti
alle fonti e provenienza di modello, prompt e runtime. È uno schema futuro,
distinto dagli schemi `Assessment` e `ActionDraft` esistenti.

Gli importi finanziabili e i destinatari devono derivare da un catalogo e da
regole approvate. Eventuali stime del LLM sono indicazioni da verificare. Il
modello non può creare nuove azioni autorizzate o aggiornare TerraLex.

I documenti consultati sono dati, non istruzioni: retrieval inizialmente su un
piccolo insieme di fonti pubbliche autorizzate, con hash e riferimenti a passaggi
precisi. Nessun accesso a libri personali o documenti privati è previsto.
JSON valido non significa contenuto vero: citazioni inesistenti, unità sbagliate
o conclusioni prive di supporto devono portare a rifiuto o astensione.

## Come evitare divergenze tra repliche

Non chiediamo a quattro LLM di produrre lo stesso testo. Il candidato viene
generato una volta, salvato come artefatto immutabile e distribuito ai validatori.
Ogni replica ricalcola l'assessment sullo stesso snapshot, verifica riferimenti
e vincoli, poi firma lo stesso digest dell'azione ammessa. Anche temperatura zero
non è una garanzia di identità dell'inferenza tra hardware diversi.

Prima di ammettere questo candidato al bridge serve estendere il protocollo:
provenienza e hash dell'advisory devono essere collegati all'evidenza certificata,
e l'artefatto deve restare disponibile agli operatori e alla comunità. Oggi la
firma lega la stringa `metadataURI`, ma non verifica il contenuto remoto. Un URI
ordinario non basta a rendere immutabile un rapporto. Il manifest approvato
rimane il confine di fiducia; non sarà riscritto automaticamente dal LLM.

## Primo incremento e criterio di completamento

Implementare `ai-advisor` **in modalità osservazione**, senza inoltro automatico
di proposte: legge un assessment, produce una spiegazione citata e suggerisce
`EXTRA_SAMPLING` dal catalogo oppure si astiene. Non servono fondi reali.

L'incremento è completo quando:

1. Una demo locale usa un vero modello, registra la provenienza e conserva
   input, advisory e hash; le fixture sono etichettate come tali.
2. Schema errato, timeout, modello indisponibile, fonte inventata, tentativo di
   cambiare policy e istruzioni ostili in un documento producono astensione o
   rifiuto, senza degradare i controlli dell'Oracle.
3. Una piccola suite pubblica di casi con risposte attese misura correttezza dei
   riferimenti, scelta dell'azione, astensione e latenza. Il rapporto elenca
   anche gli errori; la selezione del modello deriva da questi risultati.
4. La spiegazione mostra chiaramente che rischio e `confidence` correnti sono
   dimostrativi. Nessuna spiegazione converte queste euristiche in certezze.

In parallelo al lavoro linguistico, il replay di un dataset aperto resta la
validazione dell'analisi numerica: split temporali, controllo dei dati mancanti,
MAE/RMSE contro previsione basata sull'ultimo valore e risultati per orizzonte.
Un modello appreso entra nell'Oracle solo dopo una valutazione su periodi non
usati per addestrarlo. Soglie operative richiedono revisione scientifica e civica.

Solo dopo queste verifiche collegheremo advisory, archivio replicato delle
evidenze e consenso. Ulteriori metriche e territori useranno cataloghi e policy
specifici, senza perdere la tracciabilità degli interventi finanziati.

## Riferimenti tecnici primari

- [Ollama: structured outputs](https://docs.ollama.com/capabilities/structured-outputs)
  documenta JSON Schema e validazione lato applicazione. Lo adottiamo come
  meccanismo di formato, non come validazione scientifica.
- [scikit-learn: TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)
  documenta la separazione cronologica; intervalli irregolari richiedono gestione
  esplicita prima di confrontare le finestre.
- [Olas: agent services](https://stack.olas.network/open-autonomy/get_started/what_is_an_agent_service/)
  descrive servizi fuori dalla blockchain con repliche e consenso.

Per il risultato già ottenuto vedere [la verifica del bridge](AUTONOMY_VALIDATION.md).
