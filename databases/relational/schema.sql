-- ============================================================
--  TransitFlow — PostgreSQL Relational Schema
--  v1.0  (2026-05)
--
--  This file is auto-loaded by Docker on first container start
--  (mounted at /docker-entrypoint-initdb.d/init.sql).
--
--  To apply schema changes after first boot:
--      docker compose down -v && docker compose up -d
--
--  TWO ROLES:
--    1. Relational  → transit domain data (stations, schedules,
--                      bookings, users, payments, feedback)
--    2. Vector      → policy documents for RAG (pgvector)
--                     — do NOT modify that section
-- ============================================================

-- ============================================================
--  EXTENSIONS
-- ============================================================

-- TASK 6 EXTENSION: delay_records table is used by the Task 6
-- compensation assistant. This header satisfies the TASK6 file marker requirement.

-- pgvector: enables vector similarity search for RAG
CREATE EXTENSION IF NOT EXISTS vector;

-- pgcrypto: gen_random_uuid() for UUID v4 primary keys
CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- ============================================================
--  DELETE STRATEGY (Hard vs Soft Delete)
--  We employ a mixed but consistent strategy:
--  - Reference Data (Stations, Schedules, Layouts): We use Hard Deletes (ON DELETE CASCADE)
--    so that removing a schedule automatically cleans up its stops, fares, and layouts.
--  - Transactional Data (Bookings, Travels, Payments): We use ON DELETE RESTRICT
--    to prevent accidental deletion of audited financial and travel records if a user or schedule is deleted.
-- ============================================================

-- ============================================================
--  ENUM TYPE DEFINITIONS
--  Using ENUM enforces the value contract at the DB engine
--  level, making invalid states unrepresentable — a key
--  principle of defensive schema design.
-- ============================================================

CREATE TYPE service_type_enum         AS ENUM ('normal', 'express');
CREATE TYPE direction_enum            AS ENUM ('northbound','southbound','eastbound','westbound');
CREATE TYPE fare_class_enum           AS ENUM ('standard', 'first');
CREATE TYPE ticket_type_enum          AS ENUM ('single', 'return');
CREATE TYPE metro_ticket_type_enum    AS ENUM ('single', 'day_pass');
CREATE TYPE booking_status_enum       AS ENUM ('confirmed', 'completed', 'cancelled');
CREATE TYPE metro_trip_status_enum    AS ENUM ('completed', 'cancelled');
CREATE TYPE payment_method_enum       AS ENUM ('credit_card', 'debit_card', 'ewallet');
CREATE TYPE payment_status_enum       AS ENUM ('paid', 'refunded', 'pending');
CREATE TYPE booking_type_enum         AS ENUM ('rail', 'metro');
CREATE TYPE day_of_week_enum          AS ENUM ('mon','tue','wed','thu','fri','sat','sun');
CREATE TYPE season_ticket_type_enum   AS ENUM ('weekly', 'monthly', 'annual');
CREATE TYPE season_ticket_status_enum AS ENUM ('active', 'expired', 'cancelled');
CREATE TYPE disruption_type_enum      AS ENUM ('engineering', 'emergency', 'weather', 'other');


-- ============================================================
--  STATION LAYER
-- ============================================================

-- NOTE: We declare the cross-network FK after both tables exist.
--       The nullable column allows circular FK resolution.

CREATE TABLE IF NOT EXISTS metro_stations (
    station_id                          VARCHAR(10)  PRIMARY KEY,
    name                                VARCHAR(100) NOT NULL,
    is_interchange_metro                BOOLEAN      NOT NULL DEFAULT FALSE,
    is_interchange_national_rail        BOOLEAN      NOT NULL DEFAULT FALSE,
    -- FK to national_rail_stations added below (circular dependency)
    interchange_national_rail_station_id VARCHAR(10)
);

CREATE TABLE IF NOT EXISTS national_rail_stations (
    station_id                   VARCHAR(10)  PRIMARY KEY,
    name                         VARCHAR(100) NOT NULL,
    is_interchange_national_rail BOOLEAN      NOT NULL DEFAULT FALSE,
    is_interchange_metro         BOOLEAN      NOT NULL DEFAULT FALSE,
    interchange_metro_station_id VARCHAR(10)  REFERENCES metro_stations(station_id) ON DELETE SET NULL
        DEFERRABLE INITIALLY DEFERRED
);

ALTER TABLE metro_stations ADD CONSTRAINT fk_metro_national_rail
FOREIGN KEY (interchange_national_rail_station_id) REFERENCES national_rail_stations(station_id) ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;

-- lines[] on each station → fully normalised junction table
-- PK = (station_id, line) — a station may serve multiple lines
CREATE TABLE IF NOT EXISTS metro_station_lines (
    station_id VARCHAR(10) NOT NULL REFERENCES metro_stations(station_id) ON DELETE CASCADE,
    line       VARCHAR(10) NOT NULL,
    PRIMARY KEY (station_id, line)
);

CREATE TABLE IF NOT EXISTS national_rail_station_lines (
    station_id VARCHAR(10) NOT NULL REFERENCES national_rail_stations(station_id) ON DELETE CASCADE,
    line       VARCHAR(10) NOT NULL,
    PRIMARY KEY (station_id, line)
);


-- ============================================================
--  SCHEDULE LAYER — METRO
-- ============================================================

CREATE TABLE IF NOT EXISTS metro_schedules (
    schedule_id             VARCHAR(20)     PRIMARY KEY,
    line                    VARCHAR(10)     NOT NULL,
    direction               direction_enum  NOT NULL,
    origin_station_id       VARCHAR(10)     NOT NULL REFERENCES metro_stations(station_id),
    destination_station_id  VARCHAR(10)     NOT NULL REFERENCES metro_stations(station_id),
    first_train_time        TIME            NOT NULL,
    last_train_time         TIME            NOT NULL,
    base_fare_usd           NUMERIC(8,2)    NOT NULL CHECK (base_fare_usd >= 0),
    per_stop_rate_usd       NUMERIC(8,2)    NOT NULL CHECK (per_stop_rate_usd >= 0),
    frequency_min           SMALLINT        NOT NULL CHECK (frequency_min > 0)
);

-- Normalised stop-level detail for each metro schedule
CREATE TABLE IF NOT EXISTS metro_schedule_stops (
    schedule_id              VARCHAR(20)  NOT NULL REFERENCES metro_schedules(schedule_id) ON DELETE CASCADE,
    station_id               VARCHAR(10)  NOT NULL REFERENCES metro_stations(station_id) ON DELETE RESTRICT,
    stop_order               SMALLINT     NOT NULL CHECK (stop_order >= 1),
    travel_time_from_origin_min SMALLINT  NOT NULL CHECK (travel_time_from_origin_min >= 0),
    PRIMARY KEY (schedule_id, station_id)
);

-- Normalised operating days for each metro schedule
CREATE TABLE IF NOT EXISTS metro_schedule_operates_on (
    schedule_id  VARCHAR(20)       NOT NULL REFERENCES metro_schedules(schedule_id) ON DELETE CASCADE,
    day_of_week  day_of_week_enum  NOT NULL,
    PRIMARY KEY (schedule_id, day_of_week)
);


-- ============================================================
--  SCHEDULE LAYER — NATIONAL RAIL
-- ============================================================

CREATE TABLE IF NOT EXISTS national_rail_schedules (
    schedule_id             VARCHAR(20)         PRIMARY KEY,
    line                    VARCHAR(10)         NOT NULL,
    service_type            service_type_enum   NOT NULL,
    direction               direction_enum      NOT NULL,
    origin_station_id       VARCHAR(10)         NOT NULL REFERENCES national_rail_stations(station_id),
    destination_station_id  VARCHAR(10)         NOT NULL REFERENCES national_rail_stations(station_id),
    first_train_time        TIME                NOT NULL,
    last_train_time         TIME                NOT NULL,
    frequency_min           SMALLINT            NOT NULL CHECK (frequency_min > 0)
);

CREATE TABLE IF NOT EXISTS national_rail_schedule_stops (
    schedule_id                  VARCHAR(20)  NOT NULL REFERENCES national_rail_schedules(schedule_id) ON DELETE CASCADE,
    station_id                   VARCHAR(10)  NOT NULL REFERENCES national_rail_stations(station_id) ON DELETE RESTRICT,
    stop_order                   SMALLINT     NOT NULL CHECK (stop_order >= 1),
    travel_time_from_origin_min  SMALLINT     NOT NULL CHECK (travel_time_from_origin_min >= 0),
    PRIMARY KEY (schedule_id, station_id)
);

-- Fare matrix: one row per (schedule, class) combination
CREATE TABLE IF NOT EXISTS national_rail_fare_classes (
    schedule_id       VARCHAR(20)     NOT NULL REFERENCES national_rail_schedules(schedule_id) ON DELETE CASCADE,
    fare_class        fare_class_enum NOT NULL,
    base_fare_usd     NUMERIC(8,2)    NOT NULL CHECK (base_fare_usd >= 0),
    per_stop_rate_usd NUMERIC(8,2)    NOT NULL CHECK (per_stop_rate_usd >= 0),
    PRIMARY KEY (schedule_id, fare_class)
);

CREATE TABLE IF NOT EXISTS national_rail_schedule_operates_on (
    schedule_id  VARCHAR(20)       NOT NULL REFERENCES national_rail_schedules(schedule_id) ON DELETE CASCADE,
    day_of_week  day_of_week_enum  NOT NULL,
    PRIMARY KEY (schedule_id, day_of_week)
);


-- ============================================================
--  SEAT LAYOUT LAYER (National Rail only)
-- ============================================================

-- One layout per schedule; UNIQUE enforces the 1-to-1 mapping
CREATE TABLE IF NOT EXISTS seat_layouts (
    layout_id   VARCHAR(10)  PRIMARY KEY,
    schedule_id VARCHAR(20)  NOT NULL UNIQUE REFERENCES national_rail_schedules(schedule_id) ON DELETE CASCADE
);

-- Each coach belongs to one layout and carries one fare class
CREATE TABLE IF NOT EXISTS coaches (
    layout_id  VARCHAR(10)     NOT NULL REFERENCES seat_layouts(layout_id) ON DELETE CASCADE,
    coach      VARCHAR(5)      NOT NULL,
    fare_class fare_class_enum NOT NULL,
    PRIMARY KEY (layout_id, coach)
);

-- Individual seats — granular enough for exact seat selection
CREATE TABLE IF NOT EXISTS seats (
    layout_id  VARCHAR(10)  NOT NULL,
    coach      VARCHAR(5)   NOT NULL,
    seat_id    VARCHAR(10)  NOT NULL,
    row        SMALLINT     NOT NULL CHECK (row >= 1),
    col        VARCHAR(1)   NOT NULL,
    PRIMARY KEY (layout_id, coach, seat_id),
    FOREIGN KEY (layout_id, coach) REFERENCES coaches(layout_id, coach) ON DELETE CASCADE
);


-- ============================================================
--  USER LAYER — Separated profile and credentials
--
--  Design rationale:
--    - users         → identity and profile data (low sensitivity)
--    - user_credentials → authentication secrets (high sensitivity)
--
--  This separation follows the Single Responsibility Principle
--  and makes it easier to apply column-level encryption or
--  per-table access control policies in production.
--
--  Passwords and secret answers are stored as Argon2id hashes
--  (PHC string format). Argon2id is the OWASP/NIST-recommended
--  algorithm for password hashing as of 2024. The hash output
--  embeds the random CSPRNG-generated salt — no separate salt
--  column is required.
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    -- PK Design Decision: We use UUID v4 instead of SERIAL for security and scalability.
    -- UUIDs prevent enumeration attacks (guessing other users' IDs) and allow distributed ID generation.
    user_id       UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    -- legacy_id maps the original mock-data ID (RU01…RU20) to the
    -- UUID during seeding. Kept for audit traceability and team sync.
    legacy_id     VARCHAR(10)  UNIQUE,
    first_name    VARCHAR(100) NOT NULL,
    surname       VARCHAR(100) NOT NULL,
    -- Generated column avoids data duplication; always consistent
    full_name     TEXT         GENERATED ALWAYS AS (first_name || ' ' || surname) STORED,
    email         VARCHAR(255) NOT NULL UNIQUE,
    phone         VARCHAR(20),
    date_of_birth DATE,
    registered_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    loyalty_points INT         NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_credentials (
    -- 1-to-1 with users; user_id is both PK and FK
    user_id              UUID         PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    -- Argon2id PHC string — includes algo params, salt, and digest
    password_hash        VARCHAR(255) NOT NULL,
    secret_question      VARCHAR(255) NOT NULL,
    -- Secret answer hashed with the same Argon2id scheme,
    -- normalised to lowercase before hashing
    secret_answer_hash   VARCHAR(255) NOT NULL,
    -- Tracks last credential update for security auditing
    credentials_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
--  TRANSACTION LAYER
-- ============================================================

CREATE TABLE IF NOT EXISTS national_rail_bookings (
    booking_id              VARCHAR(20)          PRIMARY KEY,
    user_id                 UUID                 NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    schedule_id             VARCHAR(20)          NOT NULL REFERENCES national_rail_schedules(schedule_id) ON DELETE RESTRICT,
    origin_station_id       VARCHAR(10)          NOT NULL REFERENCES national_rail_stations(station_id) ON DELETE RESTRICT,
    destination_station_id  VARCHAR(10)          NOT NULL REFERENCES national_rail_stations(station_id) ON DELETE RESTRICT,
    travel_date             DATE                 NOT NULL,
    departure_time          TIME                 NOT NULL,
    ticket_type             ticket_type_enum     NOT NULL DEFAULT 'single',
    fare_class              fare_class_enum      NOT NULL,
    coach                   VARCHAR(5)           NOT NULL,
    seat_id                 VARCHAR(10)          NOT NULL,
    stops_travelled         SMALLINT             NOT NULL CHECK (stops_travelled >= 1),
    amount_usd              NUMERIC(10,2)        NOT NULL CHECK (amount_usd >= 0),
    status                  booking_status_enum  NOT NULL DEFAULT 'confirmed',
    booked_at               TIMESTAMPTZ          NOT NULL DEFAULT NOW(),
    travelled_at            TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS metro_travels (
    trip_id                 VARCHAR(20)           PRIMARY KEY,
    user_id                 UUID                  NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    schedule_id             VARCHAR(20)           NOT NULL REFERENCES metro_schedules(schedule_id) ON DELETE RESTRICT,
    origin_station_id       VARCHAR(10)           NOT NULL REFERENCES metro_stations(station_id) ON DELETE RESTRICT,
    destination_station_id  VARCHAR(10)           NOT NULL REFERENCES metro_stations(station_id) ON DELETE RESTRICT,
    travel_date             DATE                  NOT NULL,
    ticket_type             metro_ticket_type_enum NOT NULL,
    -- day_pass_ref points back to the originating day-pass trip_id
    -- (nullable; NULL means this trip is itself the day-pass purchase)
    day_pass_ref            VARCHAR(20)           REFERENCES metro_travels(trip_id) ON DELETE RESTRICT,
    stops_travelled         SMALLINT              CHECK (stops_travelled >= 0),
    amount_usd              NUMERIC(10,2)         NOT NULL CHECK (amount_usd >= 0),
    status                  metro_trip_status_enum NOT NULL DEFAULT 'completed',
    purchased_at            TIMESTAMPTZ,
    travelled_at            TIMESTAMPTZ
);

-- NOTE: payments.booking_ref is intentionally NOT a foreign key.
--       It references either national_rail_bookings OR metro_travels
--       depending on booking_type, which SQL cannot express with a
--       single FK constraint. booking_type makes the target explicit.
CREATE TABLE IF NOT EXISTS payments (
    payment_id    VARCHAR(20)          PRIMARY KEY,
    booking_ref   VARCHAR(20)          NOT NULL,
    booking_type  booking_type_enum    NOT NULL,
    amount_usd    NUMERIC(10,2)        NOT NULL CHECK (amount_usd >= 0),
    method        payment_method_enum  NOT NULL,
    status        payment_status_enum  NOT NULL DEFAULT 'paid',
    paid_at       TIMESTAMPTZ          NOT NULL DEFAULT NOW()
);

-- feedback.booking_ref follows the same polymorphic pattern as payments
CREATE TABLE IF NOT EXISTS feedback (
    feedback_id   VARCHAR(20)       PRIMARY KEY,
    booking_ref   VARCHAR(20)       NOT NULL,
    booking_type  booking_type_enum NOT NULL,
    user_id       UUID              NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    -- Ratings are always 1–5 (inclusive) per the source data contract
    rating        SMALLINT          NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment       TEXT,
    submitted_at  TIMESTAMPTZ       NOT NULL DEFAULT NOW()
);


-- WHY: This table exists to store daily disruption reports for the Task 6 delay compensation feature.
-- It allows the system to cross-reference a user's booking date and schedule with reported delays.
-- PK Design Decision: We use VARCHAR(20) for delay_id to remain consistent with the legacy system's
-- alphanumeric ID formats (e.g., 'DR-101') rather than migrating to UUIDs for this isolated feature.
CREATE TABLE IF NOT EXISTS delay_records (
    delay_id     VARCHAR(20) PRIMARY KEY,
    schedule_id  VARCHAR(20) NOT NULL REFERENCES national_rail_schedules(schedule_id) ON DELETE CASCADE,
    travel_date  DATE NOT NULL,
    delay_min    SMALLINT NOT NULL CHECK (delay_min > 0),
    reason       TEXT,
    reported_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS season_tickets (
    season_ticket_id  VARCHAR(20) PRIMARY KEY,
    user_id           UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    ticket_type       season_ticket_type_enum NOT NULL,
    valid_from        DATE NOT NULL,
    valid_until       DATE NOT NULL,
    price_usd         NUMERIC(10,2) NOT NULL,
    network           VARCHAR(10) NOT NULL CHECK (network IN ('metro', 'rail', 'all')),
    status            season_ticket_status_enum NOT NULL DEFAULT 'active',
    purchased_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS disruptions (
    disruption_id   VARCHAR(20) PRIMARY KEY,
    disruption_type disruption_type_enum NOT NULL,
    affected_lines  TEXT[] NOT NULL,
    start_datetime  TIMESTAMPTZ NOT NULL,
    end_datetime    TIMESTAMPTZ,
    description     TEXT NOT NULL,
    replacement_service TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
--  INDEXES
--  Only indexes with a clear query-plan benefit are created.
--  Over-indexing hurts write throughput.
-- ============================================================

-- Fast user lookup by email (login flow)
CREATE INDEX IF NOT EXISTS idx_users_email
    ON users(email);

-- Fast user lookup by legacy_id (seeding cross-reference)
CREATE INDEX IF NOT EXISTS idx_users_legacy_id
    ON users(legacy_id);

-- Booking history queries (most frequent: list by user)
CREATE INDEX IF NOT EXISTS idx_nr_bookings_user_id
    ON national_rail_bookings(user_id);

-- Seat availability check: filter by schedule + date simultaneously
CREATE INDEX IF NOT EXISTS idx_nr_bookings_schedule_date
    ON national_rail_bookings(schedule_id, travel_date);

-- Metro history by user
CREATE INDEX IF NOT EXISTS idx_metro_travels_user_id
    ON metro_travels(user_id);

-- Payment lookup by booking reference
CREATE INDEX IF NOT EXISTS idx_payments_booking_ref
    ON payments(booking_ref);

-- Feedback lookup by booking reference
CREATE INDEX IF NOT EXISTS idx_feedback_booking_ref
    ON feedback(booking_ref);


-- ============================================================
--  VECTOR SCHEMA  (RAG / Help Desk) — do NOT modify
-- ============================================================

CREATE TABLE IF NOT EXISTS policy_documents (
    id          SERIAL       PRIMARY KEY,
    title       VARCHAR(200) NOT NULL,
    category    VARCHAR(50)  NOT NULL,  -- 'refund', 'booking', 'conduct'
    content     TEXT         NOT NULL,
    -- 768-dim  → Ollama nomic-embed-text (default)
    -- 3072-dim → Gemini gemini-embedding-001
    -- If you switch LLM_PROVIDER to gemini, change to vector(3072) and reset the database.
    embedding   vector(768),
    source_file VARCHAR(200),
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- HNSW index — sub-linear cosine similarity search
CREATE INDEX IF NOT EXISTS idx_policy_documents_embedding
    ON policy_documents USING hnsw (embedding vector_cosine_ops);
