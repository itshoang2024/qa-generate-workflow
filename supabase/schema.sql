create table if not exists projects (
  id text primary key,
  name text not null,
  source_document text not null,
  created_at timestamptz not null default now()
);

create table if not exists runs (
  id text primary key,
  project_id text not null references projects(id),
  mode text not null,
  status text not null,
  current_stage text not null,
  coverage_report jsonb not null default '{}'::jsonb,
  timeline jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  finished_at timestamptz
);

create table if not exists gdd_sections (
  id text primary key,
  run_id text not null references runs(id) on delete cascade,
  section_id text not null,
  title text not null,
  level integer not null,
  parent_id text,
  text text not null default '',
  tables jsonb not null default '[]'::jsonb,
  flags jsonb not null default '[]'::jsonb,
  actionable boolean not null default true,
  actionability_reason text,
  unique(run_id, section_id)
);

create table if not exists features (
  id text primary key,
  run_id text not null references runs(id) on delete cascade,
  feature_id text not null,
  name text not null,
  summary text not null,
  feature_type text not null,
  source_sections jsonb not null,
  key_behaviors jsonb not null default '[]'::jsonb,
  dependencies jsonb not null default '[]'::jsonb,
  assignee text not null,
  confidence numeric not null,
  ambiguities jsonb not null default '[]'::jsonb,
  review_status text not null,
  unique(run_id, feature_id)
);

create table if not exists epics (
  id text primary key,
  run_id text not null references runs(id) on delete cascade,
  epic_id text not null,
  title text not null,
  description text not null,
  feature_ids jsonb not null,
  external_id text not null,
  review_status text not null,
  unique(run_id, epic_id),
  unique(external_id)
);

create table if not exists stories (
  id text primary key,
  run_id text not null references runs(id) on delete cascade,
  story_id text not null,
  epic_id text not null,
  title text not null,
  description text not null,
  feature_id text not null,
  acceptance_criteria jsonb not null default '[]'::jsonb,
  external_id text not null,
  review_status text not null,
  unique(run_id, story_id),
  unique(external_id)
);

create table if not exists qa_tasks (
  id text primary key,
  run_id text not null references runs(id) on delete cascade,
  task_id text not null,
  story_id text not null,
  epic_id text not null,
  feature_id text not null,
  title text not null,
  description text not null,
  assignee text not null,
  priority text not null,
  estimate text not null,
  source_sections jsonb not null,
  external_id text not null,
  confidence numeric not null,
  status text not null,
  review_status text not null,
  unique(run_id, task_id),
  unique(external_id)
);

create table if not exists test_cases (
  id text primary key,
  run_id text not null references runs(id) on delete cascade,
  test_case_id text not null,
  title text not null,
  type text not null,
  category text not null,
  priority text not null,
  preconditions jsonb not null,
  steps jsonb not null,
  expected_result text not null,
  related_task_id text not null,
  source_sections jsonb not null,
  external_id text not null,
  test_data jsonb not null default '{}'::jsonb,
  status text not null,
  review_status text not null,
  unique(run_id, test_case_id),
  unique(external_id)
);

create table if not exists validation_issues (
  id text primary key,
  run_id text not null references runs(id) on delete cascade,
  target_type text not null,
  target_id text not null,
  severity text not null,
  code text not null,
  message text not null,
  stage text not null,
  created_at timestamptz not null default now()
);

create table if not exists review_decisions (
  id text primary key,
  run_id text not null references runs(id) on delete cascade,
  target_type text not null,
  target_id text not null,
  decision text not null,
  reviewer text not null,
  comment text,
  patch jsonb,
  created_at timestamptz not null default now()
);

create table if not exists agent_runs (
  id text primary key,
  run_id text not null references runs(id) on delete cascade,
  agent_name text not null,
  stage text not null,
  input_snapshot jsonb not null,
  output_snapshot jsonb not null,
  provider text not null,
  created_at timestamptz not null default now()
);

create table if not exists sync_events (
  id text primary key,
  run_id text not null references runs(id) on delete cascade,
  target_type text not null,
  target_id text not null,
  external_id text not null,
  action text not null,
  provider text not null,
  status text not null,
  payload jsonb not null,
  retry_count integer not null default 0,
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_runs_project_id on runs(project_id);
create index if not exists idx_sections_run_id on gdd_sections(run_id);
create index if not exists idx_features_run_id on features(run_id);
create index if not exists idx_tasks_run_id on qa_tasks(run_id);
create index if not exists idx_test_cases_run_id on test_cases(run_id);
create index if not exists idx_sync_events_run_id_status on sync_events(run_id, status);

