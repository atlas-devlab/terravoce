import { generateKeyPairSync } from "node:crypto";

import { signObservation } from "@terravoce/protocol";
import { describe, expect, it } from "vitest";

import { buildApp } from "./app.js";
import { analyzeObservations } from "./analysis.js";
import { MemoryObservationStore, type StoredObservation } from "./store.js";

const policySource = `
policy "po-water-oxygen" version 1 {
  region "IT-PO-DELTA";
  metric "water.oxygen.mg_l";
  when risk >= 0.72 and confidence >= 0.80 and observations >= 5;
  allow "WATER_AERATION" reversible;
  budget 250 USDC per 7 days;
  challenge 24 hours;
  require community challenge;
  require guardian pause;
  forbid irreversible;
}`;

const makeKeys = () => {
  const { privateKey, publicKey } = generateKeyPairSync("ed25519");
  return {
    privateKey: privateKey.export({ format: "der", type: "pkcs8" }).toString("base64"),
    publicKey: publicKey.export({ format: "der", type: "spki" }).toString("base64")
  };
};

describe("oracle API", () => {
  it("verifies signatures and rejects replay or tampering", async () => {
    const keys = makeKeys();
    const now = new Date("2026-07-15T12:00:00.000Z");
    const app = buildApp({
      store: new MemoryObservationStore(),
      policySource,
      adminToken: "admin-secret",
      oracleToken: "oracle-secret",
      now: () => now
    });
    await app.inject({
      method: "POST",
      url: "/v1/sensors",
      headers: { "x-admin-token": "admin-secret" },
      payload: {
        sensorId: "sensor-po-01",
        regionId: "IT-PO-DELTA",
        publicKeyDerBase64: keys.publicKey,
        label: "Po oxygen sensor"
      }
    });
    const observation = signObservation(
      {
        sensorId: "sensor-po-01",
        regionId: "IT-PO-DELTA",
        metric: "water.oxygen.mg_l",
        value: 4.2,
        unit: "mg/L",
        observedAt: now.toISOString(),
        sequence: 1
      },
      keys.privateKey
    );

    const accepted = await app.inject({
      method: "POST",
      url: "/v1/observations",
      payload: observation
    });
    expect(accepted.statusCode).toBe(202);

    const replay = await app.inject({
      method: "POST",
      url: "/v1/observations",
      payload: observation
    });
    expect(replay.statusCode).toBe(409);

    const tampered = await app.inject({
      method: "POST",
      url: "/v1/observations",
      payload: { ...observation, value: 9.9, sequence: 2 }
    });
    expect(tampered.statusCode).toBe(401);
    await app.close();
  });

  it("reproduces evidence hashes and emits an allowed TerraLex action", async () => {
    const keys = makeKeys();
    const now = new Date("2026-07-15T12:00:00.000Z");
    const store = new MemoryObservationStore();
    const app = buildApp({
      store,
      policySource,
      adminToken: "admin-secret",
      oracleToken: "oracle-secret",
      now: () => now
    });
    await app.inject({
      method: "POST",
      url: "/v1/sensors",
      headers: { "x-admin-token": "admin-secret" },
      payload: {
        sensorId: "sensor-po-02",
        regionId: "IT-PO-DELTA",
        publicKeyDerBase64: keys.publicKey,
        label: "Po oxygen sensor"
      }
    });

    for (let sequence = 0; sequence < 12; sequence += 1) {
      const observedAt = new Date(now.getTime() - (11 - sequence) * 60 * 60_000);
      const observation = signObservation(
        {
          sensorId: "sensor-po-02",
          regionId: "IT-PO-DELTA",
          metric: "water.oxygen.mg_l",
          value: 7 - sequence * 0.3,
          unit: "mg/L",
          observedAt: observedAt.toISOString(),
          sequence
        },
        keys.privateKey
      );
      expect(
        (
          await app.inject({
            method: "POST",
            url: "/v1/observations",
            payload: observation
          })
        ).statusCode
      ).toBe(202);
    }

    const observations = await store.listObservations(
      "IT-PO-DELTA",
      "water.oxygen.mg_l",
      100
    );
    const forward = analyzeObservations(observations, 24 * 3_600);
    const reverse = analyzeObservations([...observations].reverse(), 24 * 3_600);
    expect(forward.evidenceHash).toBe(reverse.evidenceHash);
    expect(forward.forecastValue).toBeGreaterThanOrEqual(0);

    const response = await app.inject({
      method: "POST",
      url: "/v1/assessments/run",
      headers: { "x-oracle-token": "oracle-secret" },
      payload: {
        regionId: "IT-PO-DELTA",
        metric: "water.oxygen.mg_l",
        forecastHorizonHours: 24,
        requestedAction: "WATER_AERATION",
        requestedAmount: 180,
        asset: "USDC"
      }
    });
    expect(response.statusCode).toBe(201);
    const body = response.json();
    expect(body.decision.allowed).toBe(true);
    expect(body.actionDraft.reversible).toBe(true);
    expect(body.assessment.evidenceHash).toBe(forward.evidenceHash);
    await app.close();
  });
});
