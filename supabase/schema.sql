create table if not exists projects (
  id text primary key,
  name text not null,
  source_document text not null default '',
  created_at timestamptz not null default now()
);

create table if not exists runs (
  id text primary key,
  project_id text not null references projects(id),
  mode text not null,
  status text not null,
  current_stage text not null,
  session_memory jsonb not null default '{}'::jsonb,
  gdd_document_id text,
  source_version_id text,
  source_metadata jsonb not null default '{}'::jsonb,
  delta_report jsonb,
  coverage_report jsonb not null default '{}'::jsonb,
  timeline jsonb not null default '[]'::jsonb,
  signed_off_by text,
  signed_off_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  finished_at timestamptz
);

alter table projects
  alter column source_document set default '';

alter table runs
  add column if not exists session_memory jsonb not null default '{}'::jsonb,
  add column if not exists gdd_document_id text,
  add column if not exists source_version_id text,
  add column if not exists source_metadata jsonb not null default '{}'::jsonb,
  add column if not exists delta_report jsonb,
  add column if not exists signed_off_by text,
  add column if not exists signed_off_at timestamptz;

create table if not exists gdd_documents (
  id text primary key,
  project_id text not null references projects(id) on delete cascade,
  run_id text references runs(id) on delete set null,
  version_id text not null,
  description text,
  description_status text not null default 'PENDING',
  parent_document_id text references gdd_documents(id),
  file_name text not null,
  file_path text not null,
  content_type text not null,
  origin text not null default 'local_reference',
  size_bytes integer not null,
  sha256 text not null,
  created_at timestamptz not null default now(),
  unique(project_id, version_id)
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

create table if not exists hil0_questions (
  id text primary key,
  run_id text not null references runs(id) on delete cascade,
  section_id text not null,
  title text not null,
  reason text not null,
  question text not null,
  allowed_actions jsonb not null default '[]'::jsonb,
  status text not null default 'OPEN',
  resolved_action text,
  created_at timestamptz not null default now()
);

create table if not exists hil0_resolutions (
  id text primary key,
  run_id text not null references runs(id) on delete cascade,
  question_id text not null references hil0_questions(id) on delete cascade,
  action text not null,
  reviewer text not null,
  response text,
  artifact_ref text,
  created_at timestamptz not null default now()
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
  dedup_flag boolean not null default false,
  cross_cutting_flag boolean not null default false,
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
  dedup_flag boolean not null default false,
  cross_cutting_flag boolean not null default false,
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
  confidence numeric not null default 1,
  dedup_flag boolean not null default false,
  cross_cutting_flag boolean not null default false,
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

create table if not exists risk_events (
  id text primary key,
  run_id text not null references runs(id) on delete cascade,
  severity text not null,
  code text not null,
  summary text not null,
  target_type text not null,
  target_id text not null,
  owner_action text not null,
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
alter table features
  add column if not exists dedup_flag boolean not null default false,
  add column if not exists cross_cutting_flag boolean not null default false;

alter table qa_tasks
  add column if not exists dedup_flag boolean not null default false,
  add column if not exists cross_cutting_flag boolean not null default false;

alter table test_cases
  add column if not exists confidence numeric not null default 1,
  add column if not exists dedup_flag boolean not null default false,
  add column if not exists cross_cutting_flag boolean not null default false;

create index if not exists idx_gdd_documents_project_version
  on gdd_documents(project_id, version_id);
create index if not exists idx_gdd_documents_parent_document_id
  on gdd_documents(parent_document_id);
create index if not exists idx_sections_run_id on gdd_sections(run_id);
create index if not exists idx_hil0_questions_run_id on hil0_questions(run_id);
create index if not exists idx_hil0_resolutions_run_id on hil0_resolutions(run_id);
create index if not exists idx_features_run_id on features(run_id);
create index if not exists idx_tasks_run_id on qa_tasks(run_id);
create index if not exists idx_test_cases_run_id on test_cases(run_id);
create index if not exists idx_risk_events_run_id on risk_events(run_id);
create index if not exists idx_sync_events_run_id_status on sync_events(run_id, status);

notify pgrst, 'reload schema';
