from enum import Enum
from eth_account import Account
from eth_account.messages import encode_defunct

from packages.valory.skills.abstract_round_abci.base import (
    AbciApp, BaseSynchronizedData, CollectSameUntilThresholdRound,
    CollectDifferentUntilThresholdRound, CollectionRound, TransactionNotValidError,
)
from packages.terravoce.skills.oracle_abci.payloads import EvaluationPayload, SignaturePayload


class Event(Enum):
    DONE = "done"
    NONE = "none"
    NO_MAJORITY = "no_majority"
    TIMEOUT = "timeout"


class SynchronizedData(BaseSynchronizedData):
    @property
    def digest(self):
        return self.db.get_strict("digest")

    @property
    def signatures(self):
        return self.db.get_strict("signatures")


class EvaluationRound(CollectSameUntilThresholdRound):
    payload_class = EvaluationPayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    none_event = Event.NONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = "evaluations"
    selection_key = "digest"


class SignatureRound(CollectDifferentUntilThresholdRound):
    payload_class = SignaturePayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    collection_key = "signatures"

    def check_payload(self, payload):
        super().check_payload(payload)
        try:
            signer = Account.recover_message(
                encode_defunct(hexstr=self.synchronized_data.db.get_strict("digest")),
                signature=payload.signature)
            if signer.lower() != payload.sender.lower():
                raise ValueError("Certificate signature does not match its sender")
        except (ValueError, TypeError) as error:
            raise TransactionNotValidError(str(error)) from error


class IdleRound(CollectionRound):
    payload_class = SignaturePayload
    synchronized_data_class = SynchronizedData

    def end_block(self):
        return None


class FinishedRound(IdleRound):
    """One immutable job per service run; never automatically resubmit."""


class RejectedRound(IdleRound):
    """Quorum denied the action; no certificate is produced."""


class OracleAbciApp(AbciApp[Event]):
    initial_round_cls = EvaluationRound
    initial_states = {EvaluationRound}
    transition_function = {
        EvaluationRound: {Event.DONE: SignatureRound, Event.NONE: RejectedRound,
                          Event.NO_MAJORITY: EvaluationRound, Event.TIMEOUT: EvaluationRound},
        SignatureRound: {Event.DONE: FinishedRound, Event.TIMEOUT: SignatureRound},
        FinishedRound: {Event.DONE: FinishedRound},
        RejectedRound: {Event.DONE: RejectedRound},
    }
    final_states = set()
    event_to_timeout = {Event.TIMEOUT: 60.0}
    db_pre_conditions = {EvaluationRound: set()}
    db_post_conditions = {}
