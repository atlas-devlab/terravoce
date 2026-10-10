# Protocol invariants

These rules are stronger than application conventions and must be enforced by
code or deployment configuration.

1. AI identities cannot cast community or youth votes.
2. Token balances do not influence environmental chamber votes.
3. Autonomous proposals can authorize only reversible allowlisted actions.
4. An autonomous proposal cannot exceed the per-action or per-epoch budget.
5. Any affected community member registered before proposal creation can
   challenge an autonomous proposal.
6. An irreversible proposal requires both chamber thresholds.
7. A guardian pause is public, reasoned, single-use, and time-limited.
8. Evidence must reach independent-oracle quorum before it can support action.
9. The treasury exposes no administrator withdrawal function.
10. A TerraLex program has no loops, recursion, network access, clock access, or
    arbitrary calls. Equal inputs and compiler versions produce equal output.

