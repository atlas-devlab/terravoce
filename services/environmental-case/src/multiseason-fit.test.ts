import { describe, expect, it } from "vitest";
import { fitMultiseason } from "./multiseason-fit.js";

const fixture = () => ({ version: "willamette-multiseason-fit-input-v1", alpha: 100, rows: [
  { origin: "2024-01-01T06:00:00.000Z", target: "2024-01-01T07:00:00.000Z", features: [10, 0, 0, 0, 0, 0, 5, 0], persistence: 10, actual: 11 },
  { origin: "2024-01-01T06:30:00.000Z", target: "2024-01-01T07:30:00.000Z", features: [10, 0, 0, 0, 0, 0, 5, 0], persistence: 10, actual: 11 }
] });
describe("fixed four-season research fit", () => {
  it("learns a known constant residual without penalizing its intercept", () => {
    const model = fitMultiseason(fixture());
    expect(model.residualIntercept).toBe(1);
    expect(model.coefficients).toEqual(Array(8).fill(0));
    expect(model.scale).toEqual(Array(8).fill(1));
  });
  it("rejects later test labels, altered horizon, off-grid and duplicate training origins", () => {
    for (const mutate of [
      (v: ReturnType<typeof fixture>) => { v.rows[0]!.origin = "2025-01-01T06:00:00.000Z"; v.rows[0]!.target = "2025-01-01T07:00:00.000Z"; },
      (v: ReturnType<typeof fixture>) => { v.rows[0]!.target = "2024-01-01T08:00:00.000Z"; },
      (v: ReturnType<typeof fixture>) => { v.rows[0]!.origin = "2024-01-01T06:01:00.000Z"; v.rows[0]!.target = "2024-01-01T07:01:00.000Z"; },
      (v: ReturnType<typeof fixture>) => { v.rows[1] = structuredClone(v.rows[0]!); }
    ]) { const v = fixture(); mutate(v); expect(() => fitMultiseason(v)).toThrow("Training row"); }
  });
  it("rejects changing the fixed recipe and malformed numerical vectors", () => {
    const changed = fixture(); changed.alpha = 1;
    expect(() => fitMultiseason(changed)).toThrow();
    const broken = fixture(); broken.rows[0]!.features[0] = NaN;
    expect(() => fitMultiseason(broken)).toThrow();
    const mismatch = fixture(); mismatch.rows[0]!.features[0] = 9;
    expect(() => fitMultiseason(mismatch)).toThrow("oxygen mismatch");
  });
});
