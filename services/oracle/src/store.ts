import type {
  Assessment,
  SensorRegistration,
  SignedObservation
} from "@terravoce/protocol";

import { DomainError } from "./errors.js";

export interface StoredSensor extends SensorRegistration {
  active: boolean;
}

export interface StoredObservation {
  observationId: `0x${string}`;
  observation: SignedObservation;
}

export interface ObservationStore {
  registerSensor(sensor: SensorRegistration): Promise<StoredSensor>;
  getSensor(sensorId: string): Promise<StoredSensor | undefined>;
  addObservation(entry: StoredObservation): Promise<void>;
  listObservations(
    regionId: string,
    metric: string,
    limit: number
  ): Promise<StoredObservation[]>;
  saveAssessment(assessment: Assessment): Promise<void>;
  latestAssessment(regionId: string, metric: string): Promise<Assessment | undefined>;
  close(): Promise<void>;
}

export class MemoryObservationStore implements ObservationStore {
  private readonly sensors = new Map<string, StoredSensor>();
  private readonly observations = new Map<`0x${string}`, StoredObservation>();
  private readonly sequenceKeys = new Set<string>();
  private readonly assessments = new Map<string, Assessment>();

  public async registerSensor(sensor: SensorRegistration): Promise<StoredSensor> {
    if (this.sensors.has(sensor.sensorId)) {
      throw new DomainError("sensor already exists", 409, "SENSOR_EXISTS");
    }
    const stored = { ...sensor, active: true };
    this.sensors.set(sensor.sensorId, stored);
    return stored;
  }

  public async getSensor(sensorId: string): Promise<StoredSensor | undefined> {
    return this.sensors.get(sensorId);
  }

  public async addObservation(entry: StoredObservation): Promise<void> {
    const sequenceKey = `${entry.observation.sensorId}:${entry.observation.sequence}`;
    if (this.observations.has(entry.observationId) || this.sequenceKeys.has(sequenceKey)) {
      throw new DomainError("observation replay detected", 409, "OBSERVATION_REPLAY");
    }
    this.observations.set(entry.observationId, entry);
    this.sequenceKeys.add(sequenceKey);
  }

  public async listObservations(
    regionId: string,
    metric: string,
    limit: number
  ): Promise<StoredObservation[]> {
    return [...this.observations.values()]
      .filter(
        ({ observation }) =>
          observation.regionId === regionId && observation.metric === metric
      )
      .sort((left, right) => {
        const time =
          Date.parse(left.observation.observedAt) - Date.parse(right.observation.observedAt);
        if (time !== 0) return time;
        return left.observationId.localeCompare(right.observationId);
      })
      .slice(-limit);
  }

  public async saveAssessment(assessment: Assessment): Promise<void> {
    this.assessments.set(`${assessment.regionId}:${assessment.metric}`, assessment);
  }

  public async latestAssessment(
    regionId: string,
    metric: string
  ): Promise<Assessment | undefined> {
    return this.assessments.get(`${regionId}:${metric}`);
  }

  public async close(): Promise<void> {}
}

