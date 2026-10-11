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

The frozen seasonal validation snapshots under
`docs/datasets/usgs-willamette-validation/autumn-2025` and `winter-2026` also
contain USGS public-domain oxygen, temperature and instantaneous discharge
responses. Their manifests bind exact decompressed response hashes, retrieval
timestamps and source URLs to the predeclared validation protocol. Approval
status describes the archived observations; it does not prove their historical
real-time availability or constitute USGS endorsement of our predictions.

The four seasonal source captures under `docs/datasets/usgs-willamette-training-audit`
are from the same USGS public-domain service. Their manifests preserve source
URLs, exact decompressed-body hashes and retrieval timestamps. They are data
readiness evidence, not new measurements or USGS validation of a forecast.

The four later captures under `docs/datasets/usgs-willamette-multiseason` are
from the same USGS public-domain service. Every manifest additionally binds the
raw protocol hash, exact frozen research-model file hash, and pre-capture Git
commit. Low archived oxygen values remain source observations, not proof of
an independently observed ecological event or USGS endorsement of an alert.

## FAO WaPOR native window extracts

`docs/datasets/awash-irrigation` retains FAO WaPOR v3 catalog/mapset/raster
responses and native pixel windows read from the publisher's public cloud
assets. The manifest hashes these archived extracts and metadata, not the
complete original continental GeoTIFFs. Attribution: FAO WaPOR database,
accessed 12 October 2026 in Europe/Rome; precipitation is distributed from
CHIRPS. See https://www.fao.org/in-action/remote-sensing-for-water-productivity/wapor-data-access/en.

Publisher data terms apply separately from TerraVoce's MIT code license.
The archived L1-PCP-D mapset explicitly declares CC BY-NC-SA 4.0 in
`additionalInfo.Citation`; retain that attribution and source notice with its
extracts and derived data. The L2-AETI-D response has no explicit license in
`additionalInfo`; do not infer MIT licensing or unrestricted commercial reuse
from its open API availability. Preserve source terms with any reuse.
FAO does not endorse the forecast or a claim about irrigation withdrawals.

Rasterio 1.5.2 is an optional capture dependency (BSD-3-Clause), with separately
licensed GDAL and other wheel components. It is not vendored and is not needed
for the offline replay. Its dependency notices remain applicable.
