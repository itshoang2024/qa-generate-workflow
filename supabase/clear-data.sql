truncate table
  sync_events,
  agent_runs,
  risk_events,
  review_decisions,
  validation_issues,
  test_cases,
  qa_tasks,
  stories,
  epics,
  features,
  hil0_resolutions,
  hil0_questions,
  gdd_sections,
  gdd_documents,
  runs,
  projects
cascade;

notify pgrst, 'reload schema';
