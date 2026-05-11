# LLM Samples

This folder contains trimmed API fixture samples for UI design prompts.

- Files preserve the same `{ data, meta, error }` response envelope as the backend API.
- Array endpoints keep 1-2 representative records.
- Nested arrays in object endpoints are trimmed to reduce prompt tokens.
- Full payloads remain one level up in `frontend/_design_fixtures/` for MSW mocks and development.

