# TerraVoce: presentazione del progetto / project presentation

Scheda per spiegare il prototipo e cercare contributi tecnici e scientifici.
Project introduction for technical and scientific contributors.

## Italiano: cosa fa

TerraVoce è un progetto open source che rende tracciabili e riproducibili le
prove ambientali. L'obiettivo originale è aiutare le comunità a capire e
proteggere il proprio territorio attraverso osservazioni, analisi verificabili,
coordinamento distribuito e interventi con risultati controllabili.

Il prototipo oggi può selezionare automaticamente una stazione prima non
collegata in un catalogo USGS configurato, conservare i dati originali,
riprodurli in processi separati e registrare il loro impegno crittografico su una
blockchain locale. Nel caso Little North Santiam sono state raccolte 97 misure
storiche reali di ossigeno disciolto. I controlli rilevano alterazioni successive
rispetto a un riferimento originale conservato.

Il registro corretto permette a tre identità concordi di registrare la propria
busta di metadati anche se una quarta autorizzata presenta per prima una versione
diversa. Le 24 sequenze di arrivo sono provate sul contratto locale. Un modulo
separato verifica inoltre un risultato di revisione dei dati con governance ed
escrow simulati; le regole prevedono diritti delle comunità e dei giovani.

Sono prove locali di ricerca. Non dimostrano calibrazione fisica, assenza di
omissioni iniziali, operatori indipendenti o resistenza generale alla censura
statale. Una falsità iniziale del pubblicatore può ingannare verificatori onesti.
I modelli previsionali restano esperimenti da validare; non promettiamo oggi
previsioni ambientali affidabili, miglioramenti ecologici o interventi reali.

### Testo breve da adattare per presentazioni

> Stiamo sviluppando TerraVoce, un progetto open source per rendere verificabili
> i dati ambientali e dare alle comunità strumenti per controllare le decisioni
> sul proprio territorio. Abbiamo una demo riproducibile su misure reali USGS:
> scoperta di una nuova stazione, conservazione delle prove e test di
> manipolazione sulla blockchain locale. Cerchiamo contributi su dati,
> idrologia, sensori, sistemi distribuiti e sicurezza. È un prototipo di ricerca;
> verifiche sul campo e operatori indipendenti sono ancora da organizzare.

## English: what it does

TerraVoce is an open source project that makes environmental evidence traceable
and reproducible. Its original mission is to help communities understand and
protect their territories through observations, verifiable analysis, distributed
coordination and interventions whose outcomes can be checked.

The prototype can automatically select a previously unconnected station within
a configured USGS catalog, preserve the original data, reproduce it in separate
processes and register its cryptographic commitment on a local blockchain.
The Little North Santiam case contains 97 real historical dissolved-oxygen
measurements. Verification detects later alterations against a retained
original checkpoint.

The corrected registry allows three agreeing identities to finalize their
metadata envelope even if a fourth authorized identity submits a different
version first. All 24 arrival orders are exercised against the local contract.
A separate module also checks delivery of a data-review result through simulated
governance and escrow, preserving community and youth decision rights.

These are local research experiments. They do not establish physical
calibration, initial completeness, independent operators or general resistance
to state-level censorship. False initial publisher data can deceive honest
verifiers. Forecasting models remain experiments requiring validation; reliable
environmental forecasting, ecological improvement and real interventions are
not established by the present demonstrations.

### Short introduction to adapt for outreach

> We are developing TerraVoce, an open source project for verifiable environmental
> evidence and community oversight of decisions affecting their territories.
> Our reproducible demo uses real USGS measurements: discovery of a new station,
> retained evidence and tampering tests on a local blockchain. We welcome
> contributions in data, hydrology, sensors, distributed systems and security.
> This is a research prototype; field validation and independently operated
> deployments still need to be organized.

## ENV: base tecnica esistente / existing technical foundation

Il repository contiene già `packages/contracts/contracts/ENVToken.sol`:
ERC-20 con un limite di emissione e autorizzazioni `permit`. Il costruttore
riceve destinatario, quantità iniziale e tetto massimo; il contratto non espone
una funzione pubblica di emissione successiva. Prezzo, distribuzione commerciale,
vendita pubblica e diritti economici non sono implementati da questo file.
ENV non conferisce voto ambientale o prelievi dalla tesoreria protetta.

The repository already contains `packages/contracts/contracts/ENVToken.sol`:
an ERC-20 with a supply cap and `permit` approvals. Its constructor receives
the allocation recipient, initial supply and cap; the contract exposes no public
function for later minting. Pricing, commercial allocation, a public sale and
economic rights are not implemented by this file. ENV does not grant
environmental voting rights or withdrawals from the protected treasury.

## Raccolta fondi: proposta da definire / fundraising design to define

Una possibile utilità da valutare è l'accesso a servizi opzionali di analisi,
report personalizzati o elaborazione dati. Il servizio, i costi e il diritto
effettivo dell'acquirente devono essere definiti: questa scheda non li promette
e non configura un'offerta di ENV. Le prove ambientali pubbliche e i diritti
civici restano separati dall'acquisto di servizi.

One possible utility to assess is access to optional analysis, customized
reports or data processing. The service, its costs and the buyer's actual
entitlement must first be defined: this document promises none of them and
does not constitute an ENV offer. Public environmental evidence and civic
rights remain separate from service purchases.

| Decisione da preparare / decision to prepare | Risultato concreto / concrete output |
| --- | --- |
| Soggetto offerente e giurisdizione / offeror and jurisdiction | Struttura responsabile della raccolta / entity responsible for fundraising |
| Utilità e classificazione / utility and classification | Diritti dell'acquirente e inquadramento verificato / buyer rights and reviewed classification |
| Costi dello sviluppo / development costs | Budget per risultati verificabili, con preventivi / budget for verifiable milestones, backed by quotations |
| Emissione e allocazione / issuance and allocation | Quantità, destinatari, eventuale vesting e gestione degli invenduti / amounts, recipients, any vesting and unsold allocation |
| Regole della raccolta / fundraising rules | Obiettivo, durata, custodia, rendicontazione e condizioni applicabili / target, duration, custody, reporting and applicable terms |
| Verifica prima dell'apertura / pre-launch review | Revisione legale, fiscale, dei contratti e delle chiavi / legal, tax, contract and key-management review |

Per una normale offerta pubblica in Italia/UE di cripto-attività nel Titolo II
MiCA, l'articolo 4 prevede una persona giuridica e obblighi relativi al white
paper. Esistono eccezioni, ma non si presumono dal nome "utility" né dalla
piccola dimensione del progetto. L'articolo 6 richiede informazioni sui diritti
e sui rischi e vieta affermazioni sul valore futuro. Un white paper notificato
non equivale all'approvazione dell'autorità. Queste fonti servono a impostare
una verifica professionale del caso concreto, non a certificare una vendita.
[Articolo 4](https://www.esma.europa.eu/publications-and-data/interactive-single-rulebook/mica/article-4-offers-public-crypto-assets-other),
[articolo 6](https://www.esma.europa.eu/publications-and-data/interactive-single-rulebook/mica/article-6-content-and-form-crypto-asset).

For an ordinary public offer in Italy/the EU within MiCA Title II, Article 4
requires a legal person and white-paper obligations. Exceptions exist, but a
"utility" label or a small project does not establish eligibility. Article 6
requires information on rights and risks and prohibits assertions about future
value. Notification of a white paper is not regulatory approval. These sources
frame a professional assessment of the actual arrangement; they do not certify
a sale.
[Article 4](https://www.esma.europa.eu/publications-and-data/interactive-single-rulebook/mica/article-4-offers-public-crypto-assets-other),
[Article 6](https://www.esma.europa.eu/publications-and-data/interactive-single-rulebook/mica/article-6-content-and-form-crypto-asset).

## Documenti e collaborazione / documentation and contributions

- [README e stato del progetto / README and project status](../README.md).
- [Correzione e risultati in italiano](FIRST_ATTESTOR_FIX.md).
- [Correction, results and reproduction commands in English](FIRST_ATTESTOR_FIX_EN.md).
- [Come contribuire / how to contribute](../CONTRIBUTING.md).

I testi sono pronti per essere adattati e valutati. Questa scheda non pubblica
messaggi sui social, non contatta persone e non avvia pagamenti o una vendita.
The copy is ready for adaptation and review. This document does not post to
social networks, contact anyone or initiate payments or a sale.
