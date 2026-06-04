# Work Allocation Report — Team 28

## 1. Team Members

| Full Name | Student ID | GitHub Username | Email |
|-----------|-----------|----------------|-------|
| 黃丞胤 | 113403021 | HgCgYn | andy0625huang@gmail.com |
| 段景旻 | 113403066 | pyaegorock-ux | pyaegorock@gmail.com |
| 鄭志緬 | 113403033 | myatmink | myatminkhant725@gmail.com |

---

## 2. Task Ownership

### Code Repository

| Task | Primary Owner | Supporting Member(s) | Notes |
|------|--------------|---------------------|-------|
| **Task 1** — Relational schema design (`schema.sql`) | 黃丞胤 | 段景旻, 鄭志緬 | 黃丞胤 owned the full schema: table structure, FK cascade strategy, Argon2id credential separation. 段景旻 and 鄭志緬 joined design discussions. |
| **Task 2a** — Core availability & fare queries | 黃丞胤 | 段景旻, 鄭志緬 | 段景旻 and 鄭志緬 joined design discussions. |
| **Task 2b** — Seat & user queries | 黃丞胤 | 段景旻, 鄭志緬 | 段景旻 and 鄭志緬 joined design discussions. |
| **Task 2c** — Write operations (`execute_booking`, `execute_cancellation`) | 黃丞胤 | 段景旻, 鄭志緬 | 段景旻 caught and fixed a missing coach condition in the pessimistic lock logic. 鄭志緬 joined design discussion. |
| **Task 2d** — Authentication queries | 黃丞胤 | 段景旻, 鄭志緬 | 段景旻 and 鄭志緬 joined design discussions. |
| **Task 3** — PostgreSQL seeding (`seed_postgres.py`) | 黃丞胤 | 段景旻, 鄭志緬 | 黃丞胤 wrote all seeding scripts and mock data JSON files. 段景旻 and 鄭志緬 discussed data structure. |
| **Task 4** — Neo4j graph design & seeding (`seed_neo4j.py`, `seed.cypher`) | 黃丞胤 | 段景旻, 鄭志緬 | 黃丞胤 designed the graph schema and seeding logic. 段景旻 added idempotency to `seed_vectors.py` and handled dynamic embedding dimension changes. 鄭志緬 added dimension whitelist validation and HNSW skip logging to `seed_vectors.py`. |
| **Task 5** — Neo4j query functions (`graph/queries.py`) | 段景旻 | 黃丞胤 | 段景旻 wrote `query_interchange_path` (with `is_cross_network` flag). 黃丞胤 wrote the remaining queries (`query_shortest_route`, `query_delay_ripple`, etc.). |
| **Task 6** *(Extension)* — Delay Compensation Assistant | 鄭志緬 | 黃丞胤, 段景旻 | 鄭志緬 built the initial pipeline: compensation SQL, agent tools, refund policy docs (RF010–RF012), and test scripts. 黃丞胤 refined the implementation and brought Section 7 up to rubric. 段景旻 handled RAG verification and the HNSW threshold fix. |

### Design Document

| Section | Primary Author | Supporting Member(s) | Notes |
|---------|--------------|---------------------|-------|
| Section 1 — ER Diagram | 黃丞胤 | — | Built with dbdiagram.io; exported as SVG. |
| Section 2 — Normalisation Justification | 黃丞胤 | — | |
| Section 3 — Graph Database Design Rationale | 黃丞胤 | — | |
| Section 4 — Vector / RAG Design | 黃丞胤 | 段景旻 | The HNSW WHERE-clause bug write-up (Example 3) drew on 段景旻's debugging work. |
| Section 5 — AI Tool Usage Evidence | 黃丞胤 | — | |
| Section 6 — Reflection & Trade-offs | 黃丞胤 | — | |
| Section 7 — Task 6 Extension | 鄭志緬 | 黃丞胤 | 鄭志緬 wrote the initial draft (TASK6_DESIGN.md). 黃丞胤 expanded it to cover all rubric requirements. |

---

## 3. Estimated Contribution Percentages

| Member | Estimated % | Brief justification |
|--------|-----------|---------------------|
| 黃丞胤 | 40% | Led the overall architecture. Responsible for the schema, Tasks 2a–2d, Task 3 seeding, Task 4, most graph queries, and the full design document (Sections 1–6). |
| 段景旻 | 30% | Wrote `query_interchange_path` (Task 5); fixed the coach condition bug in `execute_booking`; built `seed_vectors.py` idempotency and dynamic dimension support; wrote RAG verification scripts; joined design discussions for Tasks 1–3. |
| 鄭志緬 | 30% | Led Task 6 (compensation pipeline, agent tools, policies, tests); drafted Section 7; added dimension validation and HNSW skip logging to `seed_vectors.py` (Task 4); joined design discussions for Tasks 1–3. |
| **Total** | **100%** | |

---

## 4. Mid-Project Changes

| Change | Original plan | Revised plan | Reason |
|--------|--------------|-------------|--------|
| Task 5 split | 黃丞胤 to write all graph query functions | 段景旻 took `query_interchange_path`; 黃丞胤 handled the rest | Workload balancing — 段景旻 already had context from the vector seeder and cross-network data. |
| Task 6 design doc | 鄭志緬 to author the full Section 7 | 鄭志緬 wrote the first draft; 黃丞胤 rewrote and expanded it | The initial draft didn't fully address the rubric, so the team lead stepped in to complete it. |

---

## 5. Team Declaration

We confirm that this work allocation accurately reflects how responsibilities were divided within our team.

| Name | Signature / Typed name | Date |
|------|----------------------|------|
| 黃丞胤 | 黃丞胤 | 2026-06-04 |
| 段景旻 | 段景旻 | 2026-06-04 |
| 鄭志緬 | 鄭志緬 | 2026-06-04 |
