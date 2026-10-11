import { z } from "zod";
import { assessmentSchema, signedObservationSchema } from "@terravoce/protocol";

export const LIMITATIONS = "Rischio e confidence sono euristiche dimostrative, non probabilità scientifiche calibrate. Nessun intervento o trasferimento di fondi viene autorizzato da questo rapporto.";

export const sourceSchema = z.strictObject({
  id: z.string().min(1).max(64),
  text: z.string().min(1).max(4000),
  contentHash: z.string().regex(/^0x[0-9a-f]{64}$/)
});
export const advisorInputSchema = z.strictObject({
  version: z.literal("advisor-input-v1"),
  dataKind: z.enum(["synthetic", "public-replay"]),
  assessment: assessmentSchema.strict(),
  observations: z.array(signedObservationSchema.strict()).min(5).max(512),
  sources: z.array(sourceSchema).min(1).max(8)
});
export const selectionSchema = z.strictObject({
  assessmentId: z.string().regex(/^0x[0-9a-f]{64}$/),
  action: z.enum(["EXTRA_SAMPLING", "NONE"]),
  factIds: z.array(z.enum(["CURRENT_OXYGEN", "DECLINING_OXYGEN", "ILLUSTRATIVE_MODEL"])).min(1).max(3),
  citations: z.array(z.strictObject({
    sourceId: z.string().min(1).max(64),
    quote: z.string().min(12).max(500)
  })).min(1).max(4)
});
export type AdvisorInput = z.infer<typeof advisorInputSchema>;
export type Selection = z.infer<typeof selectionSchema>;
export type Source = z.infer<typeof sourceSchema>;

export interface ModelRequest {
  system: string;
  user: string;
  format: Record<string, unknown>;
  options: { temperature: 0; seed: 42; num_ctx: 4096; num_predict: 512 };
  think: false;
}
export interface ModelResult {
  content: string;
  model: string;
  modelDigest: string;
  runtimeVersion: string;
}
export interface AdvisorProvider {
  readonly model: string;
  readonly endpoint: string;
  generate(request: ModelRequest, signal: AbortSignal): Promise<ModelResult>;
}
export interface Advisory {
  version: "advisory-v1";
  mode: "observation-only";
  dataKind: "synthetic" | "public-replay" | null;
  status: "suggested" | "abstained";
  code: string;
  assessmentId: string | null;
  evidenceHash: string | null;
  policyHash: string | null;
  inputHash: string;
  action: "EXTRA_SAMPLING" | null;
  explanation: string;
  limitations: string;
  citations: Array<{ sourceId: string; quote: string; contentHash: string; url: string }>;
  facts: Array<{ id: string; text: string }>;
  provenance: {
    model: string;
    modelDigest: string | null;
    runtimeVersion: string | null;
    endpoint: string;
    promptVersion: string;
    promptHash: string | null;
    responseHash: string | null;
    inferenceAttempted: boolean;
    latencyMs: number;
    generatedAt: string;
  };
  advisoryHash: string;
}
