import { describe, expect, it } from "vitest";

import { compileTerraLex, TerraLexCompileError } from "./compiler.js";
import { evaluatePolicy } from "./evaluator.js";

const source = `
policy "po-water-oxygen" version 1 {
  region "IT-PO-DELTA";
  metric "water.oxygen.mg_l";
  when risk >= 0.72 and confidence >= 0.80 and observations >= 5;
  allow "EXTRA_SAMPLING" reversible;
  allow "WATER_AERATION" reversible;
  budget 250 USDC per 7 days;
  challenge 24 hours;
  require community challenge;
  require guardian pause;
  forbid irreversible;
}
`;

describe("TerraLex", () => {
  it("compiles deterministically", () => {
    const first = compileTerraLex(source);
    const second = compileTerraLex(source.replace("  region", "\n  # comment\n  region"));

    expect(first.policyHash).toBe(second.policyHash);
    expect(first.policy.allowedActions).toEqual(["EXTRA_SAMPLING", "WATER_AERATION"]);
    expect(first.policy.budget.periodSeconds).toBe(7 * 86_400);
  });

  it("allows only contexts satisfying every constraint", () => {
    const bundle = compileTerraLex(source);
    const allowed = evaluatePolicy(bundle, {
      regionId: "IT-PO-DELTA",
      metric: "water.oxygen.mg_l",
      risk: 0.84,
      confidence: 0.91,
      observations: 12,
      requestedAction: "WATER_AERATION",
      requestedAmount: 180,
      requestedAsset: "USDC"
    });
    expect(allowed.allowed).toBe(true);

    const denied = evaluatePolicy(bundle, {
      regionId: "IT-PO-DELTA",
      metric: "water.oxygen.mg_l",
      risk: 0.84,
      confidence: 0.91,
      observations: 12,
      requestedAction: "DREDGE_RIVER",
      requestedAmount: 180,
      requestedAsset: "USDC"
    });
    expect(denied.allowed).toBe(false);
    expect(denied.reasons).toContain("action is not allowlisted");
  });

  it("rejects a policy without the guardian safeguard", () => {
    expect(() =>
      compileTerraLex(source.replace("  require guardian pause;\n", ""))
    ).toThrow(TerraLexCompileError);
  });
});

