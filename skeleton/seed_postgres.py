"""
Seed PostgreSQL with all TransitFlow mock data from train-mock-data/.

Usage:
    python skeleton/seed_postgres.py

Run AFTER docker-compose up -d.
You must first design and create your tables in databases/relational/schema.sql.
Safe to re-run: implement your inserts with ON CONFLICT DO NOTHING.
"""

import json
import os
import sys
import uuid
from argon2 import PasswordHasher

import psycopg2
from psycopg2.extras import execute_values

# ── resolve paths ────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR    = os.path.join(PROJECT_DIR, "train-mock-data")

sys.path.insert(0, PROJECT_DIR)
from skeleton import config as cfg

# We use Argon2 for hashing passwords and security answers
ph = PasswordHasher()

# Namespace for deterministic UUID v5 generation
UUID_NAMESPACE = uuid.NAMESPACE_URL

# Global dictionary to map legacy user IDs (e.g. RU01) to generated UUIDs
LEGACY_TO_UUID = {}

def get_user_uuid(legacy_id: str) -> str:
    if legacy_id not in LEGACY_TO_UUID:
        LEGACY_TO_UUID[legacy_id] = str(uuid.uuid5(UUID_NAMESPACE, legacy_id))
    return LEGACY_TO_UUID[legacy_id]

def load(filename):
    with open(os.path.join(DATA_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


def connect():
    return psycopg2.connect(
        host=cfg.PG_HOST,
        port=cfg.PG_PORT,
        dbname=cfg.PG_DB,
        user=cfg.PG_USER,
        password=cfg.PG_PASSWORD,
    )


def insert_many(cur, table, columns, rows):
    """Bulk insert with ON CONFLICT DO NOTHING. Returns row count inserted."""
    if not rows:
        return 0
    sql = (
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s "
        f"ON CONFLICT DO NOTHING"
    )
    execute_values(cur, sql, rows)
    return cur.rowcount


# ── seeders ──────────────────────────────────────────────────────────────────

def seed_metro_stations(cur):
    data = load("metro_stations.json")
    
    stations_rows = []
    lines_rows = []
    
    for item in data:
        sid = item["station_id"]
        nr_id = item.get("interchange_national_rail_station_id")
        
        stations_rows.append((
            sid,
            item["name"],
            item.get("is_interchange_metro", False),
            item.get("is_interchange_national_rail", False),
            nr_id
        ))
        
        for line in item.get("lines", []):
            lines_rows.append((sid, line))
            
    insert_many(cur, "metro_stations", 
                ["station_id", "name", "is_interchange_metro", "is_interchange_national_rail", "interchange_national_rail_station_id"],
                stations_rows)
    insert_many(cur, "metro_station_lines", ["station_id", "line"], lines_rows)
    print(f"Inserted {len(stations_rows)} metro_stations")


def seed_national_rail_stations(cur):
    data = load("national_rail_stations.json")
    
    stations_rows = []
    lines_rows = []
    
    for item in data:
        sid = item["station_id"]
        ms_id = item.get("interchange_metro_station_id")
        
        stations_rows.append((
            sid,
            item["name"],
            item.get("is_interchange_national_rail", False),
            item.get("is_interchange_metro", False),
            ms_id
        ))
        
        for line in item.get("lines", []):
            lines_rows.append((sid, line))
            
    insert_many(cur, "national_rail_stations",
                ["station_id", "name", "is_interchange_national_rail", "is_interchange_metro", "interchange_metro_station_id"],
                stations_rows)
    insert_many(cur, "national_rail_station_lines", ["station_id", "line"], lines_rows)
    print(f"Inserted {len(stations_rows)} national_rail_stations")


def seed_metro_schedules(cur):
    data = load("metro_schedules.json")
    
    schedules_rows = []
    stops_rows = []
    operates_on_rows = []
    
    for item in data:
        sch_id = item["schedule_id"]
        schedules_rows.append((
            sch_id,
            item["line"],
            item["direction"],
            item["origin_station_id"],
            item["destination_station_id"],
            item["first_train_time"],
            item["last_train_time"],
            item["base_fare_usd"],
            item["per_stop_rate_usd"],
            item["frequency_min"]
        ))
        
        stops = item.get("stops_in_order", [])
        travel_times = item.get("travel_time_from_origin_min", {})
        
        for idx, stop_id in enumerate(stops):
            tt = travel_times.get(stop_id, 0)
            stops_rows.append((sch_id, stop_id, idx + 1, tt))
            
        for day in item.get("operates_on", []):
            operates_on_rows.append((sch_id, day))
            
    insert_many(cur, "metro_schedules",
                ["schedule_id", "line", "direction", "origin_station_id", "destination_station_id",
                 "first_train_time", "last_train_time", "base_fare_usd", "per_stop_rate_usd", "frequency_min"],
                schedules_rows)
    insert_many(cur, "metro_schedule_stops", ["schedule_id", "station_id", "stop_order", "travel_time_from_origin_min"], stops_rows)
    insert_many(cur, "metro_schedule_operates_on", ["schedule_id", "day_of_week"], operates_on_rows)
    print(f"Inserted {len(schedules_rows)} metro_schedules")


def seed_national_rail_schedules(cur):
    data = load("national_rail_schedules.json")
    
    schedules_rows = []
    stops_rows = []
    fare_classes_rows = []
    operates_on_rows = []
    
    for item in data:
        sch_id = item["schedule_id"]
        schedules_rows.append((
            sch_id,
            item["line"],
            item["service_type"],
            item["direction"],
            item["origin_station_id"],
            item["destination_station_id"],
            item["first_train_time"],
            item["last_train_time"],
            item["frequency_min"]
        ))
        
        stops = item.get("stops_in_order", [])
        travel_times = item.get("travel_time_from_origin_min", {})
        for idx, stop_id in enumerate(stops):
            tt = travel_times.get(stop_id, 0)
            stops_rows.append((sch_id, stop_id, idx + 1, tt))
            
        fares = item.get("fare_classes", {})
        for fc_name, fc_data in fares.items():
            fare_classes_rows.append((
                sch_id, fc_name, fc_data["base_fare_usd"], fc_data["per_stop_rate_usd"]
            ))
            
        for day in item.get("operates_on", []):
            operates_on_rows.append((sch_id, day))
            
    insert_many(cur, "national_rail_schedules",
                ["schedule_id", "line", "service_type", "direction", "origin_station_id", "destination_station_id",
                 "first_train_time", "last_train_time", "frequency_min"],
                schedules_rows)
    insert_many(cur, "national_rail_schedule_stops", ["schedule_id", "station_id", "stop_order", "travel_time_from_origin_min"], stops_rows)
    insert_many(cur, "national_rail_fare_classes", ["schedule_id", "fare_class", "base_fare_usd", "per_stop_rate_usd"], fare_classes_rows)
    insert_many(cur, "national_rail_schedule_operates_on", ["schedule_id", "day_of_week"], operates_on_rows)
    print(f"Inserted {len(schedules_rows)} national_rail_schedules")


def seed_seat_layouts(cur):
    data = load("national_rail_seat_layouts.json")
    
    layouts_rows = []
    coaches_rows = []
    seats_rows = []
    
    for item in data:
        layout_id = item["layout_id"]
        layouts_rows.append((layout_id, item["schedule_id"]))
        
        for coach in item.get("coaches", []):
            coach_id = coach["coach"]
            coaches_rows.append((layout_id, coach_id, coach["fare_class"]))
            
            for seat in coach.get("seats", []):
                seats_rows.append((layout_id, coach_id, seat["seat_id"], seat["row"], seat["column"]))
                
    insert_many(cur, "seat_layouts", ["layout_id", "schedule_id"], layouts_rows)
    insert_many(cur, "coaches", ["layout_id", "coach", "fare_class"], coaches_rows)
    insert_many(cur, "seats", ["layout_id", "coach", "seat_id", "row", "col"], seats_rows)
    print(f"Inserted {len(layouts_rows)} seat_layouts")


def seed_users(cur):
    data = load("registered_users.json")
    
    users_rows = []
    credentials_rows = []
    
    for item in data:
        legacy_id = item["user_id"]
        user_uuid = get_user_uuid(legacy_id)
        
        full_name = item["full_name"]
        parts = full_name.split(" ", 1)
        first_name = parts[0]
        surname = parts[1] if len(parts) > 1 else ""
        
        users_rows.append((
            user_uuid,
            legacy_id,
            first_name,
            surname,
            item["email"],
            item.get("phone"),
            item.get("date_of_birth"),
            item.get("registered_at")
        ))
        
        pw_hash = ph.hash(item["password"])
        ans_hash = ph.hash(item["secret_answer"].lower().strip())
        
        credentials_rows.append((
            user_uuid,
            pw_hash,
            item["secret_question"],
            ans_hash
        ))
        
    insert_many(cur, "users",
                ["user_id", "legacy_id", "first_name", "surname", "email", "phone", "date_of_birth", "registered_at"],
                users_rows)
    insert_many(cur, "user_credentials",
                ["user_id", "password_hash", "secret_question", "secret_answer_hash"],
                credentials_rows)
    print(f"Inserted {len(users_rows)} users")


def seed_national_rail_bookings(cur):
    data = load("bookings.json")
    
    rows = []
    for item in data:
        user_uuid = get_user_uuid(item["user_id"])
        rows.append((
            item["booking_id"],
            user_uuid,
            item["schedule_id"],
            item["origin_station_id"],
            item["destination_station_id"],
            item["travel_date"],
            item["departure_time"],
            item.get("ticket_type", "single"),
            item["fare_class"],
            item["coach"],
            item["seat_id"],
            item["stops_travelled"],
            item["amount_usd"],
            item["status"],
            item["booked_at"],
            item.get("travelled_at")
        ))
        
    insert_many(cur, "national_rail_bookings",
                ["booking_id", "user_id", "schedule_id", "origin_station_id", "destination_station_id",
                 "travel_date", "departure_time", "ticket_type", "fare_class", "coach", "seat_id",
                 "stops_travelled", "amount_usd", "status", "booked_at", "travelled_at"],
                rows)
    print(f"Inserted {len(rows)} national_rail_bookings")


def seed_metro_travels(cur):
    data = load("metro_travel_history.json")
    
    rows = []
    for item in data:
        user_uuid = get_user_uuid(item["user_id"])
        rows.append((
            item["trip_id"],
            user_uuid,
            item["schedule_id"],
            item["origin_station_id"],
            item["destination_station_id"],
            item["travel_date"],
            item["ticket_type"],
            item.get("day_pass_ref"),
            item.get("stops_travelled"),
            item["amount_usd"],
            item["status"],
            item.get("purchased_at"),
            item.get("travelled_at")
        ))
        
    insert_many(cur, "metro_travels",
                ["trip_id", "user_id", "schedule_id", "origin_station_id", "destination_station_id",
                 "travel_date", "ticket_type", "day_pass_ref", "stops_travelled", "amount_usd",
                 "status", "purchased_at", "travelled_at"],
                rows)
    print(f"Inserted {len(rows)} metro_travels")


def seed_payments(cur):
    data = load("payments.json")
    
    rows = []
    for item in data:
        b_ref = item["booking_id"]
        b_type = "rail" if b_ref.startswith("BK") else "metro"
        
        rows.append((
            item["payment_id"],
            b_ref,
            b_type,
            item["amount_usd"],
            item["method"],
            item["status"],
            item["paid_at"]
        ))
        
    insert_many(cur, "payments",
                ["payment_id", "booking_ref", "booking_type", "amount_usd", "method", "status", "paid_at"],
                rows)
    print(f"Inserted {len(rows)} payments")


def seed_feedback(cur):
    data = load("feedback.json")
    
    rows = []
    for item in data:
        b_ref = item["booking_id"]
        b_type = "rail" if b_ref.startswith("BK") else "metro"
        user_uuid = get_user_uuid(item["user_id"])
        
        rows.append((
            item["feedback_id"],
            b_ref,
            b_type,
            user_uuid,
            item["rating"],
            item.get("comment"),
            item["submitted_at"]
        ))
        
    insert_many(cur, "feedback",
                ["feedback_id", "booking_ref", "booking_type", "user_id", "rating", "comment", "submitted_at"],
                rows)
    print(f"Inserted {len(rows)} feedback")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    print("Connecting to PostgreSQL...")
    conn = connect()
    conn.autocommit = False
    cur = conn.cursor()

    try:
        print("Seeding tables (dependency order):")
        # SET CONSTRAINTS ALL DEFERRED to avoid circular dependency issues
        cur.execute("SET CONSTRAINTS ALL DEFERRED;")
        
        seed_metro_stations(cur)
        seed_national_rail_stations(cur)
        seed_metro_schedules(cur)
        seed_national_rail_schedules(cur)
        seed_seat_layouts(cur)
        seed_users(cur)
        seed_national_rail_bookings(cur)
        seed_metro_travels(cur)
        seed_payments(cur)
        seed_feedback(cur)
        conn.commit()
        print("\nAll done. Database seeded successfully.")
    except Exception as e:
        conn.rollback()
        print(f"\nError: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
