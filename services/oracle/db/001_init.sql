CREATE TABLE IF NOT EXISTS sensors (
  sensor_id TEXT PRIMARY KEY,
  region_id TEXT NOT NULL,
  public_key_der_base64 TEXT NOT NULL,
  label TEXT NOT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS observations (
  observation_id CHAR(66) PRIMARY KEY,
  sensor_id TEXT NOT NULL REFERENCES sensors(sensor_id),
  region_id TEXT NOT NULL,
  metric TEXT NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL,
  sequence BIGINT NOT NULL,
  body JSONB NOT NULL,
  received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (sensor_id, sequence)
);

CREATE INDEX IF NOT EXISTS observations_region_metric_time
  ON observations (region_id, metric, observed_at DESC);

CREATE TABLE IF NOT EXISTS assessments (
  assessment_id CHAR(66) PRIMARY KEY,
  region_id TEXT NOT NULL,
  metric TEXT NOT NULL,
  generated_at TIMESTAMPTZ NOT NULL,
  body JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS assessments_region_metric_time
  ON assessments (region_id, metric, generated_at DESC);

