# TASK 6 EXTENSION

## Files Modified or Added

| File | Changes | Functions / Tables |
|------|---------|-------------------|
| databases/relational/queries.py | Added `query_compensation_eligibility`, added header marker | query_compensation_eligibility, query_delay_records |
| train-mock-data/refund_policy.json | Added 3 delay compensation policies | RF010, RF011, RF012 |
| skeleton/agent.py | Registered 2 new tools | check_delay, check_compensation |
| databases/graph/queries.py | Marked `query_delay_ripple` as Task 6 extension | query_delay_ripple |

## Purpose

This extension adds a delay-compensation assistant:
- Query delay records for schedules
- Determine refund eligibility for a booking
- Surface refund policy documents via the vector knowledge base
- Register agent tools for UI interaction

## Notes

Each modified file includes a top-of-file comment beginning with `# TASK 6 EXTENSION:` as required by the grading instructions.
