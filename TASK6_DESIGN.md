# TASK 6 DESIGN DOCUMENT

## Section 7 — Delay Compensation Extension

### 7.1 Motivation
The extension adds a real-world delay compensation assistant to TransitFlow.
While the base system stores delay records (Task 1/3), this extension implements the active logic to calculate whether a specific booking qualifies for a partial or full refund based on the delay duration and the latest policy documents.

### 7.2 Extension Details
- **Relational DB (`databases/relational/queries.py`)**: 
  - Added `query_compensation_eligibility`: This complex query correlates a user's booking with delay records and computes the exact refund percentage (50% or 100%) based on the delay duration.
- **Agent Integration (`skeleton/agent.py`)**:
  - Registered two new tools: `check_delay` and `check_compensation` to allow the LLM to directly check eligibility and delay status.
- **Policy Documents (`train-mock-data/refund_policy.json`)**:
  - Inserted 3 highly specific delay compensation policies (RF010, RF011, RF012) to power the RAG retrieval for delay queries.
- **Vector DB Architecture (`skeleton/seed_vectors.py`)**: 
  - Schema is now dynamically adapted to the LLM's embedding dimension (e.g., `ALTER TABLE ... TYPE vector(3072)`), ensuring the system doesn't crash when switching to larger models like Gemini.
  - HNSW index creation is bypassed if dimension > 2000 to prevent pgvector crashes.

### 7.3 Example Queries

**Query 1: Compensation Eligibility (Relational SQL)**
```sql
-- Determines if a booking qualifies for compensation by finding the delay of its schedule
SELECT dr.delay_min
FROM national_rail_bookings b
JOIN delay_records dr ON b.schedule_id = dr.schedule_id AND b.travel_date = dr.travel_date
WHERE b.booking_id = %s AND b.user_id = %s;
```

**Query 2: Dynamic RAG Vector Search (pgvector)**
```sql
-- HNSW ANN search without WHERE clause to ensure index utilization.
-- Threshold filtering (> 0.5) is performed in the Python application layer.
SELECT title, category, content, 1 - (embedding <=> %s::vector) AS similarity
FROM policy_documents
ORDER BY embedding <=> %s::vector
LIMIT 3;
```

### 7.4 Testing Evidence
Rigorous testing was conducted to ensure robustness:
1. **Compensation Engine**: `scripts/test_compensation_eligibility.py` successfully inserts a dummy booking, links it to a delay record, and asserts the correct refund percentage (50% or 100%).
2. **RAG Vector Search**: `scripts/test_rag_search_verification.py` proves that the Python-layer threshold filtering works flawlessly. 

### 7.5 Agent Tool Integration & Demo Scenarios
Registered two new tools in `skeleton/agent.py`:
- `check_delay(schedule_id, travel_date)` → Retrieves raw delay records.
- `check_compensation(booking_id)` → Returns eligibility and refund amount.

**Demo Scenarios for the Chat UI:**
- "My booking BK001 was delayed 45 minutes — can I get compensation?"
- "What is the policy for a 60+ minute train delay?"

