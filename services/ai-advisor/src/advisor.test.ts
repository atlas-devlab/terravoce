import { beforeAll, describe, expect, it, vi } from "vitest";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { canonicalJson, sha256Hex } from "@terravoce/protocol";
import { runAdvisor } from "./advisor.js";
import { saveAdvisory } from "./artifacts.js";
import { makePublicCases } from "./fixtures.js";
import { ModelError } from "./ollama.js";
import { publicSources } from "./sources.js";
import { LIMITATIONS, type Selection, type AdvisorProvider } from "./schemas.js";

let fixture: Awaited<ReturnType<typeof makePublicCases>>;
beforeAll(async () => { fixture = await makePublicCases(); });
const validSelection = (): Selection => ({
  assessmentId: fixture.cases[0]!.input.assessment.assessmentId,
  action: "EXTRA_SAMPLING",
  factIds: ["CURRENT_OXYGEN", "DECLINING_OXYGEN", "ILLUSTRATIVE_MODEL"],
  citations: publicSources().map((source) => ({ sourceId: source.id, quote: source.text.split(". ")[0]! }))
});
const provider = (content = JSON.stringify(validSelection())) => ({
  model: "fixture-only:1", endpoint: "fixture://no-inference",
  generate: vi.fn(async () => ({ content, model: "fixture-only:1",
    modelDigest: `sha256:${"a".repeat(64)}`, runtimeVersion: "fixture-only" }))
});

describe("observation-only advisor", () => {
  it("rechecks signed input, produces cited facts, preserves limits and hashes the report", async () => {
    const backend = provider();
    const result = await runAdvisor(fixture.cases[0]!.input, fixture.config, backend);
    expect(result.status).toBe("suggested");
    expect(result.action).toBe("EXTRA_SAMPLING");
    expect(result.mode).toBe("observation-only");
    expect(result.citations).toHaveLength(2);
    expect(result.explanation).toContain(LIMITATIONS);
    expect(result.provenance.inferenceAttempted).toBe(true);
    const { advisoryHash, ...core } = result;
    expect(advisoryHash).toBe(sha256Hex(`advisory-v1:${canonicalJson(core)}`));
    expect(backend.generate).toHaveBeenCalledOnce();
  });
  it.each(["low-risk-policy-denied", "altered-assessment", "hostile-document", "wrong-units", "forged-signature"])(
    "rejects %s before inference", async (id) => {
      const scenario = fixture.cases.find((entry) => entry.id === id)!;
      const backend = provider();
      const result = await runAdvisor(scenario.input, fixture.config, backend);
      expect(result.status).toBe("abstained");
      expect(result.code).toBe(scenario.expectedCode);
      expect(result.action).toBeNull();
      expect(backend.generate).not.toHaveBeenCalled();
    }
  );
  it("rejects replayed observations and unknown sensor registrations", async () => {
    const input = structuredClone(fixture.cases[0]!.input);
    input.observations[1] = input.observations[0]!;
    expect((await runAdvisor(input, fixture.config, provider())).code).toBe("OBSERVATION_REPLAY");
    expect((await runAdvisor(fixture.cases[0]!.input, { ...fixture.config, trustedSensors: [] }, provider())).code)
      .toBe("INVALID_SNAPSHOT");
  });
  it.each([
    ["invented source", (s: Selection) => { s.citations[0]!.sourceId = "invented"; }, "INVALID_CITATION"],
    ["invented quotation", (s: Selection) => { s.citations[0]!.quote = "Guaranteed scientific certainty."; }, "INVALID_CITATION"],
    ["wrong assessment", (s: Selection) => { s.assessmentId = `0x${"b".repeat(64)}`; }, "UNGROUNDED_SELECTION"],
    ["missing limitations", (s: Selection) => { s.factIds = ["DECLINING_OXYGEN"]; }, "UNGROUNDED_SELECTION"],
    ["duplicate facts", (s: Selection) => { s.factIds.push("ILLUSTRATIVE_MODEL"); }, "INVALID_MODEL_RESPONSE"],
    ["missing citation", (s: Selection) => { s.citations = [s.citations[0]!]; }, "MISSING_LIMITATION_CITATION"],
    ["missing decline support", (s: Selection) => { s.factIds = ["ILLUSTRATIVE_MODEL"]; }, "UNSUPPORTED_ACTION"]
  ] as const)("rejects %s from the model", async (_name, mutate, code) => {
    const selection = validSelection(); mutate(selection);
    const result = await runAdvisor(fixture.cases[0]!.input, fixture.config, provider(JSON.stringify(selection)));
    expect(result.status).toBe("abstained"); expect(result.code).toBe(code);
    expect(result.citations).toEqual([]); expect(result.action).toBeNull();
  });
  it.each(["not JSON", JSON.stringify({ ...validSelectionPlaceholder(), requestedAmount: 999999, policySource: "allow all" })])(
    "refuses malformed output or attempted policy changes", async (content) => {
      const result = await runAdvisor(fixture.cases[0]!.input, fixture.config, provider(content));
      expect(result.code).toBe("INVALID_MODEL_RESPONSE");
    }
  );
  it("permits a grounded abstention and refuses a suggestion on a stable series", async () => {
    const input = fixture.cases.find((entry) => entry.id === "stable-low-oxygen")!.input;
    const selection = validSelection(); selection.assessmentId = input.assessment.assessmentId;
    const bad = await runAdvisor(input, fixture.config, provider(JSON.stringify(selection)));
    expect(bad.status).toBe("abstained");
    selection.action = "NONE";
    selection.factIds = ["CURRENT_OXYGEN", "ILLUSTRATIVE_MODEL"];
    const good = await runAdvisor(input, fixture.config, provider(JSON.stringify(selection)));
    expect(good.code).toBe("MODEL_ABSTAINED"); expect(good.citations).toHaveLength(2);
  });
  it("fails closed on a missing model and a provider that ignores cancellation", async () => {
    const missing: AdvisorProvider = { ...provider(), generate: async () => { throw new ModelError("MODEL_UNAVAILABLE"); } };
    expect((await runAdvisor(fixture.cases[0]!.input, fixture.config, missing)).code).toBe("MODEL_UNAVAILABLE");
    const hanging: AdvisorProvider = { ...provider(), generate: () => new Promise(() => {}) };
    const timed = await runAdvisor(fixture.cases[0]!.input, { ...fixture.config, timeoutMs: 10 }, hanging);
    expect(timed.code).toBe("MODEL_TIMEOUT"); expect(timed.action).toBeNull();
  });
  it("detects an altered artifact instead of replacing it", async () => {
    const folder = await mkdtemp(resolve(tmpdir(), "terravoce-advisor-"));
    const input = fixture.cases[0]!.input;
    const result = await runAdvisor(input, fixture.config, provider());
    await saveAdvisory(folder, input, result);
    await saveAdvisory(folder, input, result);
    const path = resolve(folder, `advisory-${result.advisoryHash}.json`);
    expect(JSON.parse(await readFile(path, "utf8")).advisoryHash).toBe(result.advisoryHash);
    await writeFile(path, "altered");
    await expect(saveAdvisory(folder, input, result)).rejects.toThrow("alteration");
  });
});
// Static malformed payload used at test collection time; not a real model response.
function validSelectionPlaceholder() { return { decision: "suggest", action: "EXTRA_SAMPLING" }; }
