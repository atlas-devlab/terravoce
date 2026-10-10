import {
  createHash,
  createPrivateKey,
  createPublicKey,
  sign,
  verify
} from "node:crypto";

import {
  signedObservationSchema,
  unsignedObservationSchema,
  type SignedObservation,
  type UnsignedObservation
} from "./schemas.js";

const canonicalize = (value: unknown): unknown => {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, child]) => [key, canonicalize(child)])
    );
  }
  return value;
};

export const canonicalJson = (value: unknown): string =>
  JSON.stringify(canonicalize(value));

export const sha256Hex = (value: string | Uint8Array): `0x${string}` =>
  `0x${createHash("sha256").update(value).digest("hex")}`;

export const observationPayload = (observation: UnsignedObservation): string =>
  canonicalJson(unsignedObservationSchema.parse(observation));

export const observationId = (observation: UnsignedObservation): `0x${string}` =>
  sha256Hex(observationPayload(observation));

export const signObservation = (
  observation: UnsignedObservation,
  privateKeyDerBase64: string
): SignedObservation => {
  const parsed = unsignedObservationSchema.parse(observation);
  const privateKey = createPrivateKey({
    key: Buffer.from(privateKeyDerBase64, "base64"),
    format: "der",
    type: "pkcs8"
  });
  const signature = sign(null, Buffer.from(observationPayload(parsed)), privateKey);
  return signedObservationSchema.parse({
    ...parsed,
    signature: signature.toString("base64")
  });
};

export const verifyObservation = (
  observation: SignedObservation,
  publicKeyDerBase64: string
): boolean => {
  const parsed = signedObservationSchema.parse(observation);
  const { signature, ...unsigned } = parsed;
  const publicKey = createPublicKey({
    key: Buffer.from(publicKeyDerBase64, "base64"),
    format: "der",
    type: "spki"
  });
  return verify(
    null,
    Buffer.from(observationPayload(unsigned)),
    publicKey,
    Buffer.from(signature, "base64")
  );
};

