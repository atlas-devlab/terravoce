import { mkdir, writeFile, readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { canonicalJson, sha256Hex } from "@terravoce/protocol";
import type { Advisory } from "./schemas.js";

export const saveAdvisory = async (folder: string, input: unknown, advisory: Advisory): Promise<void> => {
  if (sha256Hex(`advisor-input-v1:${canonicalJson(input)}`) !== advisory.inputHash) {
    throw new Error("Advisory input hash mismatch");
  }
  const { advisoryHash, ...core } = advisory;
  if (sha256Hex(`advisory-v1:${canonicalJson(core)}`) !== advisoryHash) throw new Error("Advisory hash mismatch");
  const directory = resolve(folder);
  await mkdir(directory, { recursive: true });
  // Content-addressed names and exclusive creation: repeated writes cannot replace an artifact.
  for (const [name, value] of [[`input-${advisory.inputHash}.json`, input],
    [`advisory-${advisoryHash}.json`, advisory]] as const) {
    const path = resolve(directory, name);
    const content = canonicalJson(value) + "\n";
    try { await writeFile(path, content, { flag: "wx" }); }
    catch (error) {
      if (!(error instanceof Error) || !("code" in error) || error.code !== "EEXIST") throw error;
      if (await readFile(path, "utf8") !== content) throw new Error("Artifact collision or alteration");
    }
  }
};
