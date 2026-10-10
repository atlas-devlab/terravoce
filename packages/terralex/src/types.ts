import { z } from "zod";

export type DurationUnit = "hours" | "days";

export type TerraLexStatement =
  | { kind: "region"; value: string }
  | { kind: "metric"; value: string }
  | {
      kind: "when";
      conditions: Array<{
        field: "risk" | "confidence" | "observations";
        value: number;
      }>;
    }
  | { kind: "allow"; action: string; reversible: true }
  | {
      kind: "budget";
      amount: number;
      asset: string;
      period: number;
      unit: DurationUnit;
    }
  | { kind: "challenge"; duration: number; unit: DurationUnit }
  | { kind: "require-community-challenge" }
  | { kind: "require-guardian-pause" }
  | { kind: "forbid-irreversible" };

export interface TerraLexAst {
  name: string;
  version: number;
  statements: TerraLexStatement[];
}

const thresholdSchema = z.object({
  riskGte: z.number().min(0).max(1),
  confidenceGte: z.number().min(0).max(1),
  observationsGte: z.number().int().positive()
});

export const compiledPolicySchema = z.object({
  language: z.literal("TerraLex"),
  compilerVersion: z.literal(1),
  policyVersion: z.number().int().positive(),
  name: z.string().min(1),
  regionId: z.string().min(1),
  metric: z.string().min(1),
  thresholds: thresholdSchema,
  allowedActions: z.array(z.string().min(1)).min(1),
  budget: z.object({
    maxAmount: z.number().nonnegative(),
    asset: z.string().regex(/^[A-Z][A-Z0-9]{1,11}$/),
    periodSeconds: z.number().int().positive()
  }),
  challengeSeconds: z.number().int().positive(),
  safeguards: z.object({
    communityChallenge: z.literal(true),
    guardianPause: z.literal(true),
    irreversibleForbidden: z.literal(true)
  })
});

export type CompiledPolicy = z.infer<typeof compiledPolicySchema>;

export interface PolicyBundle {
  policy: CompiledPolicy;
  canonicalJson: string;
  policyHash: `0x${string}`;
}

export interface AssessmentContext {
  regionId: string;
  metric: string;
  risk: number;
  confidence: number;
  observations: number;
  requestedAction: string;
  requestedAmount: number;
  requestedAsset: string;
}

export interface PolicyDecision {
  allowed: boolean;
  reasons: string[];
  policyHash: `0x${string}`;
  action?: {
    name: string;
    reversible: true;
    maxAmount: number;
    asset: string;
    challengeSeconds: number;
  };
}

