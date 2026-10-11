import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { loadIrrigationReview, prepareIrrigationReview } from "./irrigation.js";

const input = JSON.parse(await readFile(new URL("../../../docs/evidence/awash-irrigation/result.json", import.meta.url), "utf8"));
describe("irrigation research boundary", () => {
  it("replays the source commitments and numerical score", async () => {
    const review = await loadIrrigationReview(fileURLToPath(new URL("../../../", import.meta.url)));
    expect(review.evidenceHash).toMatch(/^0x[0-9a-f]{64}$/);
    expect(review.result.absoluteErrorMmPerDay).toBeLessThan(0.1); // This archived round, not an acceptance threshold.
    expect(review.evidenceNature).toBe("remote-sensing-estimate");
  });
  it("keeps measured withdrawals, skill and ecological improvement unestablished", () => {
    const review = prepareIrrigationReview(input);
    expect(review.irrigationWithdrawalM3).toBeNull();
    expect(review.operationalEligible).toBe(false);
    expect(review.fundingRelease).toBe(false);
    for (const field of ["skillEstablished", "irrigationAttributionEstablished", "ecologicalImprovementVerified", "fundingRelease", "operationalEligible"]) {
      expect(() => prepareIrrigationReview({ ...input, [field]: true })).toThrow();
    }
    expect(() => prepareIrrigationReview({ ...input, irrigationWithdrawalM3: 1 })).toThrow();
  });
  it("rejects incompatible units and a fabricated score", () => {
    expect(() => prepareIrrigationReview({ ...input, unit: "m3" })).toThrow();
    expect(() => prepareIrrigationReview({ ...input, absoluteErrorMmPerDay: 0 })).toThrow("reproduce");
  });
});
