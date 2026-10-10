# Oracle API

The service listens on port `8787` by default.

| Method | Path | Purpose | Authentication |
| --- | --- | --- | --- |
| GET | `/healthz` | readiness and active policy hash | none |
| POST | `/v1/sensors` | register an Ed25519 sensor | `x-admin-token` |
| POST | `/v1/observations` | submit a signed observation | sensor signature |
| POST | `/v1/assessments/run` | run model and TerraLex policy | `x-oracle-token` |
| GET | `/v1/regions/:regionId/metrics/:metric/latest` | latest assessment | none in MVP |

The assessment response contains the reproducible `evidenceHash`, the TerraLex
decision, and an optional reversible `actionDraft`. The service intentionally
does not hold a treasury key or vote credential.

