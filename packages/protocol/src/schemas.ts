import { z } from "zod";

export const unsignedObservationSchema = z.object({
  sensorId: z.string().min(3).max(128),
  regionId: z.string().min(2).max(128),
  metric: z.string().regex(/^[a-z][a-z0-9_.-]{1,127}$/),
  value: z.number().finite(),
  unit: z.string().min(1).max(32),
  observedAt: z.iso.datetime({ offset: true }),
  sequence: z.number().int().nonnegative().safe()
});

export const signedObservationSchema = unsignedObservationSchema.extend({
  signature: z.string().base64()
});

export const sensorRegistrationSchema = z.object({
  sensorId: z.string().min(3).max(128),
  regionId: z.string().min(2).max(128),
  publicKeyDerBase64: z.string().base64(),
  label: z.string().min(1).max(160)
});

export const assessmentSchema = z.object({
  assessmentId: z.string().regex(/^0x[0-9a-f]{64}$/),
  regionId: z.string().min(2).max(128),
  metric: z.string().min(2).max(128),
  modelVersion: z.string().min(1).max(128),
  generatedAt: z.iso.datetime({ offset: true }),
  observationCount: z.number().int().positive(),
  currentValue: z.number().finite(),
  forecastValue: z.number().finite(),
  forecastHorizonSeconds: z.number().int().positive(),
  slopePerHour: z.number().finite(),
  anomalyScore: z.number().min(0).max(1),
  confidence: z.number().min(0).max(1),
  risk: z.number().min(0).max(1),
  evidenceHash: z.string().regex(/^0x[0-9a-f]{64}$/)
});

export const actionDraftSchema = z.object({
  regionId: z.string().min(2).max(128),
  evidenceHash: z.string().regex(/^0x[0-9a-f]{64}$/),
  policyHash: z.string().regex(/^0x[0-9a-f]{64}$/),
  action: z.string().min(1).max(128),
  reversible: z.literal(true),
  requestedAmount: z.number().nonnegative(),
  asset: z.string().regex(/^[A-Z][A-Z0-9]{1,11}$/),
  challengeSeconds: z.number().int().positive()
});

export type UnsignedObservation = z.infer<typeof unsignedObservationSchema>;
export type SignedObservation = z.infer<typeof signedObservationSchema>;
export type SensorRegistration = z.infer<typeof sensorRegistrationSchema>;
export type Assessment = z.infer<typeof assessmentSchema>;
export type ActionDraft = z.infer<typeof actionDraftSchema>;

