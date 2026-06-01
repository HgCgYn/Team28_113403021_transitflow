# TASK 6 DESIGN DOCUMENT

## Section 7 — Delay Compensation Extension

### 7.1 Motivation
The extension adds a real-world delay compensation assistant to TransitFlow.
It makes the system more useful for passengers by exposing delay records, identifying impacted services, and calculating whether a booking qualifies for a partial or full refund.

### 7.2 Relational DB Changes
- Added `query_compensation_eligibility(booking_id, user_id)` in `databases/relational/queries.py`.
- This new function:
  - validates booking ownership
  - retrieves the booked schedule and travel date
  - finds the maximum delay for that schedule/date from `delay_records`
  - applies compensation rules: 30–59 min => 50%, 60+ min => 100%
  - returns structured eligibility data for the UI/agent
- `delay_records` was already present in the schema and seeded via `skeleton/seed_postgres.py`.

### 7.3 Graph DB and Delay Analysis
- `databases/graph/queries.py` already exposes `query_delay_ripple()`.
- This function is documented as part of Task 6 and can be used to show which stations are affected by a delay.

### 7.4 Vector/RAG Knowledge Base
- Added three delay compensation policy documents to `train-mock-data/refund_policy.json`:
  - `RF010` — 30–59 minute delay compensation
  - `RF011` — 60+ minute delay compensation
  - `RF012` — alternative transport reimbursement for 120+ minute delays
- Re-ran `skeleton/seed_vectors.py` so the RAG system embeds the new documents and can answer policy questions.

### 7.5 Agent Tool Integration
- Registered two new tools in `skeleton/agent.py`:
  - `check_delay(schedule_id, travel_date)` → `query_delay_records()`
  - `check_compensation(booking_id)` → `query_compensation_eligibility()`
- This lets the conversational agent call these tools directly when users ask about delays or refund eligibility.

### 7.6 Verification
- Verified `query_delay_records()` after seeding `delay_records`.
- Verified `query_compensation_eligibility()` using a temporary test booking matched to a seeded delay record.
- Verified vector search returns the new delay compensation documents after running `skeleton/seed_vectors.py`.

### 7.7 Demo Scenarios
- "Does NR_SCH01 have a delay on 2024-10-15?"
- "Which stations are affected if NR03 is delayed?"
- "My booking BK001 was delayed 45 minutes — can I get compensation?"
- "What is the policy for a 60+ minute train delay?"
