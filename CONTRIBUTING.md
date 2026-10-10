# Contributing to TerraVoce

Thank you for helping turn an environmental research prototype into something
that can be examined and reproduced by others.

## Start with a bounded change

Check existing issues and open a proposal before a substantial architectural
change. Explain the problem, an example that demonstrates it, and how the change
would be verified. English and Italian are welcome.

Useful contributions include policy examples, API documentation, parser and
governance tests, accessibility, and evidence-based review of the environmental
assumptions. A proposed scientific improvement should identify its data sources,
units, limitations and reproducibility criteria.

## Development

Use Node.js 24 or later and pnpm 11.7.0. From the root:

```sh
pnpm install --frozen-lockfile
pnpm build
pnpm check
pnpm test
pnpm e2e
```

The end-to-end demonstration runs on Hardhat's simulated local blockchain.
Use generated identities, synthetic observations and valueless test tokens.
Keep funded wallets, API credentials, sensor identities and personal data out
of commits, logs and issues. Do not commit generated builds or dependencies.

## Pull requests

- Describe the concrete behavior before and after the change.
- Keep one coherent change per pull request.
- Add meaningful regression tests when behavior changes.
- Report the commands you ran and any verification you could not complete.
- Preserve deterministic policy evaluation and existing governance boundaries.
- Distinguish simulation results from field validation or an independent audit.

For credential exposure or a security issue that could affect real deployments,
use GitHub's private vulnerability reporting when enabled. Otherwise agree a
private channel with the maintainer before sharing sensitive details.

## License

Contributions submitted for inclusion are under the MIT License in [LICENSE](LICENSE),
unless explicitly agreed otherwise. Submit only material you can license compatibly
and preserve third-party attribution.
