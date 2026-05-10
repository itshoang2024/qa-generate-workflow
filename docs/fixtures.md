# Fixture Guide

## Purpose

`data/snake_escape_fixture.json` is the deterministic mock-agent source for the Phase 1 demo. It stands in for Agent A and Agent B output. Agent C test cases are generated from tasks at runtime.

Edit this file carefully: it drives demo counts, validation behavior, mock Notion payloads, and tests.

## Fixture Responsibilities

The fixture defines:

- `ambiguities`: known GDD ambiguity notes.
- `features`: mock Agent A feature inventory.
- `epics`: mock Agent B epic/story/task breakdown.

It does not define test cases directly. `MockAgentClient.generate_test_cases()` creates four test cases per task.

## Feature Contract

Each feature entry must match the `Feature` model fields required by `backend/app/domain/models.py`:

```json
{
  "feature_id": "F-001",
  "name": "Tap-to-Move and Health Rules",
  "summary": "Short grounded summary.",
  "feature_type": "gameplay_logic",
  "source_sections": ["§2.3"],
  "key_behaviors": ["Clear behavior"],
  "dependencies": [],
  "confidence": 0.93,
  "ambiguities": []
}
```

`assignee` is not stored in the feature fixture. It is derived from `feature_type` through `QA_ASSIGNEE_BY_FEATURE_TYPE`.

## Epic, Story, And Task Contract

Each epic contains stories, and each story contains tasks:

```json
{
  "epic_id": "E-CORE-GAMEPLAY",
  "title": "Core Gameplay QA",
  "description": "Validate movement and lives.",
  "feature_ids": ["F-001"],
  "external_id": "snake-escape-E-CORE-GAMEPLAY",
  "stories": [
    {
      "story_id": "S-001",
      "title": "Player resolves a board",
      "description": "As a player...",
      "feature_id": "F-001",
      "acceptance_criteria": ["Clear snake exits"],
      "external_id": "snake-escape-E-CORE-GAMEPLAY-S-001",
      "tasks": [
        {
          "task_id": "T-001",
          "feature_id": "F-001",
          "title": "Verify clear-path snake exits",
          "description": "Check behavior.",
          "assignee": "Ngoc Anh",
          "priority": "P0",
          "estimate": "S",
          "source_sections": ["§2.3"],
          "external_id": "snake-escape-F-001-T-01",
          "confidence": 0.92
        }
      ]
    }
  ]
}
```

## Allowed Values

Feature types must match `FeatureType`:

- `gameplay_logic`
- `ui_layout`
- `level_puzzle`
- `economy`
- `backend_liveops`
- `animation`
- `tutorial`

Priorities:

- `P0`
- `P1`
- `P2`

Estimates:

- `S`
- `M`
- `L`

Assignees must match the seeded roster:

- `Ngoc Anh`
- `Minh`
- `Huy`
- `Linh`
- `Quan`

## Source Sections

`source_sections` must match parser output from the Snake GDD. Current parser IDs use `§` prefix, such as:

- `§2.3`
- `§4.1`
- `§12.8`

Unknown section IDs become validation issues. If you edit source IDs, run parser and pipeline tests.

## Expected Demo Counts

Current fixture and runtime generation produce:

- 8 features
- 5 epics
- 5 stories
- 11 QA tasks
- 44 generated test cases

These counts are asserted by `backend/tests/test_pipeline.py` and `backend/tests/test_api.py`.

## Editing Checklist

After editing `data/snake_escape_fixture.json`:

```powershell
cd D:\Code\SUNS-RISER\qa-generate-workflow
conda activate qa-generator
cd backend
pytest tests/test_pipeline.py tests/test_api.py
python -m ruff check .
```

Also update:

- `docs/contracts/pipeline-contract.md` if counts, IDs, or validation expectations change.
- `docs/contracts/storage-contract.md` if `external_id` format changes.
- `docs/contracts/api-contract.md` if frontend-visible response shapes change.

## Common Mistakes

| Mistake | Result |
|---|---|
| Using an unknown `feature_type` | `FeatureType(...)` raises during mock Agent A generation. |
| Adding a task with an unknown assignee | `invalid_assignee` validation issue. |
| Referencing a missing section | critical source-section validation issue. |
| Changing task count without updating tests | pipeline/API tests fail. |
| Reusing the same task title with high similarity | duplicate candidate validation issue. |

