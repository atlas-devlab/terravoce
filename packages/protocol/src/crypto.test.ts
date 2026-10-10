import { generateKeyPairSync } from "node:crypto";

import { describe, expect, it } from "vitest";

import {
  observationId,
  signObservation,
  verifyObservation
} from "./crypto.js";

describe("signed observations", () => {
  it("verifies canonical Ed25519 payloads and rejects tampering", () => {
    const { privateKey, publicKey } = generateKeyPairSync("ed25519");
    const privateDer = privateKey.export({ format: "der", type: "pkcs8" }).toString("base64");
    const publicDer = publicKey.export({ format: "der", type: "spki" }).toString("base64");
    const unsigned = {
      sensorId: "sensor-po-01",
      regionId: "IT-PO-DELTA",
      metric: "water.oxygen.mg_l",
      value: 4.2,
      unit: "mg/L",
      observedAt: "2026-07-15T12:00:00.000+00:00",
      sequence: 42
    };
    const signed = signObservation(unsigned, privateDer);

    expect(verifyObservation(signed, publicDer)).toBe(true);
    expect(verifyObservation({ ...signed, value: 7.1 }, publicDer)).toBe(false);
    expect(observationId(unsigned)).toMatch(/^0x[0-9a-f]{64}$/);
  });
});

