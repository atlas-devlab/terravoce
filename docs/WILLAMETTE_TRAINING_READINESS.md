# Preparazione dei dati Willamette per la nuova prova a un'ora

La priorità concordata è migliorare e verificare la previsione numerica a
**un'ora**. Solo dopo verifiche adeguate studieremo le 24 ore e i tre mesi.
LLM, lettura del territorio e valutazione degli interventi restano passi
successivi della missione ambientale di TerraVoce.

Il precedente modello estivo ha fallito la verifica su autunno e inverno.
Questa modifica prepara i dati per una ricerca successiva: **non addestra un
nuovo modello e non dimostra che la previsione sia migliorata**.

## Cosa abbiamo verificato

Prima del download, il commit `de1ec6f` ha dichiarato quattro finestre di
quattordici giorni del 2024: 1–15 gennaio, aprile, luglio e ottobre, in UTC.
Si usano le stesse serie USGS-14211720 di ossigeno, temperatura e portata
istantanea con segno. Le risposte originali sono conservate in gzip con URL,
orari di acquisizione, impronte SHA-256 e binding al protocollo.

I criteri restano misure approvate, senza qualificatori, finite e confrontabili
per unità/statistica/serie. Ogni abbinamento richiede 12 misure consecutive a
30 minuti nelle tre serie e un bersaglio di ossigeno esatto un'ora dopo.
Non interpoliamo i vuoti. Il segno della portata è conservato.

| Finestra | Abbinamenti completi | Orari teorici utilizzabili | Copertura della griglia | Temperatura approvata | Ossigeno approvato |
| --- | ---: | ---: | ---: | --- | --- |
| Inverno 2024 | 660 | 660 | 100% | 5.1–8.6 °C | 12.4–14.7 mg/L |
| Primavera 2024 | 644 | 660 | 97.58% | 9.5–12.7 °C | 11.4–12.6 mg/L |
| Estate 2024 | 660 | 660 | 100% | 20.7–25.0 °C | 7.4–9.3 mg/L |
| Autunno 2024 | 595 | 660 | 90.15% | 14.8–17.8 °C | 8.8–9.9 mg/L |

Totale: **2.559 abbinamenti completi**. Gli intervalli descrivono tutte le
misure approvate nella rispettiva finestra, non soltanto gli input di un fit.
Le finestre coprono condizioni più varie del vecchio addestramento estivo;
sono comunque quattro periodi scelti, non un anno completo o una prova di
rappresentatività del bacino.

## Il problema del denominatore

Il primo conteggio considerava le origini con una misura di ossigeno presente.
In autunno ce ne sono 608: 595 coppie complete e 13 storie/bersagli incompleti.
Il 2.14% di origini scartate sembra poco, ma non comprende gli orari del tutto
assenti. La griglia UTC attesa contiene 660 origini: mancano 52 misure di
ossigeno all'origine, oltre alle 13 coppie incomplete. Quindi la copertura
utile è **595/660 = 90.15%**, non 595/608.

Il rapporto ora conserva entrambi i conteggi. Un test controlla esplicitamente
che le 52 origini assenti restino nel denominatore. La causa fisica o tecnica
dei vuoti non è stata accertata.

Il protocollo anticipato usava un filtro pratico di almeno 500 coppie e al
massimo 5% di scarti tra le origini presenti. Tutte le finestre lo superano.
**Quel filtro non garantisce completezza della griglia, accuratezza o validità
scientifica.** Non modifichiamo retroattivamente il criterio per presentarlo
come un altro test: mostriamo separatamente la copertura completa e i vuoti.

## Cosa è implementato

- `scripts/capture-willamette-training-audit.mjs`: acquisizione opzionale dalla
  fonte, al massimo tre richieste concorrenti. Non sovrascrive catture esistenti;
  un periodo indisponibile resta registrato come tale, senza sostituzione.
- `scripts/audit_training_readiness.py`: verifica offline di protocollo,
  query, hash, identità/qualità dei record, intervalli e griglia attesa.
- `docs/evidence/willamette-forecast/training-readiness.json`: rapporto completo
  riproducibile, con `modelFitted=false` e `forecastSkillEvaluated=false`.
- Tre test per denominatore e assenza di fit, hash alterati e finestra
  indisponibile. La CI verifica il rapporto senza collegarsi a USGS.

Il [quaderno eseguito](notebooks/willamette-training-readiness.ipynb) mostra
in poche celle il controllo, i conteggi e il limite del denominatore.

Riproduzione dalla radice, con Python disponibile:

```sh
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 scripts/audit_training_readiness.py --summary --verify docs/evidence/willamette-forecast/training-readiness.json
```

Su Windows `python3` può essere sostituito dal percorso del proprio Python.
Il comando di rete opzionale è `node scripts/capture-willamette-training-audit.mjs`;
le catture già archiviate rendono superfluo rilanciarlo.

## Decisione da preparare insieme

La nuova prova deve fissare prima del fit: dati di apprendimento, periodi per
scelta/calibrazione e verifiche successive non usate per scegliere il metodo.
Questi dati 2024 sono stati ispezionati come materiale di preparazione; non
possono essere presentati come un test finale mai visto.

Il primo confronto proposto mantiene una regressione interpretabile e la
persistenza come riferimento. Per dire che è utile serviranno miglioramento
su periodi distinti, controllo del bias stagionale e una fascia d'errore con
copertura misurata. I valori quantitativi di successo del nuovo protocollo
devono ancora essere fissati; non sono soglie ecologiche o legali.

Gli archivi finalizzati non dimostrano la disponibilità dei dati in tempo reale
alla data storica. Nessun nuovo modello entra nell'Oracle, nelle proposte o nei
finanziamenti. La governance delle comunità e dei giovani rimane quella attuale.
Le 24 ore richiederanno ulteriori verifiche; i tre mesi includeranno scenari
condizionati con ipotesi esplicite.
