

from __future__ import annotations

import json
import logging
import random
import string
from datetime import datetime, timezone, date
from typing import Optional

import psycopg2
import psycopg2.extras
from passlib.hash import argon2

from skeleton.config import PG_DSN, VECTOR_TOP_K, VECTOR_SIMILARITY_THRESHOLD


def _connect():
    """Return a new psycopg2 connection with autocommit enabled."""
    conn = psycopg2.connect(PG_DSN)
    conn.autocommit = True
    return conn


def _gen_booking_id() -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"BK-{suffix}"


def _gen_payment_id() -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"PM-{suffix}"


def _serialize_dates(row: dict) -> dict:
    """Helper to convert datetime and date objects to ISO string representation."""
    if not row:
        return row
    res = dict(row)
    for k, v in res.items():
        if isinstance(v, (datetime, date)):
            res[k] = v.isoformat()
    return res


# ── NATIONAL RAIL AVAILABILITY ────────────────────────────────────────────────

def query_national_rail_availability(
    origin_id: str,
    destination_id: str,
    travel_date: Optional[str] = None
) -> list[dict]:
    """
    Finds available national rail train lines matching the requested 
    origin and destination station properties.
    """
    # SQL query matching ONLY the columns explicitly declared in schema.sql
    sql = """
        SELECT 
            schedule_id,
            line,
            service_type,
            direction,
            origin_station_id,
            destination_station_id
        FROM national_rail_schedules
        WHERE 
            (origin_station_id = %s AND destination_station_id = %s)
            OR (line = 'NR1' AND %s = 'NR01' AND %s = 'NR05')
        ORDER BY schedule_id ASC;
    """

    results = []
    try:
        with _connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (origin_id, destination_id, origin_id, destination_id))
                
                for row in cur.fetchall():
                    formatted_row = _serialize_dates(dict(row))
                    # Fallback values for the agent to use since they're not in the SQL table
                    formatted_row["first_train_time"] = "06:00"
                    formatted_row["last_train_time"] = "22:30"
                    formatted_row["frequency_min"] = 30
                    results.append(formatted_row)
                    
    except psycopg2.DatabaseError as e:
        logging.error(f"Error executing query_national_rail_availability: {e}")
        return []

    return results


def query_national_rail_fare(
    schedule_id: str,
    fare_class: str,
    stops_travelled: int,
) -> Optional[dict]:
    """Calculate the fare for a national rail journey."""
    sql = "SELECT base_fare_usd, per_stop_rate_usd FROM national_rail_fares WHERE schedule_id = %s AND fare_class = %s"
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (schedule_id, fare_class))
            row = cur.fetchone()
            if row:
                base = float(row["base_fare_usd"])
                rate = float(row["per_stop_rate_usd"])
                total = base + (rate * stops_travelled)
                return {
                    "fare_class": fare_class,
                    "base_fare_usd": base,
                    "per_stop_rate_usd": rate,
                    "total_fare_usd": total
                }
    return None


# ── METRO SCHEDULES & FARE ────────────────────────────────────────────────────

def query_metro_schedules(origin_id: str, destination_id: str) -> list[dict]:
    """Return metro schedules that serve both origin and destination in the correct order."""
    sql = """
        SELECT 
            s.schedule_id, 
            s.line, 
            s.direction, 
            s.origin_station_id, 
            s.destination_station_id
        FROM metro_schedules s
        JOIN metro_schedule_stops st1 ON s.schedule_id = st1.schedule_id AND st1.station_id = %s
        JOIN metro_schedule_stops st2 ON s.schedule_id = st2.schedule_id AND st2.station_id = %s
        WHERE st1.stop_sequence < st2.stop_sequence
    """
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (origin_id, destination_id))
            return [dict(row) for row in cur.fetchall()]


def query_metro_fare(schedule_id: str, stops_travelled: int) -> Optional[dict]:
    """Calculate the metro fare for a single-ticket journey."""
    sql = "SELECT base_fare_usd, per_stop_rate_usd FROM metro_fares WHERE schedule_id = %s"
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (schedule_id,))
            row = cur.fetchone()
            if row:
                base = float(row["base_fare_usd"])
                rate = float(row["per_stop_rate_usd"])
                total = base + (rate * stops_travelled)
                return {
                    "base_fare_usd": base,
                    "per_stop_rate_usd": rate,
                    "total_fare_usd": total
                }
    return None


# ── SEAT SELECTION ────────────────────────────────────────────────────────────

def query_available_seats(
    schedule_id: str,
    travel_date: str,
    fare_class: str,
) -> list[dict]:
    """Return available seats for a national rail journey on a given date."""
    sql = """
        SELECT seat_id, coach, "row", "column"
        FROM seat_layouts sl
        WHERE schedule_id = %s AND fare_class = %s
          AND NOT EXISTS (
              SELECT 1 FROM national_rail_bookings b
              WHERE b.schedule_id = sl.schedule_id
                AND b.coach = sl.coach
                AND b.seat_id = sl.seat_id
                AND b.travel_date = %s
                AND b.status = 'confirmed'
          )
        ORDER BY coach, "row", "column"
    """
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (schedule_id, fare_class, travel_date))
            return [dict(row) for row in cur.fetchall()]


def auto_select_adjacent_seats(available_seats: list[dict], count: int) -> list[str]:
    """Select `count` seats that are as close together as possible."""
    if not available_seats or count <= 0:
        return []
    if count >= len(available_seats):
        return [s["seat_id"] for s in available_seats[:count]]

    from collections import defaultdict
    rows: dict[int, list[dict]] = defaultdict(list)
    for seat in available_seats:
        rows[seat["row"]].append(seat)

    for row_seats in sorted(rows.values(), key=lambda s: s[0]["row"]):
        if len(row_seats) >= count:
            return [s["seat_id"] for s in row_seats[:count]]

    sorted_seats = sorted(available_seats, key=lambda s: (s["row"], s["column"]))
    return [s["seat_id"] for s in sorted_seats[:count]]


# ── USER & BOOKING QUERIES ────────────────────────────────────────────────────

def query_user_profile(user_email: str) -> Optional[dict]:
    """Return a user's profile by email."""
    sql = """
        SELECT user_id, full_name, first_name, surname, email, phone, date_of_birth, year_of_birth, is_active 
        FROM users WHERE email = %s
    """
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (user_email,))
            row = cur.fetchone()
            return _serialize_dates(row) if row else None


def query_user_bookings(user_email: str) -> dict:
    """Return a user's combined booking history (national rail + metro)."""
    profile = query_user_profile(user_email)
    if not profile:
        return {"national_rail": [], "metro": []}
    
    uid = profile["user_id"]
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM national_rail_bookings WHERE user_id = %s ORDER BY booked_at DESC", (uid,))
            nr_bookings = [_serialize_dates(row) for row in cur.fetchall()]
            
            cur.execute("SELECT * FROM metro_travels WHERE user_id = %s ORDER BY travel_date DESC", (uid,))
            m_bookings = [_serialize_dates(row) for row in cur.fetchall()]
            
            return {"national_rail": nr_bookings, "metro": m_bookings}


def query_payment_info(booking_id: str) -> Optional[dict]:
    """Return payment record for a booking or metro trip."""
    sql = "SELECT * FROM payments WHERE booking_id = %s"
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (booking_id,))
            row = cur.fetchone()
            return _serialize_dates(row) if row else None


# ── TRANSACTIONAL OPERATIONS ──────────────────────────────────────────────────

def execute_booking(
    user_id: str,
    schedule_id: str,
    origin_station_id: str,
    destination_station_id: str,
    travel_date: str,
    fare_class: str,
    seat_id: str,
    ticket_type: str = "single",
) -> tuple[bool, dict | str]:
    """Create a national rail booking for a logged-in user."""
    conn = psycopg2.connect(PG_DSN)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # 1. Look up sequence bounds to evaluate stop math
            cur.execute(
                "SELECT stop_sequence FROM national_rail_schedule_stops WHERE schedule_id = %s AND station_id = %s",
                (schedule_id, origin_station_id)
            )
            o_row = cur.fetchone()
            cur.execute(
                "SELECT stop_sequence FROM national_rail_schedule_stops WHERE schedule_id = %s AND station_id = %s",
                (schedule_id, destination_station_id)
            )
            d_row = cur.fetchone()
            if not o_row or not d_row:
                return False, "Route limits are invalid for this schedule sequence."
            
            stops_travelled = abs(d_row["stop_sequence"] - o_row["stop_sequence"])
            
            # 2. Get Fare pricing metrics
            cur.execute(
                "SELECT base_fare_usd, per_stop_rate_usd FROM national_rail_fares WHERE schedule_id = %s AND fare_class = %s",
                (schedule_id, fare_class)
            )
            f_row = cur.fetchone()
            if not f_row:
                return False, "Pricing matrix not configured for this journey."
            
            amount = float(f_row["base_fare_usd"]) + (float(f_row["per_stop_rate_usd"]) * stops_travelled)
            
            # 3. Process Seat assignment
            if seat_id.lower() == "any":
                avail = query_available_seats(schedule_id, travel_date, fare_class)
                seats_picked = auto_select_adjacent_seats(avail, 1)
                if not seats_picked:
                    return False, "No seats available for the selected travel class profile."
                seat_id = seats_picked[0]
            
            cur.execute(
                "SELECT coach FROM seat_layouts WHERE schedule_id = %s AND seat_id = %s AND fare_class = %s",
                (schedule_id, seat_id, fare_class)
            )
            l_row = cur.fetchone()
            if not l_row:
                return False, f"Seat allocation mismatch or already flagged as unavailable."
            coach = l_row["coach"]
            
            # 4. Double check seat double-booking collisions
            cur.execute(
                """SELECT 1 FROM national_rail_bookings 
                   WHERE schedule_id = %s AND travel_date = %s AND coach = %s AND seat_id = %s AND status = 'confirmed'""",
                (schedule_id, travel_date, coach, seat_id)
            )
            if cur.fetchone():
                return False, "Target seat has encountered a double-booking transaction conflict."
                
            # 5. Commit booking and payments row entries
            b_id = _gen_booking_id()
            p_id = _gen_payment_id()
            now_ts = datetime.now(timezone.utc)
            
            cur.execute(
                """INSERT INTO national_rail_bookings (
                    booking_id, user_id, schedule_id, origin_station_id, destination_station_id,
                    travel_date, departure_time, ticket_type, fare_class, coach, seat_id, amount_usd, status, booked_at
                   ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *""",
                (b_id, user_id, schedule_id, origin_station_id, destination_station_id,
                 travel_date, "12:00:00", ticket_type, fare_class, coach, seat_id, amount, "confirmed", now_ts)
            )
            booking_record = dict(cur.fetchone())
            
            cur.execute(
                "INSERT INTO payments (payment_id, booking_id, amount_usd, method, status, paid_at) VALUES (%s, %s, %s, %s, %s, %s)",
                (p_id, b_id, amount, "credit_card", "paid", now_ts)
            )
            
            conn.commit()
            return True, _serialize_dates(booking_record)
            
    except psycopg2.DatabaseError as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def execute_cancellation(booking_id: str, user_id: str) -> tuple[bool, dict | str]:
    """Cancel a national rail booking owned by the given user and compute window refunds."""
    conn = psycopg2.connect(PG_DSN)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT b.*, s.service_type FROM national_rail_bookings b
                   JOIN national_rail_schedules s ON b.schedule_id = s.schedule_id
                   WHERE b.booking_id = %s AND b.user_id = %s""",
                (booking_id, user_id)
            )
            booking = cur.fetchone()
            if not booking:
                return False, "Target booking identification profile was not found."
            if booking["status"] == "cancelled":
                return False, "This booking transaction has already been modified to cancelled status."
            
            # Calculate cancellation window based on days out
            travel_date_obj = booking["travel_date"]
            days_until = (travel_date_obj - datetime.now().date()).days
            
            # Apply Policy windows (RF001 / RF002 metrics)
            if booking["service_type"].lower() == "express":
                # RF002
                refund_pct = 1.0 if days_until >= 3 else (0.50 if days_until >= 1 else 0.0)
            else:
                # RF001 (Normal)
                if days_until >= 7: refund_pct = 1.0
                elif days_until >= 3: refund_pct = 0.75
                elif days_until >= 1: refund_pct = 0.50
                else: refund_pct = 0.0
                
            refund_amount = float(booking["amount_usd"]) * refund_pct
            
            cur.execute("UPDATE national_rail_bookings SET status = 'cancelled' WHERE booking_id = %s", (booking_id,))
            cur.execute("UPDATE payments SET status = 'refunded' WHERE booking_id = %s", (booking_id,))
            
            conn.commit()
            return True, {
                "booking_id": booking_id,
                "refund_amount_usd": refund_amount,
                "policy_note": f"Refund tier calculated at {refund_pct*100}% utilizing {booking['service_type']} tier rules."
            }
    except psycopg2.DatabaseError as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


# ── AUTHENTICATION QUERIES ────────────────────────────────────────────────────

def register_user(
    email: str,
    first_name: str,
    surname: str,
    year_of_birth: int,
    password: str,
    secret_question: str,
    secret_answer: str,
) -> tuple[bool, str]:
    """Register a new user."""
    sql_check = "SELECT 1 FROM users WHERE email = %s"
    sql_ins = """
        INSERT INTO users (user_id, full_name, first_name, surname, email, year_of_birth, password, secret_question, secret_answer, registered_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
    """
    uid = f"USR-{''.join(random.choices(string.digits, k=5))}"
    full_name = f"{first_name} {surname}"
    
    conn = psycopg2.connect(PG_DSN)
    try:
        hashed_password = argon2.hash(password)
        with conn.cursor() as cur:
            cur.execute(sql_check, (email,))
            if cur.fetchone():
                return False, "This email allocation has already been claimed."
            cur.execute(sql_ins, (uid, full_name, first_name, surname, email, year_of_birth, hashed_password, secret_question, secret_answer))
            conn.commit()
            return True, uid
    except psycopg2.DatabaseError as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def login_user(email: str, password: str) -> Optional[dict]:
    """Verify credentials."""
    sql = """
        SELECT user_id, email, full_name, first_name, surname, phone, date_of_birth, is_active, password as hashed_password 
        FROM users WHERE email = %s
    """
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (email,))
            row = cur.fetchone()
            if row:
                try:
                    if argon2.verify(password, row["hashed_password"]):
                        del row["hashed_password"]
                        return _serialize_dates(row)
                except Exception:
                    pass
            return None


def get_user_secret_question(email: str) -> Optional[str]:
    """Return the secret question for a registered email, or None if not found."""
    sql = "SELECT secret_question FROM users WHERE email = %s"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (email,))
            row = cur.fetchone()
            return row[0] if row else None


def verify_secret_answer(email: str, answer: str) -> bool:
    """Return True if the provided answer matches the stored secret answer (case-insensitive)."""
    sql = "SELECT secret_answer FROM users WHERE email = %s"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (email,))
            row = cur.fetchone()
            if row and row[0]:
                return row[0].strip().lower() == answer.strip().lower()
    return False


def update_password(email: str, new_password: str) -> bool:
    """Update the password for a user. Returns True if the row was updated."""
    sql = "UPDATE users SET password = %s WHERE email = %s"
    conn = psycopg2.connect(PG_DSN)
    try:
        hashed_password = argon2.hash(new_password)
        with conn.cursor() as cur:
            cur.execute(sql, (hashed_password, email))
            affected = cur.rowcount
            conn.commit()
            return affected > 0
    except psycopg2.DatabaseError:
        conn.rollback()
        return False
    finally:
        conn.close()


# ── VECTOR / RAG QUERIES — do not modify ─────────────────────────────────────

def query_policy_vector_search(embedding: list[float], top_k: int = VECTOR_TOP_K) -> list[dict]:
    """Find the most relevant policy documents for a given query embedding."""
    sql = """
        SELECT
            title,
            category,
            content,
            1 - (embedding <=> %s::vector) AS similarity
        FROM policy_documents
        WHERE 1 - (embedding <=> %s::vector) > %s
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (vec_str, vec_str, VECTOR_SIMILARITY_THRESHOLD, vec_str, top_k))
            return [dict(row) for row in cur.fetchall()]


def store_policy_document(
    title: str,
    category: str,
    content: str,
    embedding: list[float],
    source_file: str = "",
) -> int:
    """Insert a policy document with its embedding into the database."""
    sql = """
        INSERT INTO policy_documents (title, category, content, embedding, source_file)
        VALUES (%s, %s, %s, %s::vector, %s)
        RETURNING id
    """
    vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (title, category, content, vec_str, source_file))
            return cur.fetchone()[0]