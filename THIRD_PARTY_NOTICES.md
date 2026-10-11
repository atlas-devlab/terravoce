# Third-party notices

TerraVoce uses external packages installed by pnpm. Their license and copyright
notices remain applicable. The exact dependency versions and integrity hashes
are recorded in `pnpm-lock.yaml`.

Direct runtime dependencies include OpenZeppelin Contracts, Zod, Chevrotain,
Fastify and node-postgres. Development tools include Hardhat and its toolbox,
TypeScript, tsx and Vitest. Read the license files distributed with the installed
packages before redistributing them.

Docker uses Node.js and PostgreSQL base images, whose components retain their
respective licenses. These images and dependency source trees are not vendored
in this repository.

The MIT SPDX headers in the project Solidity contracts have been preserved.
The recovered philosophical research downloads, build outputs, local runtime
data and tooling archives are excluded from this source publication.

The Oracle bridge uses Open Autonomy 0.21.29 and Open AEA 2.2.9 (Apache-2.0).
The generated runtime retains both upstream LICENSE files and the bridge
[NOTICE](services/autonomy/NOTICE). The skill configuration is adapted from
Valory's `register_reset_abci` configuration and declares Apache-2.0. Upstream
source is fetched at the immutable revisions recorded by `prepare.py`; it is
excluded from Git alongside generated local identities and Tendermint state.

## Optional local AI runtime and model

The AI advisor connects to a separately installed Ollama runtime (MIT license):
https://github.com/ollama/ollama. Runtime binaries and model weights are not
redistributed in this repository.

The local experiment evaluated Qwen3 0.6B and 1.7B, quantized as Q4_K_M and
downloaded through Ollama. The upstream Qwen model cards identify Apache-2.0:
https://huggingface.co/Qwen/Qwen3-0.6B and https://huggingface.co/Qwen/Qwen3-1.7B.
Keep the upstream model/runtime licenses with any separate redistribution.
## USGS real-data snapshot

`docs/datasets/usgs-willamette/continuous.json` and `station.json` contain U.S.
Geological Survey Water Data for the Nation data. The service identifies these
as US Government work in the public domain:
https://api.waterdata.usgs.gov/ogcapi/v1/
The accompanying manifest records station, time interval, retrieval date,
source URLs, quality protocol and exact body hashes. These data are not relicensed
as TerraVoce-generated measurements and USGS does not endorse this prototype.

The temperature and instantaneous discharge snapshots under
`docs/datasets/usgs-willamette-multivariate` come from the same public-domain
USGS service. Their gzip files preserve the original UTF-8 response bodies;
the accompanying manifest records the hashes of the decompressed bodies,
source URLs, parameters, units and local capture timestamps.
