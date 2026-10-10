import type {
  AssessmentContext,
  PolicyBundle,
  PolicyDecision
} from "./types.js";

export const evaluatePolicy = (
  bundle: PolicyBundle,
  context: AssessmentContext
): PolicyDecision => {
  const { policy, policyHash } = bundle;
  const reasons: string[] = [];

  if (context.regionId !== policy.regionId) reasons.push("region is outside policy scope");
  if (context.metric !== policy.metric) reasons.push("metric is outside policy scope");
  if (context.risk < policy.thresholds.riskGte) reasons.push("risk threshold not met");
  if (context.confidence < policy.thresholds.confidenceGte) {
    reasons.push("confidence threshold not met");
  }
  if (context.observations < policy.thresholds.observationsGte) {
    reasons.push("insufficient observations");
  }
  if (!policy.allowedActions.includes(context.requestedAction)) {
    reasons.push("action is not allowlisted");
  }
  if (context.requestedAsset !== policy.budget.asset) reasons.push("budget asset mismatch");
  if (context.requestedAmount > policy.budget.maxAmount) reasons.push("policy budget exceeded");
  if (!Number.isFinite(context.requestedAmount) || context.requestedAmount < 0) {
    reasons.push("requested amount is invalid");
  }

  if (reasons.length > 0) return { allowed: false, reasons, policyHash };

  return {
    allowed: true,
    reasons: ["all deterministic policy constraints passed"],
    policyHash,
    action: {
      name: context.requestedAction,
      reversible: true,
      maxAmount: policy.budget.maxAmount,
      asset: policy.budget.asset,
      challengeSeconds: policy.challengeSeconds
    }
  };
};

