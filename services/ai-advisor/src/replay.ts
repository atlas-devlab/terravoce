import { readFile, stat } from "node:fs/promises";
import { resolve } from "node:path";
import { z } from "zod";
import { sensorRegistrationSchema } from "@terravoce/protocol";
import { runAdvisor } from "./advisor.js";
import { saveAdvisory } from "./artifacts.js";
import { OllamaProvider } from "./ollama.js";

const [inputPath, configPath] = process.argv.slice(2);
if (!inputPath || !configPath || !process.env.ADVISOR_MODEL) {
  throw new Error("Usage: ADVISOR_MODEL=<tag> pnpm replay <input.json> <operator-config.json>");
}
const readJson = async (path: string, limit: number): Promise<unknown> => {
  if ((await stat(path)).size > limit) throw new Error("Input file exceeds size limit");
  return JSON.parse(await readFile(path, "utf8"));
};
const input = await readJson(inputPath, 512 * 1024);
const config = z.strictObject({
  policySource: z.string().min(1).max(16_384),
  trustedSensors: z.array(sensorRegistrationSchema.strict()).max(32),
  timeoutMs: z.number().int().min(1).max(300_000).default(90_000)
}).parse(await readJson(configPath, 128 * 1024));
const provider = new OllamaProvider(process.env.ADVISOR_MODEL, process.env.OLLAMA_URL, process.env.ADVISOR_MODEL_DIGEST);
const advisory = await runAdvisor(input, config, provider);
await saveAdvisory(resolve(process.env.ADVISOR_OUTPUT ?? ".runtime/replay"), input, advisory);
console.log(JSON.stringify(advisory, null, 2));
if (advisory.code !== "VERIFIED_SUGGESTION" && advisory.code !== "MODEL_ABSTAINED") process.exitCode = 1;
