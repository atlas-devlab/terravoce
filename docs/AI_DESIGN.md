# AI per TerraVoce: decisione tecnica e prossimo incremento

Architettura aggiornata l'11 ottobre 2026. Il primo advisor in modalità
osservazione è implementato e provato con un modello locale; la validazione
numerica su dati reali comprende un primo replay e un esperimento multivariabile
in osservazione. La validazione scientifica indipendente e il collegamento
dell'advisory linguistico al bridge restano da implementare.

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
- `services/ai-advisor` usa un LLM locale per selezionare fatti e citazioni da
  un corpus pubblico fissato nel codice. Produce spiegazioni controllate e
  suggerimenti senza inoltro alla blockchain. Non sono presenti addestramento
  ambientale, retrieval generale o esecuzione continua dell'advisor. Il modulo
  numerico separato `environmental-case` usa dati reali USGS; il replay mostra
  limiti della regressione attuale e il nuovo esperimento rimane in osservazione.

Il [test multivariabile sul Willamette](WILLAMETTE_FORECAST_EXPERIMENT.md) confronta
ossigeno, temperatura e portata con split temporali. Il piccolo miglioramento
estivo non si trasferisce alle finestre autunnale e invernale dichiarate prima
del download: il modello congelato è molto peggiore della persistenza e la
copertura invernale dell'intervallo è zero. Un secondo calcolo in Python verifica
la riproducibilità numerica, non l'efficacia scientifica. Il modello resta un
esperimento isolato; non sostituisce l'Oracle e non modifica i finanziamenti.

In questi test "modello" indica la regressione numerica, non il LLM. Il LLM
locale non è stato chiamato, riaddestrato o cambiato durante l'esperimento.

Il successivo [controllo dei dati di quattro stagioni](WILLAMETTE_TRAINING_READINESS.md)
prepara la nuova prova a un'ora. Espone anche gli orari completamente mancanti:
2559 coppie sono disponibili, con copertura autunnale della griglia del 90.15%.
Non introduce un nuovo fit, una previsione migliore o un collegamento dell'LLM.

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

Il servizio separato `services/ai-advisor`, in TypeScript, usa un adapter per
**Ollama locale** e output JSON vincolato a schema. Il primo confronto ha scelto
Qwen3 1.7B Q4_K_M per il superamento dei casi sintetici e una latenza media di
circa 2,8 secondi. L'output finale italiano è composto da frasi controllate: non
abbiamo validato la qualità della generazione libera in italiano.
L'interfaccia consente futuri backend senza modificare Governor o bridge.

Input: snapshot delle osservazioni verificate, assessment, catalogo di azioni,
policy e fonti pubbliche approvate. Output implementato: `advisory-v1` con riferimento
all'assessment, azione suggerita o astensione, motivazione, limiti, riferimenti
alle fonti e provenienza di modello, prompt e runtime. È uno schema locale,
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

Il primo incremento implementa `ai-advisor` **in modalità osservazione**, senza inoltro automatico
di proposte: legge un assessment, produce una spiegazione citata e suggerisce
`EXTRA_SAMPLING` dal catalogo oppure si astiene. Non servono fondi reali.

I criteri di verifica del primo incremento sono:

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
Il [primo caso USGS](../services/environmental-case/README.md) ora implementa
questo confronto su un archivio approvato e mostra una MAE peggiore della
persistenza: 0,242 contro 0,205 mg/L a un'ora. Questo esito riguarda una sola
stazione e finestra e non abilita interventi fisici. La disponibilità storica
dei dati provvisori e la revisione indipendente restano da verificare.
Un modello appreso entra nell'Oracle solo dopo una valutazione su periodi non
usati per addestrarlo. Soglie operative richiedono revisione scientifica e civica.

Solo dopo queste verifiche collegheremo advisory, archivio replicato delle
evidenze e consenso. Ulteriori metriche e territori useranno cataloghi e policy
specifici, senza perdere la tracciabilità degli interventi finanziati.

Comandi, esiti osservati e limiti della verifica sono nel
[rapporto AI](AI_VALIDATION.md) e nella [guida del modulo](../services/ai-advisor/README.md).

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
