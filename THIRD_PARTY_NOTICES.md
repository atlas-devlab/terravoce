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
