/**
 * TypeScript mirror of the backend Pydantic models in
 * `backend/app/domain/models.py`. Kept in sync by hand — change a model on
 * the Python side, change it here, run `npx tsc --noEmit`.
 *
 * Conventions:
 * - Backend StrEnum classes become TS string-literal unions.
 * - Backend `datetime` fields become ISO 8601 strings.
 * - Backend `dict[str, Any]` becomes `Record<string, unknown>`.
 * - Backend `computed_field` (e.g. `Feature.lane`) is included on the read
 *   shape because it appears in the JSON envelope payload.
 */

// ---------------------------------------------------------------------------
// Enums (string literal unions)
// ---------------------------------------------------------------------------

export type RunMode = "NEW_GAME" | "DELTA";

export type RunStatus = "CREATED" | "RUNNING" | "COMPLETED" | "FAILED";

export type PipelineStage =
  | "S0_TRIGGER"
  | "S1_CONTEXT_LOADER"
  | "S2_AGENT_A"
  | "S3_VALIDATION_A"
  | "S4_AGENT_B"
  | "S5_VALIDATION_B_SYNC"
  | "S6_AGENT_C"
  | "S7_VALIDATION_C_SYNC"
  | "FINAL_COVERAGE";

export type FeatureType =
  | "gameplay_logic"
  | "ui_layout"
  | "level_puzzle"
  | "economy"
  | "backend_liveops"
  | "animation"
  | "tutorial"
  | "cross_cutting";

export type DeltaStatus = "NEW" | "MODIFIED" | "UNCHANGED" | "REMOVED";

export type Priority = "P0" | "P1" | "P2";

export type Estimate = "S" | "M" | "L";

export type ReviewStatus =
  | "PENDING"
  | "AUTO_APPROVED"
  | "APPROVED"
  | "REJECTED"
  | "NEEDS_REVIEW"
  | "BLOCKED";

export type ValidationSeverity =
  | "S1_CRITICAL"
  | "S2_RECOVERABLE"
  | "S3_INFORMATIONAL";

export type RiskSeverity = "S1" | "S2" | "S3";

export type SyncStatus = "PENDING" | "SUCCESS" | "FAILED" | "REPLAYED";

export type GDDDescriptionStatus = "PENDING" | "USER_PROVIDED" | "AI_GENERATED";

export type HIL0Action =
  | "provide_artifact"
  | "proceed_with_flag"
  | "skip_section";

export type TestCategory = "positive" | "negative" | "edge" | "integration";

export type TestType =
  | "functional"
  | "ui"
  | "integration"
  | "regression"
  | "performance";

export type RouterLane = "AUTO" | "BATCH" | "BLOCK";

export type HilTier = "HIL-0" | "HIL-1" | "HIL-2" | "HIL-3";

// ---------------------------------------------------------------------------
// Domain models
// ---------------------------------------------------------------------------

export interface Project {
  id: string;
  name: string;
  source_document: string;
  created_at: string;
}

export interface GDDDocument {
  id: string;
  project_id: string;
  run_id: string | null;
  version_id: string;
  description: string | null;
  description_status: GDDDescriptionStatus;
  parent_document_id: string | null;
  file_name: string;
  file_path: string;
  content_type: string;
  origin: string;
  size_bytes: number;
  sha256: string;
  created_at: string;
}

export interface StageEvent {
  stage: PipelineStage;
  status: string;
  message: string;
  created_at: string;
}

export interface DeltaReportBuckets {
  NEW: string[];
  MODIFIED: string[];
  UNCHANGED: string[];
  REMOVED: string[];
}

export interface DeltaReportSummary {
  new: number;
  modified: number;
  unchanged: number;
  removed: number;
}

export interface DeltaReport {
  status: "READY" | "NO_BASELINE" | string;
  current_document_id: string;
  current_version_id: string;
  previous_document_id: string | null;
  previous_version_id: string | null;
  buckets: DeltaReportBuckets;
  summary: DeltaReportSummary;
}

export interface CoverageReport {
  total_sections: number;
  actionable_sections: number;
  covered_sections: string[];
  uncovered_sections: string[];
  feature_count: number;
  task_count: number;
  test_case_count: number;
  validation_issue_count: number;
  tasks_by_assignee: Record<string, number>;
  tasks_by_priority: Record<string, number>;
  risk_summary: {
    total: number;
    by_severity: Record<string, number>;
    by_code: Record<string, number>;
  };
  sync_summary: {
    total: number;
    by_status: Record<string, number>;
    by_phase: Record<string, number>;
  };
  gdd_version_metadata: {
    gdd_document_id: string | null;
    source_version_id: string | null;
    source_metadata: Record<string, unknown>;
  };
  sign_off: {
    signed_off: boolean;
    signed_off_by: string | null;
    signed_off_at: string | null;
  };
}

export interface Run {
  id: string;
  project_id: string;
  mode: RunMode;
  status: RunStatus;
  current_stage: PipelineStage;
  session_memory: Record<string, unknown>;
  gdd_document_id: string | null;
  source_version_id: string | null;
  source_metadata: Record<string, unknown>;
  delta_report: DeltaReport | null;
  coverage_report: Partial<CoverageReport>;
  timeline: StageEvent[];
  signed_off_by: string | null;
  signed_off_at: string | null;
  created_at: string;
  updated_at: string;
  finished_at: string | null;
}

export interface GDDSection {
  id: string;
  run_id: string;
  section_id: string;
  title: string;
  level: number;
  parent_id: string | null;
  text: string;
  tables: string[][][];
  flags: string[];
  actionable: boolean;
  actionability_reason: string | null;
}

export interface HIL0Question {
  id: string;
  run_id: string;
  section_id: string;
  title: string;
  reason: string;
  question: string;
  allowed_actions: HIL0Action[];
  status: string;
  resolved_action: HIL0Action | null;
  created_at: string;
}

export interface HIL0Resolution {
  id: string;
  run_id: string;
  question_id: string;
  action: HIL0Action;
  reviewer: string;
  response: string | null;
  artifact_ref: string | null;
  created_at: string;
}

export interface Feature {
  id: string;
  run_id: string;
  feature_id: string;
  name: string;
  summary: string;
  feature_type: FeatureType;
  source_sections: string[];
  key_behaviors: string[];
  dependencies: string[];
  assignee: string;
  confidence: number;
  delta_status: DeltaStatus | null;
  dedup_flag: boolean;
  cross_cutting_flag: boolean;
  ambiguities: string[];
  review_status: ReviewStatus;
  /** Computed field on the backend — always present in the JSON response. */
  lane: RouterLane;
}

export interface Epic {
  id: string;
  run_id: string;
  epic_id: string;
  title: string;
  description: string;
  feature_ids: string[];
  external_id: string;
  review_status: ReviewStatus;
}

export interface Story {
  id: string;
  run_id: string;
  story_id: string;
  epic_id: string;
  title: string;
  description: string;
  feature_id: string;
  acceptance_criteria: string[];
  external_id: string;
  review_status: ReviewStatus;
}

export interface QATask {
  id: string;
  run_id: string;
  task_id: string;
  story_id: string;
  epic_id: string;
  feature_id: string;
  title: string;
  description: string;
  assignee: string;
  priority: Priority;
  estimate: Estimate;
  source_sections: string[];
  external_id: string;
  confidence: number;
  dedup_flag: boolean;
  cross_cutting_flag: boolean;
  status: string;
  review_status: ReviewStatus;
  /** Computed field on the backend — always present in the JSON response. */
  lane: RouterLane;
}

export interface TestCase {
  id: string;
  run_id: string;
  test_case_id: string;
  title: string;
  type: TestType;
  category: TestCategory;
  priority: Priority;
  preconditions: string[];
  steps: string[];
  expected_result: string;
  related_task_id: string;
  source_sections: string[];
  external_id: string;
  confidence: number;
  dedup_flag: boolean;
  cross_cutting_flag: boolean;
  test_data: Record<string, unknown>;
  status: string;
  review_status: ReviewStatus;
  /** Computed field on the backend — always present in the JSON response. */
  lane: RouterLane;
}

export interface ValidationIssue {
  id: string;
  run_id: string;
  target_type: string;
  target_id: string;
  severity: ValidationSeverity;
  code: string;
  message: string;
  stage: PipelineStage;
  created_at: string;
}

export interface RiskEvent {
  id: string;
  run_id: string;
  severity: RiskSeverity;
  code: string;
  summary: string;
  target_type: string;
  target_id: string;
  owner_action: string;
  created_at: string;
}

export interface ReviewDecision {
  id: string;
  run_id: string;
  target_type: string;
  target_id: string;
  decision: ReviewStatus;
  reviewer: string;
  comment: string | null;
  patch: Record<string, unknown> | null;
  created_at: string;
}

export interface AgentRun {
  id: string;
  run_id: string;
  agent_name: string;
  stage: PipelineStage;
  input_snapshot: Record<string, unknown>;
  output_snapshot: Record<string, unknown>;
  provider: string;
  created_at: string;
}

export interface SyncEvent {
  id: string;
  run_id: string;
  target_type: string;
  target_id: string;
  external_id: string;
  action: string;
  provider: string;
  status: SyncStatus;
  payload: Record<string, unknown> & {
    sync_phase?: "Sync-A" | "Sync-B" | "Sync-C" | string;
    notion_page_id?: string;
    database?: string;
    properties?: Record<string, unknown>;
  };
  retry_count: number;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReviewQueueItem {
  target_type: string;
  target_id: string;
  title: string;
  reviewer: string;
  lane: RouterLane;
  review_status: string;
  feature_id: string | null;
  epic_id: string | null;
  payload: Record<string, unknown>;
}

export interface ReviewQueueGroup {
  group_id: string;
  reviewer: string;
  feature_id: string | null;
  epic_id: string | null;
  item_count: number;
  items: ReviewQueueItem[];
}

export interface ReviewQueue {
  run_id: string;
  hil_tier: HilTier;
  group_by: string[];
  item_count: number;
  groups: ReviewQueueGroup[];
}

// ---------------------------------------------------------------------------
// Provider + health responses
// ---------------------------------------------------------------------------

export interface HealthResponse {
  status: "ok" | string;
  app_env: string;
  ai_provider: string;
  notion_provider: string;
  repository_provider: string;
}

export interface ProviderState {
  provider: string;
  credentials_ready: boolean;
}

export interface ProvidersStatus {
  ai: ProviderState;
  notion: ProviderState;
  repository: ProviderState;
}

// ---------------------------------------------------------------------------
// Mutation request / response shapes
// ---------------------------------------------------------------------------

export interface DemoRunRequest {
  preset?: "snake_escape" | string;
  mode?: RunMode;
  auto_approve?: boolean;
}

export interface ProjectCreateRequest {
  name: string;
  project_id?: string;
  source_document?: string;
}

/**
 * Exactly one of `project_id` or `project_name` must be supplied. Backend
 * raises 422 otherwise. The `gdd_file_ref` alias is accepted by the backend
 * but we use the canonical `gdd_file` field name.
 */
export interface TriggerRunRequest {
  project_id?: string;
  project_name?: string;
  gdd_file: string;
}

export interface TriggerRunResponse {
  run_id: string;
  project_id: string;
  gdd_file: string;
  mode: RunMode;
}

export interface LoadContextRequest {
  description?: string;
  content_type?: string;
  origin?: string;
}

export interface LoadContextResponse {
  run_id: string;
  project_id: string;
  mode: RunMode;
  gdd_document: GDDDocument;
  section_count: number;
  actionable_section_count: number;
  hil_0_questions: HIL0Question[];
  delta_report: DeltaReport | null;
}

export interface HIL0ResolutionRequest {
  question_id: string;
  action: HIL0Action;
  reviewer?: string;
  response?: string;
  artifact_ref?: string;
}

export interface HIL0BulkResolutionRequest {
  resolutions: HIL0ResolutionRequest[];
}

export interface ReviewDecisionRequest {
  run_id: string;
  target_type: string;
  target_id: string;
  decision: ReviewStatus;
  reviewer?: string;
  comment?: string;
  patch?: Record<string, unknown>;
}

export interface SignOffRequest {
  reviewer?: string;
}

export interface SyncReplayResponse {
  replayed_count: number;
  events: SyncEvent[];
}
