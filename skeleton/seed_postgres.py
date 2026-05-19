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

import psycopg2
from psycopg2.extras import execute_values

# ── resolve paths ────────────────────────────────────────────────────────────
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "train-mock-data"

print("DATA_DIR =", DATA_DIR)
print("bookings exists =", (DATA_DIR / "bookings.json").exists())
print("feedback exists =", (DATA_DIR / "feedback.json").exists())

sys.path.insert(0, str(PROJECT_DIR))
from skeleton import config as cfg


def load(filename):
    path = DATA_DIR / filename
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def connect():
    try:
        conn = psycopg2.connect(
            host=cfg.PG_HOST,
            port=cfg.PG_PORT,
            dbname=cfg.PG_DB,
            user=cfg.PG_USER,
            password=cfg.PG_PASSWORD,
        )

        print("PostgreSQL connected successfully.")
        return conn

    except Exception as e:
        print("\nPostgreSQL connection failed.")
        print(f"HOST: {cfg.PG_HOST}")
        print(f"PORT: {cfg.PG_PORT}")
        print(f"DB: {cfg.PG_DB}")
        print(f"USER: {cfg.PG_USER}")
        print(f"\nERROR:\n{e}")
        sys.exit(1)


def insert_many(cur, table, columns, rows):
    if not rows:
        return 0
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s ON CONFLICT DO NOTHING"
    execute_values(cur, sql, rows)
    return len(rows)


# ── seeders ──────────────────────────────────────────────────────────────────

def seed_metro_stations(cur):
    data = load("metro_stations.json")
    columns = ["station_id", "station_name"]
    
    # Extracts "station_id" and "name" keys from your JSON objects
    rows = [(item["station_id"], item["name"]) for item in data]
    
    count = insert_many(cur, "metro_stations", columns, rows)
    print(f"  -> Seeded {count} metro stations.")


def seed_national_rail_stations(cur):
    data = load("national_rail_stations.json")
    columns = ["station_id", "station_name"]
    
    # Extracts "station_id" and "name" keys from your JSON objects
    rows = [(item["station_id"], item["name"]) for item in data]
    
    count = insert_many(cur, "national_rail_stations", columns, rows)
    print(f"  -> Seeded {count} national rail stations.")


def seed_metro_schedules(cur):
    data = load("metro_schedules.json")
    columns = ["schedule_id", "line", "direction", "origin_station_id", "destination_station_id"]
    
    rows = [
        (
            item["schedule_id"], 
            item["line"], 
            item["direction"], 
            item["origin_station_id"], 
            item["destination_station_id"]
        ) 
        for item in data
    ]
    
    count = insert_many(cur, "metro_schedules", columns, rows)
    print(f"  -> Seeded {count} metro schedules.")


def seed_national_rail_schedules(cur):
    data = load("national_rail_schedules.json")
    columns = ["schedule_id", "line", "service_type", "direction", "origin_station_id", "destination_station_id"]
    
    rows = [
        (
            item["schedule_id"], 
            item["line"], 
            item["service_type"], 
            item["direction"], 
            item["origin_station_id"], 
            item["destination_station_id"]
        ) 
        for item in data
    ]
    
    count = insert_many(cur, "national_rail_schedules", columns, rows)
    print(f"  -> Seeded {count} national rail schedules.")


def seed_seat_layouts(cur):
    data = load("national_rail_seat_layouts.json")
    
    # FIX: Wrap "row" and "column" in escaped double-quotes to bypass SQL reserved keyword restrictions
    columns = ["layout_id", "schedule_id", "coach", "fare_class", "seat_id", '"row"', '"column"']
    
    # Flattens nested 'coaches' and 'seats' arrays inside seat layouts
    rows = []
    for item in data:
        layout_id = item["layout_id"]
        schedule_id = item["schedule_id"]
        for coach_item in item["coaches"]:
            coach = coach_item["coach"]
            fare_class = coach_item["fare_class"]
            for seat in coach_item["seats"]:
                rows.append((
                    layout_id,
                    schedule_id,
                    coach,
                    fare_class,
                    seat["seat_id"],
                    seat["row"],
                    seat["column"]
                ))
    
    count = insert_many(cur, "seat_layouts", columns, rows)
    print(f"  -> Seeded {count} seat layout mappings.")


def seed_users(cur):
    data = load("registered_users.json")
    columns = ["user_id", "full_name", "email", "phone", "date_of_birth", "registered_at"]
    
    rows = [
        (
            item["user_id"], 
            item["full_name"], 
            item["email"], 
            item["phone"], 
            item["date_of_birth"], 
            item["registered_at"]
        ) 
        for item in data
    ]
    
    count = insert_many(cur, "users", columns, rows)
    print(f"  -> Seeded {count} users.")


def seed_national_rail_bookings(cur):
    data = load("bookings.json")
    columns = [
        "booking_id", "user_id", "schedule_id", "origin_station_id", 
        "destination_station_id", "travel_date", "departure_time", 
        "ticket_type", "fare_class", "coach", "seat_id", "amount_usd", "status", "booked_at"
    ]
    
    rows = [
        (
            item["booking_id"],
            item["user_id"],
            item["schedule_id"],
            item["origin_station_id"],
            item["destination_station_id"],
            item["travel_date"],
            item["departure_time"],
            item["ticket_type"],
            item["fare_class"],
            item["coach"],
            item["seat_id"],
            item["amount_usd"],
            item["status"],
            item["booked_at"]
        )
        for item in data
    ]
    
    count = insert_many(cur, "national_rail_bookings", columns, rows)
    print(f"  -> Seeded {count} national rail bookings.")


def seed_metro_travels(cur):
    data = load("metro_travel_history.json")
    columns = [
        "trip_id", "user_id", "schedule_id", "origin_station_id", 
        "destination_station_id", "travel_date", "ticket_type", 
        "day_pass_ref", "amount_usd", "status", "travelled_at"
    ]
    
    rows = [
        (
            item["trip_id"],
            item["user_id"],
            item["schedule_id"],
            item["origin_station_id"],
            item["destination_station_id"],
            item["travel_date"],
            item["ticket_type"],
            item.get("day_pass_ref"), 
            item["amount_usd"],
            item["status"],
            item.get("travelled_at") # <-- Use .get() here so it safely passes 'null' to SQL
        )
        for item in data
    ]
    
    count = insert_many(cur, "metro_travels", columns, rows)
    print(f"  -> Seeded {count} metro travel records.")



def seed_payments(cur):
    data = load("payments.json")

    columns = [
        "payment_id",
        "booking_id",
        "amount_usd",
        "method",
        "status",
        "paid_at"
    ]

    # Fetch valid IDs from BOTH National Rail and Metro tables
    cur.execute("SELECT booking_id FROM national_rail_bookings")
    valid_rail_ids = {row[0] for row in cur.fetchall()}
    
    cur.execute("SELECT trip_id FROM metro_travels")
    valid_metro_ids = {row[0] for row in cur.fetchall()}

    # Combine them into a single set of valid transit identifiers
    all_valid_ids = valid_rail_ids.union(valid_metro_ids)

    rows = []
    skipped = 0

    for item in data:
        # Don't skip if it matches either table's ID
        if item["booking_id"] not in all_valid_ids:
            print(f"  -> Skipping truly invalid booking_id: {item['booking_id']}")
            skipped += 1
            continue

        rows.append((
            item["payment_id"],
            item["booking_id"],
            item["amount_usd"],
            item["method"],
            item["status"],
            item["paid_at"]
        ))

    count = insert_many(cur, "payments", columns, rows)

    print(f"  -> Seeded {count} payments.")
    print(f"  -> Skipped {skipped} truly invalid payment records.")


def seed_feedback(cur):
    data = load("feedback.json")
    columns = ["feedback_id", "booking_id", "user_id", "rating", "comment", "submitted_at"]

    # Fetch valid IDs from BOTH National Rail and Metro tables
    cur.execute("SELECT booking_id FROM national_rail_bookings")
    valid_rail_ids = {row[0] for row in cur.fetchall()}
    
    cur.execute("SELECT trip_id FROM metro_travels")
    valid_metro_ids = {row[0] for row in cur.fetchall()}

    # Combine them into a single set of valid transit identifiers
    all_valid_ids = valid_rail_ids.union(valid_metro_ids)

    rows = []
    skipped = 0

    for item in data:
        booking_id = item["booking_id"]
        # Don't skip if it matches either table's ID
        if booking_id not in all_valid_ids:
            print(f" -> Skipping truly invalid booking_id: {booking_id}")
            skipped += 1
            continue

        rows.append((
            item["feedback_id"],
            booking_id,
            item["user_id"],
            item["rating"],
            item.get("comment"),
            item["submitted_at"],
        ))

    if not rows:
        print(" -> Seeded 0 feedback entries.")
        print(f" -> Skipped {skipped} invalid feedback records.")
        return 0

    insert_many(cur, "feedback", columns, rows)
    print(f" -> Seeded {len(rows)} feedback entries.")
    print(f" -> Skipped {skipped} invalid feedback records.")
    return len(rows)

# ── main ─────────────────────────────────────────────────────────────────────

def main():
    print("Connecting to PostgreSQL...")
    conn = connect()
    conn.autocommit = False
    cur = conn.cursor()

    try:
        print("Seeding tables (dependency order):")
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
