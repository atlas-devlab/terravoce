from packages.valory.skills.abstract_round_abci.models import (
    BaseParams, SharedState as BaseSharedState, BenchmarkTool, Requests,
)
from packages.terravoce.skills.oracle_abci.rounds import OracleAbciApp


class Params(BaseParams):
    def __init__(self, *args, **kwargs):
        self.oracle_url = self._ensure("oracle_url", kwargs, str)
        self.oracle_token = self._ensure("oracle_token", kwargs, str)
        self.job_path = self._ensure("job_path", kwargs, str)
        self.certificate_path = self._ensure("certificate_path", kwargs, str)
        super().__init__(*args, **kwargs)


class SharedState(BaseSharedState):
    abci_app_cls = OracleAbciApp
