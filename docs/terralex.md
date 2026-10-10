# TerraLex v0.1

TerraLex is a deliberately small policy language. It is not a general-purpose
language and cannot access the network, inspect the clock, allocate unbounded
memory, loop, recurse, or call a contract. Its job is to decide whether a model
assessment may produce a reversible action draft.

```terralex
policy "po-water-oxygen" version 1 {
  region "IT-PO-DELTA";
  metric "water.oxygen.mg_l";
  when risk >= 0.72 and confidence >= 0.80 and observations >= 5;
  allow "WATER_AERATION" reversible;
  budget 250 USDC per 7 days;
  challenge 24 hours;
  require community challenge;
  require guardian pause;
  forbid irreversible;
}
```

The compiler validates required safeguards, sorts unordered fields, serializes
canonical JSON, and computes a SHA-256 policy hash. Whitespace and comments do
not affect that hash. The on-chain activation ceremony binds the hash to a
region, action hashes, executor addresses, funding-unit limits, and a minimum
challenge duration.

Future versions should add source locations to diagnostics, a formal semantics
document, conformance vectors for non-TypeScript compilers, and a proof-oriented
compiler implementation. General loops or arbitrary smart-contract calls are
explicitly out of scope.

