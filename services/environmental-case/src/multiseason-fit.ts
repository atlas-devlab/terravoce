import { z } from "zod";
import { fitRidge, type RidgeModel } from "./ridge.js";

const rowSchema = z.object({
  origin: z.iso.datetime(), target: z.iso.datetime(),
  features: z.array(z.number().finite()).length(8),
  actual: z.number().finite().nonnegative(), persistence: z.number().finite().nonnegative()
}).strict();
const inputSchema = z.object({
  version: z.literal("willamette-multiseason-fit-input-v1"),
  alpha: z.literal(100), rows: z.array(rowSchema).min(1)
}).strict();
const starts = ["2024-01-01", "2024-04-01", "2024-07-01", "2024-10-01"].map((s) => Date.parse(s + "T00:00:00Z"));

/** Research-only entry point: fixed recipe and 2024 windows; never exported by the operational package. */
export function fitMultiseason(input: unknown): RidgeModel {
  const parsed = inputSchema.parse(input), origins = new Set<number>();
  for (const row of parsed.rows) {
    const origin = Date.parse(row.origin), target = Date.parse(row.target);
    if (target - origin !== 3_600_000 || row.features[0] !== row.persistence || origins.has(origin) ||
        !starts.some((start) => origin >= start + 19_800_000 && target <= start + 14 * 86_400_000 && (origin - start) % 1_800_000 === 0)) {
      throw new Error("Training row outside fixed 2024 grid, wrong horizon, duplicate origin or oxygen mismatch");
    }
    origins.add(origin);
  }
  return fitRidge(parsed.rows.map((r) => r.features), parsed.rows.map((r) => r.actual - r.persistence), parsed.alpha);
}
