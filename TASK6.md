# TASK 6 EXTENSION

## Files Modified or Added

| File | What was modified/added | Specific function/table name |
|---|---|---|
| databases/relational/schema.sql | Added `delay_records` table and `idx_delay_records_schedule_date` index | delay_records, idx_delay_records_schedule_date |
| databases/relational/queries.py | Added `query_compensation_eligibility` and `query_delay_records` functions | query_compensation_eligibility, query_delay_records |
| train-mock-data/delay_records.json | Added 5 seed delay records for testing | DR-001 – DR-005 |
| train-mock-data/refund_policy.json | Added 3 delay compensation policy documents (RF010–RF012) | RF010, RF011, RF012 |
| skeleton/seed_postgres.py | Added `seed_delay_records()` seeder function | seed_delay_records |
| skeleton/agent.py | Registered 2 new agent tools to expose the feature to the LLM | check_delay, check_compensation |

## Purpose

This extension adds a delay-compensation assistant on top of the existing system:
- `delay_records` table (in `schema.sql`) stores per-schedule, per-date delay incidents reported by operations staff.
- `query_compensation_eligibility` (in `queries.py`) correlates a user's booking with delay records and computes a 50% or 100% refund recommendation based on the delay duration.
- `query_delay_records` (in `queries.py`) retrieves all delay incidents for a given schedule and date.
- The 3 new policy documents (RF010–RF012) allow the RAG search engine to surface precise delay compensation rules when users ask about delays.
- The 2 new agent tools (`check_delay`, `check_compensation`) expose this feature end-to-end through the chat UI.

## Supporting Evidence

The following files were created as testing evidence (referenced in TASK6_DESIGN.md Section 7.4, not primary bonus code):
- `scripts/test_compensation_eligibility.py` — verifies refund percentage calculation
- `scripts/test_delay_records.py` — verifies delay record retrieval
- `scripts/test_vector_search.py` — verifies vector similarity search
- `scripts/test_rag_search_verification.py` — verifies RAG pipeline end-to-end
- `RAG_SEARCH_VERIFICATION.md` — full test log with query/result evidence

## Notes

Each primary modified file includes a top-of-file comment beginning with `# TASK 6 EXTENSION:` as required by the grading instructions.
