CREATE TABLE compute.jobs (
  id uuid PRIMARY KEY,
  simulation_id uuid UNIQUE NOT NULL,
  status text NOT NULL,
  input_params jsonb NOT NULL,
  details text,
  step text,
  step_index integer,
  total_steps integer,
  calculation jsonb,
  travel_times jsonb,
  outputs jsonb NOT NULL DEFAULT '[]'::jsonb,
  result_bucket text,
  result_key text,
  error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  started_at timestamptz,
  finished_at timestamptz,
  -- The task-queue attempt that owns this row. Every write an attempt makes
  -- matches on this column, so a superseded attempt matches zero rows. NULL
  -- until the first attempt claims the row.
  owner_attempt integer
);

CREATE INDEX jobs_status_idx ON compute.jobs(status);
CREATE INDEX jobs_created_at_idx ON compute.jobs(created_at DESC);
