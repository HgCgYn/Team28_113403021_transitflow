# TASK 6 EXTENSION

## Files Modified or Added

| File | Changes | Functions / Tables |
|------|---------|-------------------|
| databases/relational/queries.py | Added `query_compensation_eligibility`, added header marker | query_compensation_eligibility, query_delay_records |
| databases/relational/schema.sql | Added `delay_records` schema, added PK explanations and EXTENSION header | delay_records |
| train-mock-data/refund_policy.json | Added 3 delay compensation policies | RF010, RF011, RF012 |
| skeleton/agent.py | Registered 2 new tools | check_delay, check_compensation |
| skeleton/seed_vectors.py | Dynamic pgvector dimensions handling and marker | seed |
| databases/graph/queries.py | Marked `query_delay_ripple` as Task 6 extension | query_delay_ripple |
| scripts/test_compensation_eligibility.py | Test script for compensation | N/A |
| scripts/test_delay_records.py | Test script for delay records | N/A |
| scripts/test_vector_search.py | Test script for vector search retrieval | N/A |
| scripts/test_rag_search_verification.py | RAG search logic test script | N/A |
| RAG_SEARCH_VERIFICATION.md | Vector search design decisions and verification | N/A |

## Purpose

This extension adds a delay-compensation assistant:
- Query delay records for schedules
- Determine refund eligibility for a booking
- Surface refund policy documents via the vector knowledge base
- Register agent tools for UI interaction

## Notes

Each modified file includes a top-of-file comment beginning with `# TASK 6 EXTENSION:` as required by the grading instructions.
