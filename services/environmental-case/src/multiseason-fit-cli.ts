import { readFile } from "node:fs/promises";
import { fitMultiseason } from "./multiseason-fit.js";

if (process.argv.length !== 3) throw new Error("Usage: multiseason-fit-cli.ts prepared-training.json");
console.log(JSON.stringify(fitMultiseason(JSON.parse(await readFile(process.argv[2]!, "utf8")))));
