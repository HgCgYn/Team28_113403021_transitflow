# TASK 6 DESIGN DOCUMENT

## Section 7 — Delay Compensation Extension

### 7.1 Motivation
The extension adds a real-world delay compensation assistant to TransitFlow.
It makes the system more useful for passengers by exposing delay records, identifying impacted services, and calculating whether a booking qualifies for a partial or full refund based on the delay duration.

### 7.2 Schema Changes
- **Relational DB (`databases/relational/schema.sql`)**: 
  - `delay_records` table was integrated to store delay incidents (`delay_id`, `schedule_id`, `delay_min`). `delay_id` uses `VARCHAR(20)` to align with legacy system formats.
  - `season_tickets` and `disruptions` tables were documented with explicit Why/PK justifications.
  - All foreign keys enforce a mixed Hard/Soft delete strategy (e.g., `ON DELETE CASCADE` for reference data like schedules, `RESTRICT` for transactional bookings).
- **Vector DB (`skeleton/seed_vectors.py`)**: 
  - Schema is now dynamically adapted to the LLM's embedding dimension (e.g., `ALTER TABLE ... TYPE vector(3072)`).
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

**Query 3: Delay Ripple Analysis (Graph Cypher)**
```cypher
-- Visualizes the blast radius of disruptions within a safe, clamped hop distance
MATCH p = (start:Station {station_id: $delayed_station_id})-[:METRO_LINK|RAIL_LINK*0..2]-(end:Station)
WITH end, min(length(p)) AS hops_away
ORDER BY hops_away ASC
RETURN end.station_id AS station_id, end.name AS name, hops_away
```

### 7.4 Testing Evidence
Rigorous testing was conducted to ensure robustness:
1. **Compensation Engine**: `scripts/test_compensation_eligibility.py` successfully inserts a dummy booking, links it to a delay record, and asserts the correct refund percentage (50% or 100%) based on `refund_policy.json` rules.
2. **Delay Records**: `scripts/test_delay_records.py` verifies successful retrieval of seeded delays.
3. **RAG Vector Search**: `scripts/test_rag_search_verification.py` proves that the Python-layer threshold filtering works flawlessly. 
   - *Evidence:* Queries like "Unrelated pizza recipe" return 0 results, while "train is late" successfully returns the 3 relevant delay policies with similarity scores > 0.5. (See `RAG_SEARCH_VERIFICATION.md` for full test logs).

### 7.5 Agent Tool Integration & Demo Scenarios
Registered two new tools in `skeleton/agent.py`:
- `check_delay(schedule_id, travel_date)` → Retrieves raw delay records.
- `check_compensation(booking_id)` → Returns eligibility and refund amount.

**Demo Scenarios for the Chat UI:**
- "Does NR_SCH01 have a delay on 2024-10-15?"
- "Which stations are affected if NR03 is delayed?"
- "My booking BK001 was delayed 45 minutes — can I get compensation?"
- "What is the policy for a 60+ minute train delay?"
