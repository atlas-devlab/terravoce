from dataclasses import dataclass
from typing import Optional

from packages.valory.skills.abstract_round_abci.base import BaseTxPayload


@dataclass(frozen=True)
class EvaluationPayload(BaseTxPayload):
    digest: Optional[str]


@dataclass(frozen=True)
class SignaturePayload(BaseTxPayload):
    signature: str
