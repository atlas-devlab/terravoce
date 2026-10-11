import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { runAdvisor } from "./advisor.js";
import { saveAdvisory } from "./artifacts.js";
import { makePublicCases } from "./fixtures.js";
import { OllamaProvider } from "./ollama.js";
import { canonicalJson, sha256Hex } from "@terravoce/protocol";
import type { AdvisorProvider } from "./schemas.js";

const models = (process.env.ADVISOR_MODELS ?? "qwen3:0.6b,qwen3:1.7b").split(",");
const repetitions = Number(process.env.ADVISOR_REPETITIONS ?? 2);
if (!Number.isInteger(repetitions) || repetitions < 1 || repetitions > 10) throw new Error("Invalid repetitions");
const { config, cases } = await makePublicCases();
const folder = resolve(process.env.ADVISOR_OUTPUT ?? `.runtime/benchmark-${Date.now()}`);
await mkdir(folder, { recursive: true });
// Public registrations only, no sensor private key. This is fixture trust configuration.
await writeFile(resolve(folder, "fixture-config.json"), JSON.stringify(config, null, 2), { flag: "wx" });
interface BenchmarkRow {
  model: string; repetition: number; case: string; expected: string; status: string;
  code: string; pass: boolean; inferenceAttempted: boolean; latencyMs: number;
  modelDigest: string | null; runtimeVersion: string | null; verifiedCitations: number; advisoryHash: string;
}
const rows: BenchmarkRow[] = [];
for (const model of models) {
  const backend = new OllamaProvider(model, process.env.OLLAMA_URL);
  const provider: AdvisorProvider = {
    model: backend.model, endpoint: backend.endpoint,
    generate: async (request, signal) => {
      const result = await backend.generate(request, signal);
      const trace = canonicalJson({ request, result });
      const path = resolve(folder, `model-${sha256Hex(trace)}.json`);
      try { await writeFile(path, trace + "\n", { flag: "wx" }); }
      catch (error) { if (!(error instanceof Error) || !("code" in error) || error.code !== "EEXIST") throw error; }
      return result;
    }
  };
  for (let repetition = 1; repetition <= repetitions; repetition += 1) {
    for (const scenario of cases) {
      const advisory = await runAdvisor(scenario.input, config, provider);
      await saveAdvisory(folder, scenario.input, advisory);
      const row = { model, repetition, case: scenario.id, expected: scenario.expected,
        status: advisory.status, code: advisory.code,
        pass: advisory.status === scenario.expected && advisory.code === scenario.expectedCode,
        inferenceAttempted: advisory.provenance.inferenceAttempted,
        latencyMs: advisory.provenance.latencyMs, modelDigest: advisory.provenance.modelDigest,
        runtimeVersion: advisory.provenance.runtimeVersion,
        verifiedCitations: advisory.citations.length, advisoryHash: advisory.advisoryHash };
      rows.push(row);
      console.log(JSON.stringify(row));
    }
  }
}
const summaries = models.map((model) => {
  const own = rows.filter((row) => row.model === model);
  const inference = own.filter((row) => row.inferenceAttempted);
  return { model, total: own.length, passed: own.filter((row) => row.pass).length,
    inferenceCases: inference.length, inferencePassed: inference.filter((row) => row.pass).length,
    meanInferenceMs: Math.round(inference.reduce((sum, row) => sum + row.latencyMs, 0) / inference.length),
    maxInferenceMs: Math.max(...inference.map((row) => row.latencyMs)),
    modelDigests: [...new Set(inference.map((row) => row.modelDigest))] };
});
const candidates = summaries.filter((entry) => entry.passed === entry.total && entry.inferencePassed === entry.inferenceCases)
  .sort((a, b) => a.meanInferenceMs - b.meanInferenceMs);
const report = { version: "advisor-benchmark-v1", synthetic: true, repetitions,
  generatedAt: new Date().toISOString(), limitations: "Small synthetic suite. Not a scientific, multilingual or adversarial robustness validation. Guard rejections are reported separately from actual inference.",
  selectedModel: candidates[0]?.model ?? null, summaries, rows };
await writeFile(resolve(folder, "benchmark.json"), JSON.stringify(report, null, 2), { flag: "wx" });
console.log(JSON.stringify({ folder, selectedModel: report.selectedModel, summaries }, null, 2));
if (!report.selectedModel) process.exitCode = 1;
