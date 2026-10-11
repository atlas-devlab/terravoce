import { resolve } from "node:path";
import { runAdvisor } from "./advisor.js";
import { saveAdvisory } from "./artifacts.js";
import { makePublicCases } from "./fixtures.js";
import { OllamaProvider } from "./ollama.js";

const model = process.env.ADVISOR_MODEL;
if (!model) throw new Error("Set ADVISOR_MODEL to an installed, benchmarked Ollama model tag");
const provider = new OllamaProvider(model, process.env.OLLAMA_URL, process.env.ADVISOR_MODEL_DIGEST);
const { config, cases } = await makePublicCases();
const scenario = cases[0]!;
const advisory = await runAdvisor(scenario.input, config, provider);
const folder = resolve(process.env.ADVISOR_OUTPUT ?? ".runtime/demo");
await saveAdvisory(folder, scenario.input, advisory);
console.log(JSON.stringify({ synthetic: true, oracle: "real local API via Fastify injection",
  artifactFolder: folder, advisory }, null, 2));
if (advisory.status !== "suggested") process.exitCode = 1;
