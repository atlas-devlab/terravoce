import { readFile, writeFile, mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { canonicalJson } from "@terravoce/protocol";
import { loadIrrigationReview } from "./irrigation.js";

const root = fileURLToPath(new URL("../../../", import.meta.url));
const command = process.argv[2];
if (command !== "replay" && command !== "verify") throw new Error("Use irrigation-cli.ts replay|verify");
const expected = await loadIrrigationReview(root);
const path = resolve(root, "docs/evidence/awash-irrigation/review.json");
if (command === "replay") {
  await mkdir(resolve(root, "docs/evidence/awash-irrigation"), { recursive: true });
  try {
    await writeFile(path, JSON.stringify(expected, null, 2) + "\n", { flag: "wx" });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error;
    if (canonicalJson(JSON.parse(await readFile(path, "utf8"))) !== canonicalJson(expected)) {
      throw new Error("Refusing to replace irrigation research evidence");
    }
  }
} else if (canonicalJson(JSON.parse(await readFile(path, "utf8"))) !== canonicalJson(expected)) {
  throw new Error("Irrigation review does not reproduce");
}
console.log(JSON.stringify({ verified: true, evidenceHash: expected.evidenceHash,
  scope: "research score and source commitments; run Python verify for native pixel replay",
  result: expected.result }));
