import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { canonicalJson } from "@terravoce/protocol";
import { loadMultivariateData } from "./multivariate-data.js";
import { runMultivariateExperiment, verifyMultivariateReport } from "./multivariate.js";

const root = fileURLToPath(new URL("../../../", import.meta.url));
const data = await loadMultivariateData(resolve(root, "docs/datasets/usgs-willamette-multivariate"), resolve(root, "docs/datasets/usgs-willamette"));
const folder = resolve(process.argv[3] ?? resolve(root, "outputs/willamette-forecast"));
const path = resolve(folder, "forecast.json");
if (process.argv[2] === "replay") {
  const report = runMultivariateExperiment(data), content = canonicalJson(report) + "\n";
  await mkdir(folder, { recursive: true });
  try { await writeFile(path, content, { flag: "wx" }); }
  catch (error) {
    if (!(error instanceof Error) || !("code" in error) || error.code !== "EEXIST") throw error;
    if (await readFile(path, "utf8") !== content) throw new Error("Existing forecast artifact differs; use a new folder");
  }
  console.log(JSON.stringify({ artifact: path, selected: report.selected, holdout: report.selectedHoldout,
    improvementPercent: report.holdoutImprovementOverPersistencePercent, interval: report.interval,
    decision: report.decision, reportHash: report.reportHash }, null, 2));
} else if (process.argv[2] === "verify") {
  console.log(JSON.stringify(verifyMultivariateReport(data, JSON.parse(await readFile(path, "utf8"))), null, 2));
} else throw new Error("Use replay/verify [output-folder]");
