# Source publication validation

The source was recovered on 10 October 2026 from the existing TerraVoce research
workspace. Project implementation, policy, database schema, configuration and
dependency lockfile were preserved. Publication adds a root MIT license,
contribution guidance and repository documentation.

Generated dependency trees, compiled outputs, caches, machine-specific working
files and philosophical research downloads are excluded. The source copy was
verified against its originals with SHA-256 before documentation updates.

## Checks rerun on the public copy

Environment: Windows, Node.js 24.19.0, pnpm 11.7.0 and Solidity compiler 0.8.28
(Cancun target). The dependency lockfile is unchanged from the recovered project.

| Command | Result |
| --- | --- |
| `pnpm install --frozen-lockfile` | Passed with the pinned package manager; dependency integrity checks retained |
| `pnpm build` | Passed: TypeScript workspace and 11 Solidity source files compiled |
| `pnpm check` | Passed |
| `pnpm test` | Passed: 16 tests, no failures or skips |
| `pnpm e2e` | Passed: proposal reached Executed and released simulated funding |
| `pnpm demo` | Passed: 12 signed synthetic observations and an allowed demo action |
| `pnpm terralex compile ../../policies/po-water-v1.terra` | Passed: policy hash agrees with the end-to-end demonstration |

Tests cover protocol signatures (1), TerraLex (3), the oracle API (2), and
Solidity governance (10). The end-to-end transfer is 180 units of the
six-decimal mock funding asset on a simulated network, not a real payment.

The initial README compiler command failed because pnpm runs the filtered CLI
from `packages/terralex`. The public README corrects the argument to
`../../policies/po-water-v1.terra`; this documentation correction leaves the
implementation unchanged.

## Verification boundaries

The tests and end-to-end demonstration use synthetic observations, generated
demo identities, an in-memory store and Hardhat's simulated local network.
They establish behavior of this prototype under the tested scenarios. They do
not establish environmental model validity, production security, a deployed
public blockchain, or field performance.

The Docker/PostgreSQL deployment was not rerun for this source publication.
No live sensors, real funds or physical actuators are connected. An independent
contract audit, scientific review and deployment validation remain future work.
