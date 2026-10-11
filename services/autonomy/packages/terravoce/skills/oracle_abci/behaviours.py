import json
from pathlib import Path

from packages.valory.skills.abstract_round_abci.behaviours import AbstractRoundBehaviour, BaseBehaviour
from packages.terravoce.skills.oracle_abci.payloads import EvaluationPayload, SignaturePayload
from packages.terravoce.skills.oracle_abci.rounds import (
    OracleAbciApp, EvaluationRound, SignatureRound, FinishedRound, RejectedRound, SynchronizedData,
)
from packages.terravoce.skills.oracle_abci.validation import action_digest


class EvaluateBehaviour(BaseBehaviour):
    matching_round = EvaluationRound

    def async_act(self):
        # The local harness opens this gate only after injecting the node failure.
        while not Path(self.context.params.job_path).with_name("start").exists():
            yield from self.sleep(1.0)
        job = json.loads(Path(self.context.params.job_path).read_text())
        response = yield from self.get_http_response(
            method="POST", url=self.context.params.oracle_url + "/v1/assessments/run",
            headers={"Content-Type": "application/json", "x-oracle-token": self.context.params.oracle_token},
            content=json.dumps(job["input"]).encode(),
        )
        digest = None
        try:
            if response.status_code != 201:
                raise ValueError("Oracle HTTP error")
            digest = action_digest(job, json.loads(response.body))
            self.context.logger.info("ORACLE_VERIFIED job=%s digest=%s", job["jobId"], digest)
        except (ValueError, KeyError, TypeError) as error:
            self.context.logger.error("ORACLE_REJECTED %s", error)
        yield from self.send_a2a_transaction(EvaluationPayload(self.context.agent_address, digest))
        yield from self.wait_until_round_end()
        self.set_done()


class SignBehaviour(BaseBehaviour):
    matching_round = SignatureRound

    def async_act(self):
        state = SynchronizedData(self.context.state.synchronized_data.db)
        signature = yield from self.get_signature(bytes.fromhex(state.digest[2:]))
        yield from self.send_a2a_transaction(SignaturePayload(self.context.agent_address, signature))
        yield from self.wait_until_round_end()
        self.set_done()


class ExportBehaviour(BaseBehaviour):
    matching_round = FinishedRound

    def async_act(self):
        state = SynchronizedData(self.context.state.synchronized_data.db)
        job = json.loads(Path(self.context.params.job_path).read_text())
        certificate = {"jobId": job["jobId"], "digest": state.digest,
                       "signatures": [{"signer": sender, "signature": payload["signature"]}
                                      for sender, payload in sorted(state.signatures.items(), key=lambda x: x[0].lower())]}
        destination = Path(self.context.params.certificate_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(json.dumps(certificate, indent=2))
        temporary.replace(destination)
        self.context.logger.info("CERTIFICATE_EXPORTED job=%s signers=%s", job["jobId"], len(certificate["signatures"]))
        while True:
            yield from self.sleep(60.0)


class RejectedBehaviour(BaseBehaviour):
    matching_round = RejectedRound

    def async_act(self):
        self.context.logger.error("JOB_REJECTED: no certificate")
        while True:
            yield from self.sleep(60.0)


class OracleRoundBehaviour(AbstractRoundBehaviour):
    initial_behaviour_cls = EvaluateBehaviour
    abci_app_cls = OracleAbciApp
    behaviours = {EvaluateBehaviour, SignBehaviour, ExportBehaviour, RejectedBehaviour}
