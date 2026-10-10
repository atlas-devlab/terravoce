import { generateKeyPairSync } from "node:crypto";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

import { signObservation } from "@terravoce/protocol";

import { buildApp } from "./app.js";
import { MemoryObservationStore } from "./store.js";

const fixedNow = new Date("2026-07-15T12:00:00.000Z");
const policySource = await readFile(resolve("../../policies/po-water-v1.terra"), "utf8");
const app = buildApp({
  store: new MemoryObservationStore(),
  policySource,
  adminToken: "demo-admin",
  oracleToken: "demo-oracle",
  now: () => fixedNow
});

const { privateKey, publicKey } = generateKeyPairSync("ed25519");
const privateKeyDerBase64 = privateKey
  .export({ format: "der", type: "pkcs8" })
  .toString("base64");
const publicKeyDerBase64 = publicKey
  .export({ format: "der", type: "spki" })
  .toString("base64");

await app.inject({
  method: "POST",
  url: "/v1/sensors",
  headers: { "x-admin-token": "demo-admin" },
  payload: {
    sensorId: "sensor-po-demo-01",
    regionId: "IT-PO-DELTA",
    publicKeyDerBase64,
    label: "Po delta dissolved oxygen demo"
  }
});

for (let sequence = 0; sequence < 12; sequence += 1) {
  const observedAt = new Date(fixedNow.getTime() - (11 - sequence) * 60 * 60_000);
  const observation = signObservation(
    {
      sensorId: "sensor-po-demo-01",
      regionId: "IT-PO-DELTA",
      metric: "water.oxygen.mg_l",
      value: 7 - sequence * 0.3,
      unit: "mg/L",
      observedAt: observedAt.toISOString(),
      sequence
    },
    privateKeyDerBase64
  );
  const response = await app.inject({
    method: "POST",
    url: "/v1/observations",
    payload: observation
  });
  if (response.statusCode !== 202) throw new Error(response.body);
}

const result = await app.inject({
  method: "POST",
  url: "/v1/assessments/run",
  headers: { "x-oracle-token": "demo-oracle" },
  payload: {
    regionId: "IT-PO-DELTA",
    metric: "water.oxygen.mg_l",
    forecastHorizonHours: 24,
    requestedAction: "WATER_AERATION",
    requestedAmount: 180,
    asset: "USDC"
  }
});

console.log(JSON.stringify(result.json(), null, 2));
await app.close();

