# Virdacora: licenza del codice / source license

## Italiano

Dal presente aggiornamento, il codice e la documentazione di progetto senza
un'indicazione specifica sono distribuiti sotto **GNU Affero General Public
License, versione 3 soltanto (`AGPL-3.0-only`)**. Il testo integrale, senza
modifiche, è in [LICENSE](LICENSE). Questa pagina spiega l'ambito; non modifica
i termini della licenza.

La scelta mantiene possibile studiare, modificare e collaborare al progetto.
Permette anche usi commerciali. Chi distribuisce una versione coperta deve
rispettare gli obblighi relativi al sorgente; chi modifica il programma e lo
offre attraverso una rete deve offrire il sorgente corrispondente agli utenti
che vi interagiscono, secondo la sezione 13. La licenza non obbliga a pagarci,
donare alle comunità o aprire una pull request.

### Il codice precedente non scompare

Il progetto, allora chiamato TerraVoce, è stato pubblicato sotto MIT. Conserviamo
quella licenza e l'avviso di copyright in [LICENSES/MIT-legacy.txt](LICENSES/MIT-legacy.txt).
I permessi già concessi sulle copie MIT non vengono revocati. Il commit
`11549cf4d7284e7d39b470c5ea9d24747998dcc5` precede questo passaggio: non diventa
retroattivamente esclusivo o coperto solo da AGPL.

Le parti MIT incorporate conservano i propri avvisi e possono essere riutilizzate
secondo quei termini. La disponibilità della nuova versione complessiva sotto
AGPL non cancella quei permessi sulle parti preesistenti. Una modifica futura
deve dichiarare correttamente quali nuovi contributi sono coperti da AGPL.

### Eccezioni da rispettare

| Materiale | Termini applicabili |
| --- | --- |
| Codice e documentazione senza avviso specifico | AGPL-3.0-only per questa versione e i nuovi contributi a questi file. |
| Contratti e altri file con un avviso MIT esplicito | MIT; gli avvisi restano validi. Un cambio del singolo file richiede una revisione esplicita. |
| Skill adattata da Valory, configurazione e file sotto `services/autonomy/packages/terravoce/skills/oracle_abci` | Apache-2.0, con [NOTICE](services/autonomy/NOTICE) e attribuzioni originali. |
| Dipendenze, modelli e dati esterni | Termini dei rispettivi autori e fornitori, come documentato in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). |
| Nome, logo e immagini in `docs/assets` | [TRADEMARK_POLICY.md](TRADEMARK_POLICY.md); non sono inclusi nella licenza predefinita del codice. |

I dati USGS restano dati del fornitore; gli estratti FAO/CHIRPS conservano le
condizioni archiviate, comprese eventuali restrizioni commerciali. Cambiare
la licenza del codice non autorizza nuovi usi di quei dati.

### Contribuire e offrire un servizio

Inviare solo materiale che si può concedere sotto la licenza del file interessato,
conservando copyright e attribuzioni. Non è richiesta una cessione dei diritti
al promotore. Un fork deve distinguere la propria identità dal progetto ufficiale.

La repository è pubblica. Non è in esercizio un servizio pubblico
AGPL: non esiste oggi un'offerta di sorgenti operativa da promettere agli utenti.
Prima di rendere disponibile una versione modificata in rete, predisporre un
accesso gratuito al suo sorgente corrispondente, incluse le informazioni necessarie
per costruirla e installarla. Un semplice link a una repository privata non basta.

Riferimenti: [testo ufficiale AGPLv3](https://www.gnu.org/licenses/agpl-3.0.en.html),
[licenze compatibili secondo GNU](https://www.gnu.org/licenses/license-list.html#Expat).

## English

From this update, project source and documentation without a specific notice
are provided under the **GNU Affero General Public License, version 3 only
(`AGPL-3.0-only`)**. [LICENSE](LICENSE) contains the complete, unmodified text.
This page describes scope and does not change its terms.

Study, modification, collaboration and commercial use remain possible.
Distribution of covered versions entails the applicable source obligations.
Under section 13, operators of a modified networked version must offer its
Corresponding Source to users interacting with it. AGPL does not require
payments to the project, donations to communities or upstream pull requests.

TerraVoce's earlier MIT permissions remain valid. The original copyright and
license are preserved in [LICENSES/MIT-legacy.txt](LICENSES/MIT-legacy.txt).
Commit `11549cf4d7284e7d39b470c5ea9d24747998dcc5` predates this transition;
it is not retroactively made exclusive or AGPL-only. Incorporated MIT portions
retain their notices and permissions. Future changes must accurately identify
the new AGPL-covered contributions.

Files with explicit MIT notices remain MIT. The Valory-adapted skill under
`services/autonomy/packages/terravoce/skills/oracle_abci` retains Apache-2.0
and its [NOTICE](services/autonomy/NOTICE). These exceptions apply wherever
the corresponding files are present; older branches may not contain the skill.
Dependencies, external models and source datasets retain their own terms in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Logo assets and identity use
are covered separately by [TRADEMARK_POLICY.md](TRADEMARK_POLICY.md).

Contribute only material you can license under the affected file's terms and
preserve attribution. No copyright assignment to the maintainer is required.
A fork must distinguish its own identity from the official project.

The repository is public and no public AGPL service is operating.
Before offering a modified version over a network, provide free access to its
Corresponding Source and the required build/installation information.
A link to an inaccessible private repository is insufficient.

