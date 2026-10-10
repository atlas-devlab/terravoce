import { createHash } from "node:crypto";

import {
  compiledPolicySchema,
  type CompiledPolicy,
  type DurationUnit,
  type PolicyBundle,
  type TerraLexAst,
  type TerraLexStatement
} from "./types.js";
import { parseTerraLex } from "./parser.js";

const seconds = (value: number, unit: DurationUnit): number =>
  value * (unit === "days" ? 86_400 : 3_600);

const canonicalize = (value: unknown): unknown => {
  if (Array.isArray(value)) {
    return value.map(canonicalize);
  }
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, child]) => [key, canonicalize(child)])
    );
  }
  return value;
};

export const canonicalJson = (value: unknown): string =>
  JSON.stringify(canonicalize(value));

const one = <T extends TerraLexStatement["kind"]>(
  ast: TerraLexAst,
  kind: T,
  diagnostics: string[]
): Extract<TerraLexStatement, { kind: T }> | undefined => {
  const matches = ast.statements.filter(
    (statement): statement is Extract<TerraLexStatement, { kind: T }> =>
      statement.kind === kind
  );
  if (matches.length !== 1) {
    diagnostics.push(`expected exactly one '${kind}' statement, found ${matches.length}`);
  }
  return matches[0];
};

export class TerraLexCompileError extends Error {
  public constructor(public readonly diagnostics: string[]) {
    super(diagnostics.join("\n"));
    this.name = "TerraLexCompileError";
  }
}

export const compileAst = (ast: TerraLexAst): PolicyBundle => {
  const diagnostics: string[] = [];
  if (!Number.isInteger(ast.version) || ast.version <= 0) {
    diagnostics.push("policy version must be a positive integer");
  }

  const region = one(ast, "region", diagnostics);
  const metric = one(ast, "metric", diagnostics);
  const when = one(ast, "when", diagnostics);
  const budget = one(ast, "budget", diagnostics);
  const challenge = one(ast, "challenge", diagnostics);
  one(ast, "require-community-challenge", diagnostics);
  one(ast, "require-guardian-pause", diagnostics);
  one(ast, "forbid-irreversible", diagnostics);

  const actions = ast.statements
    .filter(
      (statement): statement is Extract<TerraLexStatement, { kind: "allow" }> =>
        statement.kind === "allow"
    )
    .map((statement) => statement.action);

  if (actions.length === 0) diagnostics.push("at least one reversible action is required");
  if (new Set(actions).size !== actions.length) diagnostics.push("allowed actions must be unique");

  const conditionValues = new Map(
    when?.conditions.map((condition) => [condition.field, condition.value]) ?? []
  );
  for (const field of ["risk", "confidence", "observations"] as const) {
    if (!conditionValues.has(field)) diagnostics.push(`missing '${field}' threshold`);
  }
  if (conditionValues.size !== (when?.conditions.length ?? 0)) {
    diagnostics.push("threshold fields must not be repeated");
  }

  const risk = conditionValues.get("risk");
  const confidence = conditionValues.get("confidence");
  const observations = conditionValues.get("observations");
  if (risk !== undefined && (risk < 0 || risk > 1)) diagnostics.push("risk must be between 0 and 1");
  if (confidence !== undefined && (confidence < 0 || confidence > 1)) {
    diagnostics.push("confidence must be between 0 and 1");
  }
  if (observations !== undefined && (!Number.isInteger(observations) || observations < 1)) {
    diagnostics.push("observations must be a positive integer");
  }
  if (budget !== undefined && (!Number.isFinite(budget.amount) || budget.amount < 0)) {
    diagnostics.push("budget amount must be non-negative");
  }
  if (budget !== undefined && (!Number.isInteger(budget.period) || budget.period < 1)) {
    diagnostics.push("budget period must be a positive integer");
  }
  if (challenge !== undefined && (!Number.isInteger(challenge.duration) || challenge.duration < 1)) {
    diagnostics.push("challenge duration must be a positive integer");
  }

  if (
    diagnostics.length > 0 ||
    region === undefined ||
    metric === undefined ||
    budget === undefined ||
    challenge === undefined ||
    risk === undefined ||
    confidence === undefined ||
    observations === undefined
  ) {
    throw new TerraLexCompileError(diagnostics);
  }

  const candidate: CompiledPolicy = {
    language: "TerraLex",
    compilerVersion: 1,
    policyVersion: ast.version,
    name: ast.name,
    regionId: region.value,
    metric: metric.value,
    thresholds: {
      riskGte: risk,
      confidenceGte: confidence,
      observationsGte: observations
    },
    allowedActions: [...actions].sort(),
    budget: {
      maxAmount: budget.amount,
      asset: budget.asset,
      periodSeconds: seconds(budget.period, budget.unit)
    },
    challengeSeconds: seconds(challenge.duration, challenge.unit),
    safeguards: {
      communityChallenge: true,
      guardianPause: true,
      irreversibleForbidden: true
    }
  };

  const policy = compiledPolicySchema.parse(candidate);
  const serialized = canonicalJson(policy);
  const policyHash = `0x${createHash("sha256").update(serialized).digest("hex")}` as const;
  return { policy, canonicalJson: serialized, policyHash };
};

export const compileTerraLex = (source: string): PolicyBundle =>
  compileAst(parseTerraLex(source));

