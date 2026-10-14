# Verifica del ponte Open Autonomy

Verifica locale eseguita l'11 ottobre 2026, su Windows con Docker Desktop e container Linux. Il codice usa Open Autonomy 0.21.29, Open AEA 2.2.9 e Tendermint 0.34.19. Le osservazioni sono sintetiche e la blockchain è Hardhat locale.

| Prova | Esito osservato |
| --- | --- |
| Quattro nodi in avvio | Tutti producono blocchi con potenza di voto uguale |
| Due nodi completi spenti prima del job | Gli altri agenti restano attivi; nessun certificato; altezze ferme a 5 e 5 durante l'osservazione |
| Un nodo completo spento prima del job | Tre firme valide sullo stesso digest; i tre validatori proseguono fino al blocco 9 |
| Inoltro del certificato da un relayer | `TerraAutonomyBridge` crea la proposta nel Governor |
| Due firme, firma duplicata, importo modificato | Il bridge rifiuta la presentazione |
| Riutilizzo dello stesso job | Il bridge rifiuta la seconda presentazione |
| Esecuzione prima della finestra pubblica | Il Governor rifiuta l'esecuzione |
| Comunità contesta e approva; giovani non approvano | Proposta respinta; saldo dell'esecutore pari a zero |

Digest del certificato verificato dal contratto: `0x7949a96da5a6526160a692e7316bc9d04b9e6283094511ddb14c4dd5ae6a244f`.

Controlli aggiuntivi passati: build e check del workspace; 21 test TypeScript/Solidity, inclusi cinque test del bridge; sette test Python di interoperabilità del digest e rifiuto di manifest alterati; dimostrazione blockchain preesistente (`pnpm e2e`). I test del bridge verificano anche scadenza, binding al contratto, policy disattivata e finanziamento di una proposta reversibile dopo la finestra del Governor.

Per riprodurre la prova e trovare manifest, certificati, report e log, seguire [la guida del servizio](../services/autonomy/README.md). Ogni esecuzione genera identità locali nuove, quindi cambiano job ID, digest e altezze dei blocchi. Le proprietà da verificare restano quorum tre, assenza di certificato con due nodi offline e mantenimento delle garanzie civiche.

Questa verifica riguarda un job e guasti di arresto sullo stesso computer. Non verifica operatori geograficamente indipendenti, recupero dopo riavvio, partizioni prolungate, sensori reali, accuratezza scientifica, fondi reali, Safe o registrazione del servizio Olas. Le attestazioni del registro delle evidenze sono predisposte dalla fixture locale. La missione globale di Virdacora richiede ancora questi collegamenti e la gestione collettiva del servizio.
