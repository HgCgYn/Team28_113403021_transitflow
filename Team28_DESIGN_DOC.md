# Team28 — TransitFlow Database Design Document

> **Course:** IM2002 Database Management  
> **Team:** G28  
> **Project:** TransitFlow — LLM + RAG Transit Assistant

---

## Section 1 — Entity-Relationship Diagram

### 1.1 ER Diagram

> Generated with [dbdiagram.io](https://dbdiagram.io). Crow's Foot notation: `|` = "one" side; `≪` = "many" side.

![TransitFlow ER Diagram — Team28](./er_diagram.svg)

### 1.2 Cardinality Summary

| Relationship | Cardinality | Description |
|---|---|---|
| `users` → `user_credentials` | 1:1 | Each user has exactly one credential record |
| `users` → `national_rail_bookings` | 1:N | A user can have many bookings |
| `users` → `metro_travels` | 1:N | A user can have many metro trips |
| `users` → `season_tickets` | 1:N | A user can hold multiple season tickets |
| `users` → `feedback` | 1:N | A user can submit multiple feedback items |
| `national_rail_schedules` → `national_rail_bookings` | 1:N | One schedule can appear across many bookings |
| `national_rail_schedules` → `national_rail_schedule_stops` | 1:N | One schedule has many stops |
| `national_rail_schedules` → `national_rail_fare_classes` | 1:N | One schedule has multiple fare class rows |
| `national_rail_schedules` → `seat_layouts` | 1:1 | Each schedule maps to exactly one seat layout |
| `seat_layouts` → `coaches` | 1:N | One layout contains many coaches |
| `coaches` → `seats` | 1:N | One coach contains many seats |
| `metro_schedules` → `metro_travels` | 1:N | One metro schedule can have many travel records |
| `metro_schedules` → `metro_schedule_stops` | 1:N | One schedule has many stops |
| `metro_stations` ↔ `national_rail_stations` | M:N (via FK pair) | Cross-network interchange (circular FK, DEFERRABLE) |
| `national_rail_schedules` → `delay_records` | 1:N | One schedule can have delay records on different dates |

---

## Section 2 — Normalisation Justification

### 2.1 Third Normal Form (3NF) Design Decisions

**Decision 1: Schedule Stops in a Dedicated Junction Table**

We created `metro_schedule_stops(schedule_id, station_id, stop_order, travel_time_from_origin_min)` rather than storing stops as a `TEXT[]` array column, for three reasons:

- Arrays violate 1NF (non-atomic values) and can't enforce referential integrity — no guarantee a stop actually exists in `metro_stations`.
- Filtering or joining on array elements requires `unnest()`, which is slow.
- The junction table satisfies 1NF, 2NF, and 3NF cleanly (composite PK, no transitive dependencies).

**Decision 2: Fare Data Separated into `national_rail_fare_classes`**

`national_rail_fare_classes(schedule_id, fare_class, base_fare_usd, per_stop_rate_usd)` uses a composite PK `(schedule_id, fare_class)`, so all non-key attributes depend on the full key. Storing fare columns directly on `national_rail_schedules` would create a partial dependency and a 2NF violation the moment a third fare class is introduced.

**Decision 3: User Credentials Separated from User Profile**

`users` holds identity and profile data; `user_credentials` holds `password_hash` and `secret_answer_hash`. The 1:1 split is intentional:

- Separate access control policies can be applied to each table in production.
- Credentials won't accidentally leak through a `SELECT *` on `users`.
- Different access patterns and sensitivity levels warrant separate tables.

### 2.2 Deliberate De-normalisation Trade-offs

**`full_name` as a Generated Stored Column**

`full_name TEXT GENERATED ALWAYS AS (first_name || ' ' || surname) STORED` is technically a 3NF violation (transitive dependency via `first_name`, `surname`), but it eliminates update anomalies and allows full-name text search without runtime concatenation.

**`national_rail_bookings`: Omitting `layout_id` as a Foreign Key**

`layout_id` is already derivable from `schedule_id` via `seat_layouts.schedule_id UNIQUE` — storing it in bookings would be a transitive dependency (3NF violation). Seat validity is enforced at the application layer via `SELECT ... FOR UPDATE` pessimistic locking during booking execution.

### 2.3 Password Hashing Design

We use **Argon2id** (PHC string format) for all password and secret answer storage.

**Why Argon2id over MD5 or SHA-256?**  
MD5 and SHA-256 are designed to be fast — wrong for password hashing. Argon2id is memory-hard: deliberately slow and RAM-intensive per attempt, making GPU-based brute-force attacks orders of magnitude more expensive. It won the 2015 Password Hashing Competition and is the current OWASP/NIST recommendation.

**Salt handling:** Argon2id generates a random CSPRNG salt per hash and embeds it in the PHC output string (e.g., `$argon2id$v=19$m=65536,t=3,p=4$<salt>$<hash>`). Two users with the same password produce completely different hashes, making precomputed rainbow tables useless. No separate salt column is needed.

---

## Section 3 — Graph Database Design Rationale

### 3.1 Node Design

We use a single `Station` label for all nodes, with a `network` property (`"metro"` or `"rail"`) distinguishing sub-types.

| Property | Type | Reason |
|---|---|---|
| `station_id` | String | Unique ID (e.g., `MS01`, `NR05`). Matches the relational PK for cross-database correlation. Idempotent `MERGE` during seeding prevents duplicate nodes. |
| `name` | String | Human-readable label for UI and LLM responses. |
| `network` | String | Filters traversals to a single network without redundant label checks. |
| `lines` | List | Quick display of which lines serve a station — no extra traversal needed. |

Stations are nodes (not relationships) because they are real-world entities with identity and multiple attributes that appear independently across many relationships.

### 3.2 Relationship Design

| Relationship Type | Properties | Meaning |
|---|---|---|
| `METRO_LINK` | `travel_time_min`, `line` | Direct metro connection between two adjacent stations |
| `RAIL_LINK` | `travel_time_min`, `line` | Direct national rail connection between two adjacent stations |
| `INTERCHANGE_TO` | `travel_time_min` | Walking transfer between a co-located metro and rail station |

`travel_time_min` lives on the relationship because travel time is a property of the *segment*, not either station — the same station may be 3 minutes from one neighbour and 12 from another. This lets Dijkstra use it directly as an edge weight.

### 3.3 Why a Graph Database Outperforms Relational for Routing

For shortest-path queries, a relational database needs a recursive CTE:

```sql
-- The visited array prevents cycles but causes exponential memory growth;
-- PostgreSQL's planner cannot optimise across recursive iterations.
WITH RECURSIVE path AS (
    SELECT origin_id, destination_id, ARRAY[origin_id] AS visited, 0 AS total_time
    WHERE station_id = 'MS01'
    UNION ALL
    SELECT ...
    FROM path p JOIN links l ON p.destination_id = l.origin_id
    WHERE NOT l.destination_id = ANY(p.visited)
)
SELECT * FROM path WHERE destination_id = 'MS14'
ORDER BY total_time LIMIT 1;
```

In Neo4j, the equivalent is a single APOC Dijkstra call:

```cypher
MATCH (s:Station {station_id: 'MS01'}), (e:Station {station_id: 'MS14'})
CALL apoc.algo.dijkstra(s, e, 'METRO_LINK>', 'travel_time_min') YIELD path, weight
RETURN path, weight AS total_time_min
```

Neo4j stores adjacency lists natively, enabling O(V + E log V) traversal via pointer-chasing. On our 30-station network: graph query < 5ms; recursive SQL > 100ms at 5-hop depth.

### 3.4 Query Types Enabled by the Graph Model

**Shortest Route (`query_shortest_route`)** — `METRO_LINK>` / `RAIL_LINK>` with `travel_time_min` as edge weight; APOC Dijkstra finds the minimum-time path in a single `CALL`.

**Cross-Network Interchange Path (`query_interchange_path`)** — `INTERCHANGE_TO` models the walking transfer between co-located stations. Setting `network="auto"` traverses `METRO_LINK|RAIL_LINK|INTERCHANGE_TO` in one Dijkstra call, crossing network boundaries seamlessly.

---

## Section 4 — Vector / RAG Design

### 4.1 What Is Embedded and Why

We embed **policy documents** — JSON objects covering refund policies, booking rules, ticket types, travel conduct, and delay compensation. Each is a self-contained unit of policy that a user might ask about in natural language.

Policy documents suit vector embedding because they carry semantic meaning that keyword search misses ("Can I get my money back?" should match "Refund Policy") and are relatively static — unlike bookings or trips, policies don't change on every transaction.

### 4.2 Why Cosine Similarity Is Appropriate

We use cosine similarity (`vector_cosine_ops`) because it measures the **angle** between vectors, ignoring magnitude. Two texts with the same meaning but different lengths produce vectors pointing in the same direction but with different magnitudes — cosine similarity treats them as nearly identical, while Euclidean distance would penalise the length difference. This aligns with how embedding models encode semantic proximity.

### 4.3 Full RAG Pipeline

```
User Query (natural language)
        │
        ▼
[1] Query Embedding
    llm.embed(query_text)
    → 768-dimensional float vector (Ollama nomic-embed-text)
        │
        ▼
[2] Vector Similarity Search (pgvector HNSW)
    SELECT title, content, 1 - (embedding <=> %s::vector) AS similarity
    FROM policy_documents
    ORDER BY embedding <=> %s::vector
    LIMIT 5
    -- NOTE: WHERE clause excluded to preserve HNSW index usage.
    -- Threshold filtering (similarity > 0.5) applied in Python.
        │
        ▼
[3] Retrieved Documents
    Top-K policy documents ranked by cosine similarity
    (filtered: only docs with similarity > VECTOR_SIMILARITY_THRESHOLD)
        │
        ▼
[4] LLM Prompt Construction
    System prompt + retrieved policy content injected as context
    → LLM (llama3.2 via Ollama / Gemini) generates a grounded answer
        │
        ▼
[5] Answer to User
    Factual, policy-grounded response surfaced in the Gradio chat UI
```

### 4.4 Embedding Dimension and Provider Switching

Our default uses **768 dimensions** (Ollama `nomic-embed-text`); Gemini (`gemini-embedding-001`) uses **3072**. Inserting a 3072-dim vector into a `vector(768)` column raises a dimension mismatch error and breaks the entire RAG pipeline.

We handle this in `seed_vectors.py` with a dynamic schema migration:

```python
# Step 1: Truncate existing embeddings (cannot ALTER while data exists)
cur.execute("TRUNCATE TABLE policy_documents RESTART IDENTITY;")
# Step 2: Drop the HNSW index (cannot ALTER an indexed column)
cur.execute("DROP INDEX IF EXISTS idx_policy_documents_embedding;")
# Step 3: Alter column type to match active provider
cur.execute(f"ALTER TABLE policy_documents ALTER COLUMN embedding TYPE vector({llm.embed_dim});")
# Step 4: Rebuild HNSW index (only if dim <= 2000; pgvector HNSW limit)
if llm.embed_dim <= 2000:
    cur.execute("CREATE INDEX ... USING hnsw (embedding vector_cosine_ops);")
```

**Switching providers without re-running `seed_vectors.py` breaks all similarity searches.**

---

## Section 5 — AI Tool Usage Evidence

We used AI assistants (primarily Antigravity IDE and ChatGPT) throughout development. The examples below include one case where the AI got it wrong.

---

**Example 1 — Schema Design: UUID vs SERIAL for Primary Keys**

*Context:* Designing the `users` table primary key.

*Prompt:* "Should we use SERIAL or UUID as the primary key for our users table? What are the security trade-offs?"

*Outcome:* The AI correctly identified that SERIAL integers are vulnerable to **ID enumeration attacks** — knowing booking ID `BK005` makes `BK001`–`BK004` trivially guessable. We adopted `UUID DEFAULT gen_random_uuid()` for `users.user_id`.

---

**Example 2 — Query Writing: Seat Availability with Pessimistic Locking**

*Context:* Two concurrent users could book the same seat simultaneously in `execute_booking()`.

*Prompt:* "How do I prevent two concurrent transactions from booking the same seat in PostgreSQL?"

*Outcome:* The AI suggested `SELECT ... FOR UPDATE` for row-level locking — correct, and we implemented it. It also suggested `SERIALIZABLE` isolation, which we rejected as it would lock the entire table rather than a single row, causing unnecessary contention.

---

**Example 3 — AI Gave a Wrong Answer (Debugging the HNSW Index)**

*Context:* Adding a similarity threshold to `query_policy_vector_search`:

```sql
WHERE 1 - (embedding <=> %s::vector) > 0.5
ORDER BY embedding <=> %s::vector LIMIT 3
```

Latency jumped from ~5ms to ~800ms (full sequential scan) despite the HNSW index being in place.

*Prompt:* "Why is my pgvector query not using the HNSW index with a WHERE clause on the similarity score?"

*Outcome (incorrect):* The AI blamed a "statistics cache miss" and suggested rebuilding the index with lower `ef_construction`. Both were wrong. Reading the pgvector docs directly revealed the real cause: **HNSW only activates for `ORDER BY ... LIMIT` queries — a `WHERE` on the distance expression forces an exact scan.**

The fix: remove the `WHERE` clause; apply the threshold in Python. Latency dropped back to ~5ms. Lesson: verify AI output against primary documentation for anything performance-critical.

---

**Example 4 — Graph Database: Cypher for Delay Ripple Analysis**

*Context:* Implementing `query_delay_ripple` — all stations within N hops of a disrupted station.

*Prompt:* "Write a Cypher query that finds all stations within N hops and returns the minimum hop count to each."

*Outcome:* The AI provided a correct variable-length path query using `min(length(p))`, but used a parameterised bound (`*0..$hops`) which Cypher **does not support** — bounds must be literals. We worked around this with a Python f-string, clamped to `_MAX_HOPS = 5` to prevent unbounded traversals.

---

**Example 5 — Argon2id Password Hashing Integration**

*Context:* Integrating a strong password hashing algorithm into `register_user()`.

*Prompt:* "How do I hash and verify passwords using argon2-cffi in Python?"

*Outcome:* The AI correctly demonstrated `PasswordHasher().hash(password)` and `PasswordHasher().verify(hash, password)`, with `VerifyMismatchError` for failed verification. We adopted it directly, adding a `try/except VerifyMismatchError` clause and a `return None` for unknown emails in `login_user()`.

---

## Section 6 — Reflection & Trade-offs

### 6.1 Design Decisions

**Decision 1: Mixed Delete Strategy (CASCADE vs. RESTRICT)**

Reference data (schedules, stations, layouts) uses `ON DELETE CASCADE` — deleting a schedule cleans up its stops, fare classes, and operating days automatically. Transactional data (bookings, payments, feedback) uses `ON DELETE RESTRICT` — booking and payment records are financial audit trails and must not be silently deleted. We use `is_active = FALSE` soft deletion on `users` rather than hard deletion.

**Decision 2: Polymorphic `booking_ref` in `payments` and `feedback`**

Both tables reference either a `national_rail_bookings.booking_id` or a `metro_travels.trip_id` depending on `booking_type`. SQL doesn't support polymorphic foreign keys, so we can't enforce referential integrity at the database level. We chose this over separate `rail_payments` / `metro_payments` tables to keep the payment and feedback schemas unified and simplify agent-layer query logic; the trade-off is documented with a schema comment.

### 6.2 What Would Be Different in Production

**Connection Pooling:** Every query function currently calls `psycopg2.connect()` directly. Under real load this exhausts PostgreSQL's connection limit. A production system would use `psycopg2.pool.ThreadedConnectionPool` or `pgBouncer`.

**Schema Migration Management:** We reset the schema with `docker compose down -v` during development. Production deployments would use **Alembic** or **Flyway** for incremental, versioned migrations that track applied changes without wiping data.

---

## Section 7 — Task 6 Extension: Delay Compensation Assistant

### 7.1 Motivation

The base TransitFlow system stores `delay_records` but provides no way for users to check whether their booking qualifies for compensation. This extension adds a complete pipeline: a SQL query that correlates bookings with delay records, two agent tools, and three RAG policy documents that let the assistant explain the rules in plain language.

### 7.2 Database Changes

**New Table: `delay_records`** (defined in `databases/relational/schema.sql`):

```sql
CREATE TABLE IF NOT EXISTS delay_records (
    delay_id     VARCHAR(20) PRIMARY KEY,
    schedule_id  VARCHAR(20) NOT NULL REFERENCES national_rail_schedules(schedule_id) ON DELETE CASCADE,
    travel_date  DATE NOT NULL,
    delay_min    SMALLINT NOT NULL CHECK (delay_min > 0),
    reason       TEXT,
    reported_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Composite index for the most frequent query pattern: filter by schedule + date
CREATE INDEX IF NOT EXISTS idx_delay_records_schedule_date
    ON delay_records(schedule_id, travel_date);
```

**New Policy Documents** (added to `train-mock-data/refund_policy.json`):
- `RF010` — Delay Compensation: All Networks (general eligibility)
- `RF011` — Delay Compensation: 30–59 Minutes (50% refund)
- `RF012` — Delay Compensation: 60+ Minutes (100% refund)

### 7.3 Example Queries

**Query 1 — Compensation Eligibility Check (SQL)**

```sql
-- Correlates a booking with delay records for its schedule on its travel date.
-- Returns the maximum delay recorded in case of multiple reports for the same run.
SELECT
    b.booking_id,
    b.user_id,
    b.travel_date,
    b.amount_usd,
    b.status,
    MAX(dr.delay_min) AS max_delay_min,
    CASE
        WHEN MAX(dr.delay_min) >= 60 THEN 100
        WHEN MAX(dr.delay_min) >= 30 THEN 50
        ELSE 0
    END AS refund_percentage
FROM national_rail_bookings b
JOIN delay_records dr
    ON b.schedule_id = dr.schedule_id
    AND b.travel_date = dr.travel_date
WHERE b.booking_id = 'BK001'
  AND b.user_id = '<user-uuid>'
GROUP BY b.booking_id, b.user_id, b.travel_date, b.amount_usd, b.status;
```

**Expected Output (with BK001 delayed 45 minutes):**

| booking_id | travel_date | amount_usd | max_delay_min | refund_percentage |
|---|---|---|---|---|
| BK001 | 2026-04-01 | 45.50 | 45 | 50 |

**Query 2 — RAG Vector Search for Policy Retrieval**

```sql
-- HNSW ANN search — WHERE clause excluded to ensure index activation.
-- Threshold filtering applied in Python after fetching results.
SELECT title, category, content,
       1 - (embedding <=> '[0.021, -0.034, ...]'::vector) AS similarity
FROM policy_documents
ORDER BY embedding <=> '[0.021, -0.034, ...]'::vector
LIMIT 5;
```

For the query `"My train was delayed 45 minutes, am I eligible for compensation?"`, this returns:
- `RF011 — Delay Compensation: 30–59 Minutes` (similarity: 0.87)
- `RF010 — Delay Compensation: All Networks` (similarity: 0.81)

### 7.4 Testing Evidence

Testing was done via dedicated scripts in the `scripts/` directory.

**Test 1 — Compensation Engine** (`scripts/test_compensation_eligibility.py`)

```
[TEST] Booking BK001 — schedule NR_SCH01, date 2026-04-01
  Delay record found: 45 minutes (DR-101)
  Expected refund: 50% (30-59 min threshold)
  Result: PASS — refund_percentage = 50, refund_amount = $22.75
```

**Test 2 — RAG Policy Retrieval** (`scripts/test_rag_search_verification.py`)

```
Query: "My train was delayed 45 minutes, am I eligible for compensation?"
  [1] RF011 — Delay Compensation 30-59 Minutes    similarity=0.87  PASS
  [2] RF010 — Delay Compensation: All Networks    similarity=0.81  PASS
  [3] RF001 — National Rail Refund Policy         similarity=0.62  PASS (context)
```

Full test logs are in `RAG_SEARCH_VERIFICATION.md` at the repository root.

### 7.5 Agent Tool Integration

Two tools were registered in `skeleton/agent.py`:

- **`check_delay(schedule_id, travel_date)`** — Retrieves all delay records for a given schedule on a given date. Lets the LLM answer: *"Was train NR_SCH01 delayed on April 1st?"*
- **`check_compensation(booking_id)`** — Returns full eligibility assessment including refund percentage and amount. Lets the LLM answer: *"Does my booking BK001 qualify for compensation?"*

**Demo scenarios for the live session:**
1. *"My booking BK001 was delayed 45 minutes — can I get a refund?"* → `check_compensation` returns 50% refund eligibility
2. *"What is the policy for a 60+ minute delay?"* → RAG retrieves RF012 and the LLM explains the 100% refund rule
