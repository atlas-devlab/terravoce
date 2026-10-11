# Prova Willamette a un'ora con quattro stagioni

Il protocollo è dichiarato prima del fit e prima di acquisire le quattro nuove
finestre di verifica. La priorità concordata è controllare se il nuovo
apprendimento riduce l'errore in modo credibile e regge nelle quattro stagioni.
Il 10% resta un obiettivo indicativo, non la soglia automatica di successo.

Si mantiene una sola ricetta: regressione ridge, otto ingressi già usati,
penalizzazione alpha=100. Si apprendono nuovi pesi su tutte le coppie complete
delle quattro finestre 2024. Nessuna variante viene scelta in base al test.
Con questa funzione di perdita, la forza relativa della penalizzazione dipende
anche dal numero di esempi: la prova valuta l'intero nuovo fit, senza attribuire
causalmente il risultato alla sola diversità stagionale.

Le finestre di esame sono 15–29 gennaio, aprile, luglio e ottobre 2025, in UTC.
Sono periodi successivi al training, diversi da quelli già usati dal progetto.
La qualità e disponibilità sono ancora da verificare. Una finestra insufficiente
o indisponibile rimane tale; non viene sostituita dopo aver visto i risultati.

Il confronto principale è con l'ultima misura invariata, sugli stessi orari.
Si riportano MAE, RMSE, bias e grandi errori per stagione e per giorno. La media
complessiva assegna lo stesso peso alle quattro stagioni. I periodi devono
avere almeno 500 coppie e 90% di copertura della griglia UTC per superare il
filtro pratico dei dati. Questo filtro non dimostra validità o potenza statistica.

L'incertezza esplorativa del vantaggio è stimata ricampionando blocchi di
48 ore dentro ciascuna stagione, con controlli anticipati a 24 e 72 ore, 5.000
repliche e seme fissato. Un vantaggio medio senza intervallo positivo oppure
con peggioramenti stagionali osservati non supera la regola dichiarata.
La precisione numerica 1e-9 non è una tolleranza ecologica. L'assenza di aumento
della MAE puntuale in una stagione non prova noninferiorità statistica.

Nessun risultato entra automaticamente nell'Oracle o nei finanziamenti.
Non si ricalibra né riusa la fascia estiva fallita. Questa prima prova misura
il valore previsto, non la qualità di un nuovo intervallo di previsione.
LLM, governance delle comunità e dei giovani e contratti restano quelli attuali.

Il protocollo completo è in
[`datasets/usgs-willamette-multiseason/protocol.json`](datasets/usgs-willamette-multiseason/protocol.json).
Il protocollo è stato pubblicato nel commit `eaebc10` prima del fit.
Il modello congelato è in
[`evidence/willamette-multiseason/frozen-model.json`](evidence/willamette-multiseason/frozen-model.json).
È stato appreso da 2.559 coppie complete del 2024. Il solver TypeScript già
presente è controllato con Cholesky Decimal a 50 cifre in Python: differenza
massima tra parametri 5,51e-14, sotto la tolleranza 1e-9. Questo è un controllo
aritmetico fra due implementazioni, non una validazione scientifica esterna.

Il comando di fit rifiuta orari del test, duplicati, ingressi non finiti,
ricette modificate e orizzonti diversi da un'ora. La valutazione usa i pesi
salvati e non chiama nessuno dei due solver. Il comando di acquisizione richiede
che protocollo e file dei pesi coincidano esattamente con quelli già nel commit
locale; ogni manifest lega i dati al loro hash e a quel commit.

I risultati saranno aggiunti dopo la verifica. Comandi dalla radice del repo,
dopo aver installato le dipendenze Node con `pnpm install --frozen-lockfile`:

```text
python scripts/experiment_multiseason.py verify-fit
node scripts/capture-willamette-multiseason.mjs
python scripts/experiment_multiseason.py evaluate
python scripts/experiment_multiseason.py verify
```

`fit` è disponibile per una nuova copia senza il file congelato. I comandi
di fit, acquisizione e valutazione rifiutano di sovrascrivere gli artefatti.
Per il normale controllo offline si usano soltanto `verify-fit` e `verify`.

Riferimenti metodologici:
[ridge](https://scikit-learn.org/stable/modules/linear_model.html#ridge-regression-and-classification),
[valutazione temporale e riferimenti](https://otexts.com/fpp3/toolbox.html),
[bootstrap a blocchi per dipendenza temporale](https://otexts.com/fpp3/advanced.html#bootstrapping-time-series).
