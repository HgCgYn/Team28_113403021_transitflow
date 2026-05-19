

-- 1. METRO STATIONS
CREATE TABLE IF NOT EXISTS metro_stations (
    station_id     VARCHAR(50) PRIMARY KEY,
    station_name   VARCHAR(100) NOT NULL
);

-- 2. NATIONAL RAIL STATIONS
CREATE TABLE IF NOT EXISTS national_rail_stations (
    station_id     VARCHAR(50) PRIMARY KEY,
    station_name   VARCHAR(100) NOT NULL
);

-- 3. METRO SCHEDULES
CREATE TABLE IF NOT EXISTS metro_schedules (
    schedule_id            VARCHAR(50) PRIMARY KEY,
    line                   VARCHAR(50) NOT NULL,
    direction              VARCHAR(50) NOT NULL,
    origin_station_id      VARCHAR(50) REFERENCES metro_stations(station_id) ON DELETE CASCADE,
    destination_station_id VARCHAR(50) REFERENCES metro_stations(station_id) ON DELETE CASCADE
);

-- 4. NATIONAL RAIL SCHEDULES
CREATE TABLE IF NOT EXISTS national_rail_schedules (
    schedule_id            VARCHAR(50) PRIMARY KEY,
    line                   VARCHAR(50) NOT NULL,
    service_type           VARCHAR(50) NOT NULL, -- 'Normal' or 'Express'
    direction              VARCHAR(50) NOT NULL,
    origin_station_id      VARCHAR(50) REFERENCES national_rail_stations(station_id) ON DELETE CASCADE,
    destination_station_id VARCHAR(50) REFERENCES national_rail_stations(station_id) ON DELETE CASCADE
);

-- EXTENSION: SCHEDULE SEQUENCE TRACKING (To fulfill "correct order" lookup)
CREATE TABLE IF NOT EXISTS metro_schedule_stops (
    schedule_id   VARCHAR(50) REFERENCES metro_schedules(schedule_id) ON DELETE CASCADE,
    station_id    VARCHAR(50) REFERENCES metro_stations(station_id) ON DELETE CASCADE,
    stop_sequence INT NOT NULL,
    PRIMARY KEY (schedule_id, station_id)
);

CREATE TABLE IF NOT EXISTS national_rail_schedule_stops (
    schedule_id   VARCHAR(50) REFERENCES national_rail_schedules(schedule_id) ON DELETE CASCADE,
    station_id    VARCHAR(50) REFERENCES national_rail_stations(station_id) ON DELETE CASCADE,
    stop_sequence INT NOT NULL,
    PRIMARY KEY (schedule_id, station_id)
);

-- EXTENSION: FARE CONFIGURATIONS
CREATE TABLE IF NOT EXISTS metro_fares (
    schedule_id       VARCHAR(50) PRIMARY KEY REFERENCES metro_schedules(schedule_id) ON DELETE CASCADE,
    base_fare_usd     NUMERIC(10, 2) NOT NULL,
    per_stop_rate_usd NUMERIC(10, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS national_rail_fares (
    schedule_id       VARCHAR(50) REFERENCES national_rail_schedules(schedule_id) ON DELETE CASCADE,
    fare_class        VARCHAR(50) NOT NULL, -- 'standard' or 'first'
    base_fare_usd     NUMERIC(10, 2) NOT NULL,
    per_stop_rate_usd NUMERIC(10, 2) NOT NULL,
    PRIMARY KEY (schedule_id, fare_class)
);

-- 5. SEAT LAYOUTS
CREATE TABLE IF NOT EXISTS seat_layouts (
    layout_id   VARCHAR(50),
    schedule_id VARCHAR(50) REFERENCES national_rail_schedules(schedule_id) ON DELETE CASCADE,
    coach       VARCHAR(10) NOT NULL,
    fare_class  VARCHAR(50) NOT NULL,
    seat_id     VARCHAR(10) NOT NULL,
    "row"       INT NOT NULL,
    "column"    VARCHAR(5) NOT NULL,
    PRIMARY KEY (layout_id, schedule_id, coach, seat_id)
);

-- 6. USERS (EXTENDED with Authentication & Profile fields)
CREATE TABLE IF NOT EXISTS users (
    user_id         VARCHAR(50) PRIMARY KEY,
    full_name       VARCHAR(100) NOT NULL,
    first_name      VARCHAR(50),
    surname         VARCHAR(50),
    email           VARCHAR(100) UNIQUE NOT NULL,
    phone           VARCHAR(50),
    date_of_birth   DATE,
    year_of_birth   INT,
    password        VARCHAR(255), -- Stored plain text for teaching context
    secret_question TEXT,
    secret_answer   TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    registered_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 7. NATIONAL RAIL BOOKINGS
CREATE TABLE IF NOT EXISTS national_rail_bookings (
    booking_id             VARCHAR(50) PRIMARY KEY,
    user_id                VARCHAR(50) REFERENCES users(user_id) ON DELETE CASCADE,
    schedule_id            VARCHAR(50) REFERENCES national_rail_schedules(schedule_id) ON DELETE CASCADE,
    origin_station_id      VARCHAR(50) REFERENCES national_rail_stations(station_id),
    destination_station_id VARCHAR(50) REFERENCES national_rail_stations(station_id),
    travel_date            DATE NOT NULL,
    departure_time         TIME NOT NULL,
    ticket_type            VARCHAR(50) NOT NULL,
    fare_class             VARCHAR(50) NOT NULL,
    coach                  VARCHAR(10) NOT NULL,
    seat_id                VARCHAR(10) NOT NULL,
    amount_usd             NUMERIC(10, 2) NOT NULL,
    status                 VARCHAR(50) NOT NULL, -- 'confirmed', 'cancelled'
    booked_at              TIMESTAMPTZ NOT NULL
);

-- 8. METRO TRAVELS
CREATE TABLE IF NOT EXISTS metro_travels (
    trip_id                VARCHAR(50) PRIMARY KEY,
    user_id                VARCHAR(50) REFERENCES users(user_id) ON DELETE CASCADE,
    schedule_id            VARCHAR(50) REFERENCES metro_schedules(schedule_id) ON DELETE CASCADE,
    origin_station_id      VARCHAR(50) REFERENCES metro_stations(station_id),
    destination_station_id VARCHAR(50) REFERENCES metro_stations(station_id),
    travel_date            DATE NOT NULL,
    ticket_type            VARCHAR(50) NOT NULL,
    day_pass_ref           VARCHAR(50),
    amount_usd             NUMERIC(10, 2) NOT NULL,
    status                 VARCHAR(50) NOT NULL,
    travelled_at           TIMESTAMPTZ
);

-- 9. PAYMENTS
CREATE TABLE IF NOT EXISTS payments (
    payment_id VARCHAR(50) PRIMARY KEY,
    booking_id VARCHAR(50), -- Removed the foreign key constraint
    amount_usd NUMERIC(10, 2) NOT NULL,
    method     VARCHAR(50) NOT NULL,
    status     VARCHAR(50) NOT NULL, 
    paid_at    TIMESTAMPTZ NOT NULL
);

-- 10. FEEDBACK
CREATE TABLE IF NOT EXISTS feedback (
    feedback_id  VARCHAR(50) PRIMARY KEY,
    booking_id   VARCHAR(50), -- Removed the foreign key constraint
    user_id      VARCHAR(50) REFERENCES users(user_id) ON DELETE CASCADE,
    rating       INT NOT NULL CHECK (rating >= 1 AND rating <= 5),
    comment      TEXT,
    submitted_at TIMESTAMPTZ NOT NULL
);

-- ============================================================
--  VECTOR SCHEMA  (RAG / Help Desk) — do not modify
-- ============================================================
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS policy_documents (
    id          SERIAL       PRIMARY KEY,
    title       VARCHAR(200) NOT NULL,
    category    VARCHAR(50)  NOT NULL,  
    content     TEXT         NOT NULL,
    embedding   vector(768),
    source_file VARCHAR(200),
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS policy_documents_embedding_idx ON policy_documents USING hnsw (embedding vector_cosine_ops);
-- ============================================================