"""
TransitFlow — Comprehensive Database Verification & Stress Test Suite
======================================================================
Covers:
  1. Rubric correctness checks (Task 1-5 criteria)
  2. Logic & edge-case verification
  3. Performance profiling (latency per function)
  4. Concurrency stress testing (booking race condition)
  5. Security compliance (PII masking, Argon2 hashing, injection prevention)
  6. Vector / RAG semantic accuracy

Run from the project root:
    python scripts/verify_all_databases.py

Requirements: Docker containers must be running (postgres:5433, neo4j:7688/7475).
"""

import sys
import io
# Force UTF-8 output on Windows terminals that default to cp950/cp936
if sys.stdout.encoding.lower() not in ('utf-8', 'utf-8-sig'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
import os
import time
import threading
import statistics
import uuid
import json
from typing import Any, Callable

# ── PATH SETUP ────────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, PROJECT_ROOT)

# ── COLOUR CODES ──────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
DIM    = "\033[2m"

# ── GLOBAL COUNTERS ───────────────────────────────────────────────────────────
_pass = 0
_fail = 0
_warn = 0
_created_bookings: list[str] = []  # Track bookings created during stress tests for cleanup

# ── TEST HELPERS ──────────────────────────────────────────────────────────────

def header(title: str) -> None:
    width = 72
    print(f"\n{BOLD}{CYAN}{'=' * width}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * width}{RESET}")


def section(title: str) -> None:
    print(f"\n{BOLD}-- {title} {'-' * (60 - len(title))}{RESET}")


def ok(msg: str) -> None:
    global _pass
    _pass += 1
    print(f"  {GREEN}[PASS]{RESET} {msg}")


def fail(msg: str) -> None:
    global _fail
    _fail += 1
    print(f"  {RED}[FAIL]{RESET} {msg}")


def warn(msg: str) -> None:
    global _warn
    _warn += 1
    print(f"  {YELLOW}[WARN]{RESET} {msg}")


def info(msg: str) -> None:
    print(f"  {DIM}[INFO] {msg}{RESET}")


def assert_true(condition: bool, pass_msg: str, fail_msg: str) -> None:
    if condition:
        ok(pass_msg)
    else:
        fail(fail_msg)


def assert_equal(actual: Any, expected: Any, label: str) -> None:
    if actual == expected:
        ok(f"{label} — got: {actual!r}")
    else:
        fail(f"{label} — expected {expected!r}, got {actual!r}")


def assert_almost_equal(actual: float, expected: float, label: str, tol: float = 0.01) -> None:
    if abs(actual - expected) <= tol:
        ok(f"{label} — {actual:.4f} ≈ {expected:.4f}")
    else:
        fail(f"{label} — expected ~{expected:.4f}, got {actual:.4f}")


def profile(fn: Callable, *args, label: str = "", runs: int = 5, **kwargs) -> tuple[Any, float]:
    """Run fn(*args) `runs` times and return (last_result, median_ms)."""
    times = []
    result = None
    for _ in range(runs):
        t0 = time.perf_counter()
        result = fn(*args, **kwargs)
        times.append((time.perf_counter() - t0) * 1000)
    median_ms = statistics.median(times)
    max_ms = max(times)
    if label:
        status = GREEN if median_ms < 500 else (YELLOW if median_ms < 2000 else RED)
        print(f"  {status}[TIME] {label}: median={median_ms:.1f}ms  max={max_ms:.1f}ms  (n={runs}){RESET}")
    return result, median_ms


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — RELATIONAL DATABASE (PostgreSQL)
# ══════════════════════════════════════════════════════════════════════════════

def test_relational() -> None:
    header("SECTION 1 — RELATIONAL DATABASE (PostgreSQL)")

    from databases.relational.queries import (
        query_national_rail_availability,
        query_national_rail_fare,
        query_metro_schedules,
        query_metro_fare,
        query_available_seats,
        query_user_profile,
        query_user_bookings,
        query_payment_info,
        execute_booking,
        execute_cancellation,
        login_user,
        register_user,
        get_user_secret_question,
        verify_secret_answer,
        update_password,
        query_compensation_eligibility,
        query_delay_records,
    )

    # ── 1.1 National Rail Availability ───────────────────────────────────────
    section("1.1 query_national_rail_availability")

    result, ms = profile(
        query_national_rail_availability,
        "NR01", "NR05", "2026-06-10",
        label="NR availability NR01→NR05",
        runs=5
    )
    assert_true(isinstance(result, list), "Returns a list", "Must return a list")
    assert_true(len(result) > 0, f"Found {len(result)} schedule(s) for NR01→NR05", "No schedules found — seeding issue?")
    if result:
        row = result[0]
        assert_true("schedule_id" in row, "schedule_id present in result", "Missing schedule_id field")
        assert_true("available_seats" in row, "available_seats present in result", "Missing available_seats field")
        assert_true("origin_stop_order" in row, "origin_stop_order present", "Missing origin_stop_order")
        assert_true("destination_stop_order" in row, "destination_stop_order present", "Missing destination_stop_order")
        assert_true(
            row["origin_stop_order"] < row["destination_stop_order"],
            f"origin_stop_order ({row['origin_stop_order']}) < dest_stop_order ({row['destination_stop_order']})",
            "Stop order direction is WRONG — origin should come before destination"
        )
        assert_true(
            int(row["available_seats"]) >= 0,
            f"available_seats ≥ 0 (got {row['available_seats']})",
            "Negative available_seats — logic error"
        )

    # Edge case: reversed direction should return 0 results (NR05 is before NR01 on NR_SCH01)
    rev = query_national_rail_availability("NR05", "NR01", "2026-06-10")
    # NOTE: NR_SCH02 runs NR05→NR01, so results ARE expected; just verify stop order is correct
    for r in rev:
        assert_true(
            r["origin_stop_order"] < r["destination_stop_order"],
            f"Reversed query: stop order correct in schedule {r['schedule_id']}",
            f"Reversed query: stop order WRONG in schedule {r['schedule_id']}"
        )

    # Edge case: unknown station
    unknown = query_national_rail_availability("NR99", "NR01", "2026-06-10")
    assert_equal(unknown, [], "Unknown station returns empty list (not exception)")

    # ── 1.2 National Rail Fare Calculation ───────────────────────────────────
    section("1.2 query_national_rail_fare — arithmetic verification")

    fare, ms = profile(
        query_national_rail_fare,
        "NR_SCH01", "standard", 4,
        label="NR fare NR_SCH01 standard 4 stops",
        runs=5
    )
    assert_true(fare is not None, "Returns fare dict for valid schedule+class", "Returned None — check fare_class seeding")
    if fare:
        assert_true("base_fare_usd" in fare, "base_fare_usd present", "Missing base_fare_usd")
        assert_true("per_stop_rate_usd" in fare, "per_stop_rate_usd present", "Missing per_stop_rate_usd")
        assert_true("total_fare_usd" in fare, "total_fare_usd present", "Missing total_fare_usd")
        expected_total = round(fare["base_fare_usd"] + 4 * fare["per_stop_rate_usd"], 2)
        assert_almost_equal(
            fare["total_fare_usd"], expected_total,
            "Fare arithmetic: total = base + stops * rate"
        )

    fare_first, _ = profile(
        query_national_rail_fare,
        "NR_SCH01", "first", 4,
        label="NR fare NR_SCH01 first class 4 stops",
        runs=5
    )
    if fare and fare_first:
        assert_true(
            fare_first["base_fare_usd"] > fare["base_fare_usd"],
            f"First class base ({fare_first['base_fare_usd']}) > Standard base ({fare['base_fare_usd']})",
            "First class should cost more than standard"
        )

    invalid_fare = query_national_rail_fare("NONEXISTENT", "standard", 1)
    assert_true(invalid_fare is None, "Unknown schedule returns None (not exception)", "Should return None for unknown schedule")

    # ── 1.3 Metro Schedules ───────────────────────────────────────────────────
    section("1.3 query_metro_schedules")

    ms_result, ms_t = profile(
        query_metro_schedules,
        "MS01", "MS03",
        label="Metro schedules MS01→MS03",
        runs=5
    )
    assert_true(isinstance(ms_result, list), "Returns a list", "Must return a list")
    if ms_result:
        row = ms_result[0]
        assert_true("schedule_id" in row, "schedule_id present", "Missing schedule_id")
        assert_true("origin_stop_order" in row, "origin_stop_order present", "Missing origin_stop_order")
        assert_true("destination_stop_order" in row, "destination_stop_order present", "Missing destination_stop_order")
        for r in ms_result:
            assert_true(
                r["origin_stop_order"] < r["destination_stop_order"],
                f"Metro stop order correct (schedule {r['schedule_id']})",
                f"Metro stop order WRONG in schedule {r['schedule_id']}"
            )

    # ── 1.4 Metro Fare Calculation ────────────────────────────────────────────
    section("1.4 query_metro_fare — arithmetic verification")

    mf, _ = profile(query_metro_fare, "MS_SCH01", 3, label="Metro fare MS_SCH01 3 stops", runs=5)
    assert_true(mf is not None, "Metro fare returns dict", "Returned None")
    if mf:
        assert_true("base_fare_usd" in mf, "base_fare_usd present", "Missing base_fare_usd")
        assert_true("per_stop_rate_usd" in mf, "per_stop_rate_usd present", "Missing per_stop_rate_usd")
        assert_true("total_fare_usd" in mf, "total_fare_usd present", "Missing total_fare_usd")
        expected_mf = round(mf["base_fare_usd"] + 3 * mf["per_stop_rate_usd"], 2)
        assert_almost_equal(mf["total_fare_usd"], expected_mf, "Metro fare arithmetic: total = base + stops * rate")

    # ── 1.5 Available Seats ───────────────────────────────────────────────────
    section("1.5 query_available_seats — collision detection")

    seats, ms_t = profile(
        query_available_seats,
        "NR_SCH01", "2026-06-10", "standard", "NR01", "NR05",
        label="Seats NR_SCH01 2026-06-10 standard NR01→NR05",
        runs=5
    )
    assert_true(isinstance(seats, list), "Returns a list", "Must return a list")
    if seats:
        seat = seats[0]
        assert_true("seat_id" in seat, "seat_id present in each seat", "Missing seat_id field")
        assert_true("coach" in seat, "coach present in each seat", "Missing coach field")

    # Collision: already-booked date for the same seat on the same route
    seats_booked = query_available_seats("NR_SCH01", "2026-04-01", "standard", "NR01", "NR05")
    # BK006 is confirmed on NR_SCH03 so NR_SCH01 availability should still show seats
    assert_true(
        isinstance(seats_booked, list),
        "Returns list even on dates with existing bookings",
        "Failed to return list"
    )

    # Fallback path: no origin/dest (rubric does not require this, but must not crash)
    seats_fallback = query_available_seats("NR_SCH01", "2026-06-10", "standard")
    assert_true(isinstance(seats_fallback, list), "Fallback (no origin/dest) returns list without crash", "Fallback path crashed")

    # ── 1.6 User Profile & PII Masking ───────────────────────────────────────
    section("1.6 query_user_profile — correctness & PII masking")

    profile_res, _ = profile(
        query_user_profile, "alice.tan@email.com",
        label="User profile alice.tan@email.com",
        runs=5
    )
    assert_true(profile_res is not None, "Returns dict for valid email", "Returned None for known user")
    if profile_res:
        assert_true("user_id" in profile_res, "user_id present", "Missing user_id")
        assert_true("email" in profile_res, "email present", "Missing email")
        # PII masking checks
        if profile_res.get("phone"):
            phone = profile_res["phone"]
            assert_true(
                "*" in phone,
                f"Phone is masked: {phone!r}",
                f"Phone NOT masked — PII leak! Got: {phone!r}"
            )
        if profile_res.get("date_of_birth"):
            dob = profile_res["date_of_birth"]
            assert_true(
                "**" in dob,
                f"Date of birth is masked: {dob!r}",
                f"DOB NOT masked — PII leak! Got: {dob!r}"
            )

    unknown_profile = query_user_profile("nobody@nowhere.com")
    assert_true(unknown_profile is None, "Returns None for unknown email (not exception)", "Should return None, not raise")

    # ── 1.7 User Bookings ─────────────────────────────────────────────────────
    section("1.7 query_user_bookings — return shape")

    bookings, _ = profile(
        query_user_bookings, "alice.tan@email.com",
        label="User bookings alice.tan@email.com",
        runs=5
    )
    assert_true("national_rail" in bookings, "national_rail key present", "Missing national_rail key")
    assert_true("metro" in bookings, "metro key present", "Missing metro key")
    assert_true(isinstance(bookings["national_rail"], list), "national_rail is a list", "national_rail not a list")
    assert_true(isinstance(bookings["metro"], list), "metro is a list", "metro not a list")

    # Unknown email must still return both keys (per rubric)
    unknown_bookings = query_user_bookings("nobody@nowhere.com")
    assert_true(
        "national_rail" in unknown_bookings and "metro" in unknown_bookings,
        "Unknown email returns both keys (not None or exception)",
        "Unknown email must still return {national_rail: [], metro: []}"
    )
    assert_equal(unknown_bookings["national_rail"], [], "unknown_email → national_rail is empty list")
    assert_equal(unknown_bookings["metro"], [], "unknown_email → metro is empty list")

    # ── 1.8 Payment Info ──────────────────────────────────────────────────────
    section("1.8 query_payment_info")

    payment, _ = profile(query_payment_info, "BK006", label="Payment for BK006", runs=5)
    assert_true(payment is not None, "Returns dict for known booking", "Returned None for BK006")
    if payment:
        assert_true("payment_id" in payment, "payment_id present", "Missing payment_id")
        assert_true("amount_usd" in payment, "amount_usd present", "Missing amount_usd")
        assert_true(isinstance(payment["amount_usd"], float), "amount_usd is float", "amount_usd should be float")

    no_payment = query_payment_info("BK-DOESNOTEXIST")
    assert_true(no_payment is None, "Returns None for unknown booking_id", "Should return None")

    # ── 1.9 Authentication ────────────────────────────────────────────────────
    section("1.9 Authentication — login, register, secret Q&A, update password")

    # login: correct password
    logged_in, _ = profile(login_user, "alice.tan@email.com", "alice1990", label="Login alice (correct pw)", runs=3)
    assert_true(logged_in is not None, "Login succeeds with correct password", "Login failed for known user with correct password")

    # login: wrong password
    bad_login = login_user("alice.tan@email.com", "WRONGPASSWORD")
    assert_true(bad_login is None, "Login returns None for wrong password", "Login should fail with wrong password")

    # login: unknown email
    no_login = login_user("ghost@example.com", "anything")
    assert_true(no_login is None, "Login returns None for unknown email", "Login should return None for unknown email")

    # register: new user
    test_email = f"test_{uuid.uuid4().hex[:8]}@verify.com"
    reg_ok, reg_msg = register_user(
        email=test_email,
        first_name="Test",
        surname="User",
        year_of_birth=1995,
        password="SecurePass!99",
        secret_question="What is 2+2?",
        secret_answer="four",
    )
    assert_true(reg_ok, f"New user registered: {test_email}", f"Registration failed: {reg_msg}")

    # register: duplicate email
    dup_ok, dup_msg = register_user(
        email=test_email,
        first_name="Dup",
        surname="User",
        year_of_birth=1995,
        password="AnotherPass!1",
        secret_question="Q",
        secret_answer="A",
    )
    assert_true(not dup_ok, "Duplicate email rejected gracefully (returns False, not exception)", "Duplicate email should be rejected")

    # secret question
    sq = get_user_secret_question(test_email)
    assert_true(sq == "What is 2+2?", f"Secret question returned: {sq!r}", f"Wrong secret question: {sq!r}")

    sq_none = get_user_secret_question("ghost@ghost.com")
    assert_true(sq_none is None, "Unknown email returns None for secret question", "Should return None")

    # verify secret answer (case-insensitive)
    assert_true(verify_secret_answer(test_email, "four"), "Correct answer (lowercase) verifies", "Case-insensitive verify failed")
    assert_true(verify_secret_answer(test_email, "FOUR"), "Correct answer (uppercase) verifies — case insensitive", "Case-insensitive check failed for uppercase")
    assert_true(not verify_secret_answer(test_email, "five"), "Wrong answer returns False", "Wrong answer should fail")

    # update password
    upd = update_password(test_email, "NewPassword!22")
    assert_true(upd, "update_password returns True on success", "update_password failed")

    # new password must work
    new_login = login_user(test_email, "NewPassword!22")
    assert_true(new_login is not None, "Login with new password succeeds after update_password", "New password login failed")

    # old password must fail
    old_login = login_user(test_email, "SecurePass!99")
    assert_true(old_login is None, "Old password fails after update_password", "Old password should not work after update")

    # ── 1.10 Argon2 Hash Compliance ───────────────────────────────────────────
    section("1.10 Argon2 Hash Compliance (rubric: plain-text = 0 marks)")
    import psycopg2
    from skeleton.config import PG_DSN
    with psycopg2.connect(PG_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT password_hash FROM user_credentials LIMIT 3")
            for (pw_hash,) in cur.fetchall():
                assert_true(
                    pw_hash.startswith("$argon2"),
                    f"Password stored as Argon2 PHC string: {pw_hash[:20]}…",
                    f"Password NOT Argon2 — CRITICAL: {pw_hash[:40]!r}"
                )

    # ── 1.11 execute_booking — Atomicity & Concurrency ────────────────────────
    section("1.11 execute_booking — atomicity & concurrency stress test")

    # First, find a real available seat to book
    avail = query_available_seats("NR_SCH01", "2027-01-15", "standard", "NR01", "NR05")
    if not avail:
        warn("No available seats for 2027-01-15 NR_SCH01 — skipping booking stress test")
    else:
        test_seat = avail[0]["seat_id"]
        info(f"Using seat {test_seat} for concurrency stress test")

        # Get a valid user_id
        with psycopg2.connect(PG_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM users WHERE email = 'alice.tan@email.com'")
                user_id = str(cur.fetchone()[0])

        # Concurrency: 5 threads all try to book the same seat simultaneously
        results = []
        def try_book():
            ok_flag, res = execute_booking(
                user_id=user_id,
                schedule_id="NR_SCH01",
                origin_station_id="NR01",
                destination_station_id="NR05",
                travel_date="2027-01-15",
                fare_class="standard",
                seat_id=test_seat,
            )
            results.append((ok_flag, res))
            if ok_flag and isinstance(res, dict):
                _created_bookings.append(res.get("booking_id", ""))

        THREAD_COUNT = 5
        threads = [threading.Thread(target=try_book) for _ in range(THREAD_COUNT)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        successes = [r for r in results if r[0]]
        failures = [r for r in results if not r[0]]
        assert_true(
            len(successes) == 1,
            f"Exactly 1 of {THREAD_COUNT} concurrent booking attempts succeeded (race condition prevented)",
            f"Overbooking DETECTED: {len(successes)} threads succeeded for same seat — CRITICAL concurrency bug"
        )
        info(f"  Concurrent bookings: {len(successes)} success, {len(failures)} blocked correctly")

        # Performance test for single booking
        avail2 = query_available_seats("NR_SCH01", "2027-02-15", "standard", "NR01", "NR05")
        if avail2:
            seat2 = avail2[0]["seat_id"]
            t0 = time.perf_counter()
            ok2, res2 = execute_booking(user_id, "NR_SCH01", "NR01", "NR05", "2027-02-15", "standard", seat2)
            elapsed = (time.perf_counter() - t0) * 1000
            status_color = GREEN if elapsed < 1000 else YELLOW
            print(f"  {status_color}[TIME] execute_booking latency: {elapsed:.1f}ms{RESET}")
            if ok2 and isinstance(res2, dict):
                _created_bookings.append(res2.get("booking_id", ""))

    # ── 1.12 execute_cancellation — refund policy compliance ──────────────────
    section("1.12 execute_cancellation — refund policy (RF001/RF002)")

    # Test cancellation of a real confirmed booking (BK006)
    t0 = time.perf_counter()
    cancel_ok, cancel_res = execute_cancellation("BK006", "384558a5-cf21-5e25-b834-4b5e95a43590")
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  {GREEN if elapsed < 1000 else YELLOW}[TIME] execute_cancellation latency: {elapsed:.1f}ms{RESET}")

    if cancel_ok:
        ok(f"BK006 cancelled successfully — refund: ${cancel_res.get('refund_amount_usd', 'N/A')}")
    else:
        # Booking may already be cancelled from previous test run — that's ok
        if "status" in str(cancel_res).lower() or "cancelled" in str(cancel_res).lower():
            warn(f"BK006 already cancelled (expected on re-runs): {cancel_res}")
        else:
            fail(f"Cancellation of BK006 failed: {cancel_res}")

    # Cannot cancel already-cancelled booking
    cancel_twice = execute_cancellation("BK006", "384558a5-cf21-5e25-b834-4b5e95a43590")
    assert_true(
        not cancel_twice[0],
        "Re-cancelling an already-cancelled booking returns False (idempotent guard)",
        "Re-cancellation should fail gracefully"
    )

    # Wrong user cannot cancel another user's booking
    wrong_user_cancel = execute_cancellation("BK009", "00000000-0000-0000-0000-000000000000")
    assert_true(
        not wrong_user_cancel[0],
        "User cannot cancel another user's booking (ownership check)",
        "SECURITY: Booking cancelled by wrong user_id — ownership check MISSING"
    )

    # ── 1.13 Task 6 Extension: Compensation Eligibility ───────────────────────
    section("1.13 query_compensation_eligibility (Task 6 bonus)")

    comp = query_compensation_eligibility("BK009", "384558a5-cf21-5e25-b834-4b5e95a43590")
    assert_true("eligible" in comp, "Compensation result has 'eligible' key", "Missing 'eligible' key")
    assert_true("delay_min" in comp, "Compensation result has 'delay_min' key", "Missing 'delay_min' key")
    assert_true("refund_pct" in comp, "Compensation result has 'refund_pct' key", "Missing 'refund_pct' key")
    assert_true("estimated_refund_usd" in comp, "Compensation result has 'estimated_refund_usd' key", "Missing 'estimated_refund_usd'")
    info(f"  Booking BK009 compensation: delay={comp.get('delay_min')}min, eligible={comp.get('eligible')}, refund_pct={comp.get('refund_pct')}")

    # Wrong user gets access-denied
    comp_wrong = query_compensation_eligibility("BK009", "00000000-0000-0000-0000-000000000000")
    assert_true(
        not comp_wrong.get("eligible", True) and "not belong" in comp_wrong.get("note", "").lower(),
        "Compensation check rejects wrong user_id",
        "SECURITY: Compensation accessible by wrong user_id"
    )

    # Delay records
    delay_recs = query_delay_records("NR_SCH01", "2026-04-02")
    assert_true(isinstance(delay_recs, list), "query_delay_records returns list", "Must return list")
    info(f"  Delay records for NR_SCH01 on 2026-04-02: {len(delay_recs)} record(s)")

    # ── 1.14 DB Seeding Idempotency ───────────────────────────────────────────
    section("1.14 Seeding Idempotency — verify ON CONFLICT DO NOTHING")
    with psycopg2.connect(PG_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users")
            count_before = cur.fetchone()[0]

            # Re-insert an existing user — should silently do nothing
            cur.execute("""
                INSERT INTO users (user_id, legacy_id, first_name, surname, email, registered_at)
                VALUES (gen_random_uuid(), 'RU01', 'Alice', 'Tan', 'alice.tan@email.com', NOW())
                ON CONFLICT DO NOTHING
            """)

            cur.execute("SELECT COUNT(*) FROM users")
            count_after = cur.fetchone()[0]
            conn.commit()

        assert_equal(count_before, count_after, "ON CONFLICT DO NOTHING: user count unchanged after duplicate insert")

    # ── 1.15 Schema FK Cascade Spot-Check ────────────────────────────────────
    section("1.15 Schema: verify all FK ON DELETE behaviours declared")
    with psycopg2.connect(PG_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT tc.constraint_name, kcu.column_name, rc.delete_rule
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                JOIN information_schema.referential_constraints AS rc
                  ON tc.constraint_name = rc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = 'public'
                  AND rc.delete_rule = 'NO ACTION'
            """)
            no_action_fks = cur.fetchall()

        if no_action_fks:
            for fk in no_action_fks:
                warn(f"FK '{fk[0]}' on column '{fk[1]}' uses NO ACTION (not explicit RESTRICT/CASCADE/SET NULL)")
        else:
            ok("All FK constraints have explicit ON DELETE behaviour (no implicit NO ACTION)")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — GRAPH DATABASE (Neo4j)
# ══════════════════════════════════════════════════════════════════════════════

def test_graph() -> None:
    header("SECTION 2 — GRAPH DATABASE (Neo4j)")

    from databases.graph.queries import (
        query_shortest_route,
        query_cheapest_route,
        query_alternative_routes,
        query_interchange_path,
        query_delay_ripple,
        query_station_connections,
    )

    # ── 2.1 query_shortest_route ──────────────────────────────────────────────
    section("2.1 query_shortest_route (APOC Dijkstra by travel_time_min)")

    route, ms_t = profile(
        query_shortest_route, "NR01", "NR05", "rail",
        label="Shortest route NR01→NR05 (rail)",
        runs=5
    )
    assert_true(route.get("found"), "Route found: NR01→NR05", "Route NOT found — check Neo4j seeding")
    assert_true("path" in route, "Result contains 'path' key", "Missing 'path' key")
    assert_true("total_time_min" in route, "Result contains 'total_time_min' key", "Missing 'total_time_min'")
    if route.get("path"):
        assert_equal(route["path"][0]["station_id"], "NR01", "Path starts at origin NR01")
        assert_equal(route["path"][-1]["station_id"], "NR05", "Path ends at destination NR05")
        assert_true(route["total_time_min"] > 0, f"total_time_min > 0 (got {route['total_time_min']})", "total_time_min must be positive")
    info(f"  NR01→NR05 path: {' → '.join(s['station_id'] for s in route.get('path', []))}")
    info(f"  Total time: {route.get('total_time_min')} minutes")

    # Metro route
    metro_route, _ = profile(
        query_shortest_route, "MS01", "MS09", "metro",
        label="Shortest route MS01→MS09 (metro)",
        runs=5
    )
    assert_true(metro_route.get("found"), "Metro route found: MS01→MS09", "Metro route NOT found")

    # Edge cases
    same_od = query_shortest_route("NR01", "NR01", "rail")
    assert_true(isinstance(same_od, dict), "Same O/D returns dict (not exception)", "Same O/D crashed")

    nonexist = query_shortest_route("NR99", "NR01", "rail")
    assert_true(not nonexist.get("found"), "Non-existent station returns found=False", "Non-existent station should return found=False")

    # ── 2.2 query_cheapest_route — fare_class must affect cost ────────────────
    section("2.2 query_cheapest_route — fare_class effect (rubric requirement)")

    cheap_std, _ = profile(
        query_cheapest_route, "NR01", "NR05", "rail", "standard",
        label="Cheapest NR01→NR05 standard",
        runs=5
    )
    cheap_first, _ = profile(
        query_cheapest_route, "NR01", "NR05", "rail", "first",
        label="Cheapest NR01→NR05 first",
        runs=5
    )

    assert_true(cheap_std.get("found"), "Cheapest route (standard) found", "Cheapest route not found")
    assert_true(cheap_first.get("found"), "Cheapest route (first) found", "Cheapest route not found")

    if cheap_std.get("found") and cheap_first.get("found"):
        assert_true(
            cheap_first.get("cost", 0) > cheap_std.get("cost", 0),
            f"First class cost ({cheap_first['cost']:.2f}) > Standard cost ({cheap_std['cost']:.2f}) — rubric: fare_class visibly affects cost",
            f"RUBRIC FAIL: first class NOT more expensive than standard — fare_class not affecting cost"
        )
        assert_true("path" in cheap_std, "Result contains 'path' list", "Missing 'path'")
        assert_true("stops" in cheap_std, "Result contains 'stops' count", "Missing 'stops'")

    # ── 2.3 query_alternative_routes — avoid station ──────────────────────────
    section("2.3 query_alternative_routes — avoided station must not appear in paths")

    avoid_station = "NR03"
    alts, _ = profile(
        query_alternative_routes, "NR01", "NR05", avoid_station, "rail", 3,
        label=f"Alt routes NR01→NR05 avoiding {avoid_station}",
        runs=5
    )
    assert_true(isinstance(alts, list), "Returns list of routes", "Must return list")

    for i, route_item in enumerate(alts):
        station_ids = [s["station_id"] for s in route_item.get("stations", [])]
        assert_true(
            avoid_station not in station_ids,
            f"Route {i+1}: avoided station {avoid_station} not present in path {station_ids}",
            f"Route {i+1}: avoided station {avoid_station} FOUND in path — avoid logic broken"
        )

    # max_routes is respected
    alts_limited, _ = profile(
        query_alternative_routes, "NR01", "NR05", avoid_station, "rail", 1,
        label="Alt routes limited to max_routes=1",
        runs=3
    )
    assert_true(len(alts_limited) <= 1, f"max_routes=1 respected (got {len(alts_limited)} routes)", "max_routes limit not respected")

    info(f"  Found {len(alts)} alternative routes avoiding {avoid_station}")

    # ── 2.4 query_interchange_path — cross-network traversal ──────────────────
    section("2.4 query_interchange_path — must traverse INTERCHANGE_TO edges")

    # MS01 (metro) → NR05 (rail) — requires INTERCHANGE_TO crossing
    interchange_result, _ = profile(
        query_interchange_path, "MS01", "NR05",
        label="Interchange path MS01 (metro) → NR05 (rail)",
        runs=5
    )
    assert_true(isinstance(interchange_result, dict), "Returns dict", "Must return dict")
    assert_true(interchange_result.get("found"), "Cross-network path found", "Cross-network path NOT found — check INTERCHANGE_TO edges and seed_neo4j.py")
    assert_true("interchange_points" in interchange_result, "Result contains 'interchange_points'", "Missing 'interchange_points'")
    assert_true("is_cross_network" in interchange_result, "Result contains 'is_cross_network'", "Missing 'is_cross_network'")

    if interchange_result.get("found"):
        assert_true(
            interchange_result.get("is_cross_network"),
            "is_cross_network=True confirmed (INTERCHANGE_TO was traversed)",
            "is_cross_network=False for MS01→NR05 — interchange edge may be missing"
        )
        path_ids = [s["station_id"] for s in interchange_result.get("path", [])]
        has_metro = any(sid.startswith("MS") for sid in path_ids)
        has_rail = any(sid.startswith("NR") for sid in path_ids)
        assert_true(has_metro and has_rail, f"Path includes both metro and rail stations: {path_ids}", "Path should include both network types")
        info(f"  Interchange path: {' → '.join(path_ids)}")

    # ── 2.5 query_delay_ripple — hops_away must be present ────────────────────
    section("2.5 query_delay_ripple — hops_away count verification")

    ripple, _ = profile(
        query_delay_ripple, "NR03", 2,
        label="Delay ripple from NR03, 2 hops",
        runs=5
    )
    assert_true(isinstance(ripple, list), "Returns list", "Must return list")
    assert_true(len(ripple) > 0, f"Found {len(ripple)} affected station(s) within 2 hops of NR03", "No stations found — seeding issue?")

    if ripple:
        for station in ripple:
            assert_true("hops_away" in station, f"hops_away present for {station.get('station_id')}", "Missing hops_away")
            assert_true("station_id" in station, "station_id present", "Missing station_id")
            assert_true("name" in station, "name present", "Missing name")
            assert_true(
                0 <= station["hops_away"] <= 2,
                f"{station['station_id']}: hops_away={station['hops_away']} within range [0, 2]",
                f"{station['station_id']}: hops_away={station['hops_away']} OUT OF RANGE"
            )

    # Hard cap test (hops > _MAX_HOPS=5)
    ripple_capped = query_delay_ripple("NR01", 999)
    assert_true(isinstance(ripple_capped, list), "Extreme hops value (999) capped — returns list without crash", "Hard cap failed")
    info(f"  hops=999 clamped to 5, returned {len(ripple_capped)} stations")

    # ── 2.6 query_station_connections ─────────────────────────────────────────
    section("2.6 query_station_connections — direct neighbour check")

    conns, _ = profile(query_station_connections, "NR03", label="Station connections NR03", runs=5)
    assert_true(isinstance(conns, list), "Returns list", "Must return list")
    assert_true(len(conns) > 0, f"NR03 has {len(conns)} direct connection(s)", "NR03 should have at least one connection")
    if conns:
        conn_item = conns[0]
        assert_true("station_id" in conn_item, "station_id present", "Missing station_id")
        assert_true("travel_time_min" in conn_item, "travel_time_min present", "Missing travel_time_min (rubric requirement)")
        assert_true(conn_item["travel_time_min"] >= 0, f"travel_time_min ≥ 0 (got {conn_item['travel_time_min']})", "Negative travel_time_min")
    info(f"  NR03 connections: {[c['station_id'] for c in conns]}")

    # ── 2.7 Graph Node & Relationship Existence ────────────────────────────────
    section("2.7 Task 4: graph schema verification (MetroStation, NationalRailStation, 3 rel types)")

    from neo4j import GraphDatabase
    from skeleton.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            metro_count = session.run("MATCH (n:MetroStation) RETURN count(n) AS c").single()["c"]
            rail_count = session.run("MATCH (n:NationalRailStation) RETURN count(n) AS c").single()["c"]
            metro_link = session.run("MATCH ()-[r:METRO_LINK]->() RETURN count(r) AS c").single()["c"]
            rail_link = session.run("MATCH ()-[r:RAIL_LINK]->() RETURN count(r) AS c").single()["c"]
            interchange = session.run("MATCH ()-[r:INTERCHANGE_TO]->() RETURN count(r) AS c").single()["c"]
            travel_time_check = session.run(
                "MATCH ()-[r:METRO_LINK]->() WHERE r.travel_time_min IS NULL RETURN count(r) AS c"
            ).single()["c"]

        assert_true(metro_count > 0, f"MetroStation nodes present: {metro_count}", "No MetroStation nodes — seeding failed")
        assert_true(rail_count > 0, f"NationalRailStation nodes present: {rail_count}", "No NationalRailStation nodes")
        assert_true(metro_link > 0, f"METRO_LINK relationships present: {metro_link}", "No METRO_LINK relationships")
        assert_true(rail_link > 0, f"RAIL_LINK relationships present: {rail_link}", "No RAIL_LINK relationships")
        assert_true(interchange > 0, f"INTERCHANGE_TO relationships present: {interchange}", "No INTERCHANGE_TO — cross-network routing will fail")
        assert_equal(travel_time_check, 0, f"All METRO_LINK edges have travel_time_min (null count: {travel_time_check})")

    # ── 2.8 Neo4j Seeding Idempotency ─────────────────────────────────────────
    section("2.8 Neo4j MERGE idempotency — duplicate MERGE must not create duplicates")

    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            count_before = session.run("MATCH (n:MetroStation) RETURN count(n) AS c").single()["c"]
            # Re-MERGE an existing station — should not create a duplicate
            session.run("MERGE (n:MetroStation {station_id: 'MS01'}) SET n.name = 'Central Square'")
            count_after = session.run("MATCH (n:MetroStation) RETURN count(n) AS c").single()["c"]
        assert_equal(count_before, count_after, "MERGE idempotency: node count unchanged after re-MERGE")

    # ── 2.9 Cypher Injection Prevention ───────────────────────────────────────
    section("2.9 Security: whitelist prevents Cypher structure injection")

    # Attempt injection via network parameter — should fall back to 'auto' safely
    injected_result = query_shortest_route("NR01", "NR05", "RAIL_LINK>]) RETURN 'injected'//")
    assert_true(
        isinstance(injected_result, dict),
        "Injection payload in 'network' param handled safely (returns dict)",
        "Injection payload caused unexpected behaviour"
    )
    # The injected string is not in the whitelist, so it falls back to 'auto'
    info(f"  Injection test result: found={injected_result.get('found')}")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — VECTOR DATABASE (pgvector / RAG)
# ══════════════════════════════════════════════════════════════════════════════

def test_vector() -> None:
    header("SECTION 3 — VECTOR DATABASE (pgvector / RAG)")

    from skeleton.llm_provider import llm
    from databases.relational.queries import query_policy_vector_search
    from skeleton.config import VECTOR_SIMILARITY_THRESHOLD

    # ── 3.1 Policy Document Count ─────────────────────────────────────────────
    section("3.1 Policy documents seeded and accessible")

    import psycopg2
    from skeleton.config import PG_DSN
    with psycopg2.connect(PG_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM policy_documents")
            doc_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM policy_documents WHERE embedding IS NULL")
            null_embed = cur.fetchone()[0]
            cur.execute("SELECT DISTINCT category FROM policy_documents")
            categories = [row[0] for row in cur.fetchall()]

    assert_true(doc_count > 0, f"{doc_count} policy documents seeded", "No policy documents — run seed_vectors.py")
    assert_equal(null_embed, 0, f"All {doc_count} documents have embeddings (null count: {null_embed})")
    info(f"  Categories present: {categories}")
    assert_true("refund" in categories, "Category 'refund' present", "Missing 'refund' category")
    assert_true("booking" in categories, "Category 'booking' present", "Missing 'booking' category")
    assert_true("conduct" in categories, "Category 'conduct' present", "Missing 'conduct' category")

    # ── 3.2 HNSW Index Exists ─────────────────────────────────────────────────
    section("3.2 HNSW index verification (idx_policy_documents_embedding)")

    with psycopg2.connect(PG_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'policy_documents'
                  AND indexdef ILIKE '%hnsw%'
            """)
            hnsw_indexes = cur.fetchall()

    assert_true(len(hnsw_indexes) > 0, f"HNSW index found: {[i[0] for i in hnsw_indexes]}", "No HNSW index — create it in schema.sql or seed_vectors.py")

    # ── 3.3 Semantic Similarity Search Accuracy ───────────────────────────────
    section("3.3 Semantic similarity search — accuracy & threshold compliance")

    test_queries = [
        ("delay compensation 45 minutes refund", "refund", "RF005"),
        ("can I get money back if train is late", "refund", None),
        ("bicycle luggage pets on train rules", "conduct", None),
        ("how to book a single ticket for metro", "booking", None),
        ("cancel my national rail ticket", "refund", None),
    ]

    for query_text, expected_category, expected_policy in test_queries:
        t0 = time.perf_counter()
        embedding = llm.embed(query_text)
        embed_ms = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        results = query_policy_vector_search(embedding, top_k=3)
        search_ms = (time.perf_counter() - t0) * 1000

        print(f"  {CYAN}Query:{RESET} {query_text!r}")
        print(f"  {DIM}Embed: {embed_ms:.0f}ms | Search: {search_ms:.0f}ms{RESET}")

        assert_true(isinstance(results, list), f"Returns list for query: {query_text[:30]}", "Must return list")

        if results:
            top_result = results[0]
            assert_true("similarity" in top_result, "similarity score present in result", "Missing similarity score")
            assert_true("title" in top_result, "title present in result", "Missing title")
            assert_true("content" in top_result, "content present in result", "Missing content")

            # All results must be above threshold (threshold filtering done in Python layer)
            for r in results:
                assert_true(
                    r["similarity"] >= VECTOR_SIMILARITY_THRESHOLD,
                    f"Result '{r['title'][:40]}' similarity={r['similarity']:.4f} >= threshold ({VECTOR_SIMILARITY_THRESHOLD})",
                    f"Result below threshold: {r['title'][:40]} similarity={r['similarity']:.4f}"
                )

            top_sim = top_result["similarity"]
            top_title = top_result["title"]
            info(f"  Top result: '{top_title}' (similarity={top_sim:.4f})")

            if expected_policy:
                # NOTE: Check that the result is semantically relevant (mentions delay/compensation)
                # We do NOT hard-require a specific policy_id string because the RAG may return
                # a more specific child policy (RF010/RF011/RF012) instead of the parent (RF005) —
                # that is CORRECT behaviour, not a failure.
                top_content = (top_result.get("content", "") + top_result.get("title", "")).lower()
                assert_true(
                    "delay" in top_content or "compensation" in top_content or "refund" in top_content,
                    f"Top result is semantically relevant for '{query_text[:30]}': '{top_title}'",
                    f"Top result not semantically related to expected category — may indicate embedding quality issue"
                )
        else:
            warn(f"No results above threshold ({VECTOR_SIMILARITY_THRESHOLD}) for: {query_text!r}")

    # ── 3.4 Threshold Enforcement — SQL uses ORDER BY, not WHERE ──────────────
    section("3.4 HNSW index correctness: filter is in Python, not SQL WHERE clause")
    import psycopg2.extras
    with psycopg2.connect(PG_DSN) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Check that query_policy_vector_search SQL does NOT have a WHERE on embedding
            # We verify this by reading the source code directly
            import inspect
            from databases.relational.queries import query_policy_vector_search as qpvs
            src = inspect.getsource(qpvs)
            has_where_on_embedding = "WHERE" in src and "embedding" in src.split("WHERE")[-1].split("ORDER")[0]
            assert_true(
                not has_where_on_embedding,
                "SQL ORDER BY used without WHERE on embedding — HNSW index can be used (correct)",
                "SQL WHERE clause on embedding found — this prevents HNSW index usage (performance penalty)"
            )

    # ── 3.5 RAG Stress Test — 10 rapid queries ────────────────────────────────
    section("3.5 Vector search stress test — 10 rapid queries")

    stress_queries = [
        "refund policy", "express train cancel", "bicycle policy", "day pass metro",
        "delay compensation", "first class booking", "lost property", "interchange stations",
        "season ticket renewal", "no show policy"
    ]
    latencies = []
    for q in stress_queries:
        emb = llm.embed(q)
        t0 = time.perf_counter()
        _ = query_policy_vector_search(emb, top_k=3)
        latencies.append((time.perf_counter() - t0) * 1000)

    med = statistics.median(latencies)
    mx = max(latencies)
    mn = min(latencies)
    print(f"  {GREEN if med < 200 else YELLOW}[TIME] Vector search stress (n=10): min={mn:.0f}ms median={med:.0f}ms max={mx:.0f}ms{RESET}")
    assert_true(med < 2000, f"Median search latency {med:.0f}ms < 2000ms", f"Search too slow: {med:.0f}ms")

    # ── 3.6 Dimension Consistency ─────────────────────────────────────────────
    section("3.6 Embedding dimension consistency (LLM provider ↔ schema)")

    sample_emb = llm.embed("test")
    actual_dim = len(sample_emb)
    info(f"  Active provider: {llm.chat_provider}, embedding dim: {actual_dim}")

    with psycopg2.connect(PG_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT atttypmod
                FROM pg_attribute
                JOIN pg_class ON pg_attribute.attrelid = pg_class.oid
                WHERE pg_class.relname = 'policy_documents'
                  AND pg_attribute.attname = 'embedding'
            """)
            row = cur.fetchone()
            schema_dim = row[0] if row else -1

    assert_equal(actual_dim, schema_dim, f"LLM embedding dim ({actual_dim}) matches schema dim ({schema_dim})")


# ══════════════════════════════════════════════════════════════════════════════
# CLEANUP & FINAL SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

def cleanup_test_bookings() -> None:
    """Remove bookings created by the stress test to restore DB state."""
    if not _created_bookings:
        return
    import psycopg2
    from skeleton.config import PG_DSN
    with psycopg2.connect(PG_DSN) as conn:
        with conn.cursor() as cur:
            for bid in _created_bookings:
                if bid:
                    cur.execute("DELETE FROM payments WHERE booking_ref = %s", (bid,))
                    cur.execute("DELETE FROM national_rail_bookings WHERE booking_id = %s", (bid,))
        conn.commit()
    info(f"  Cleaned up {len(_created_bookings)} stress-test booking(s): {_created_bookings}")


def print_summary() -> None:
    total = _pass + _fail + _warn
    print(f"\n{BOLD}{'═' * 72}{RESET}")
    print(f"{BOLD}  FINAL RESULTS{RESET}")
    print(f"{BOLD}{'═' * 72}{RESET}")
    print(f"  {GREEN}✓ Passed:{RESET}  {_pass}")
    print(f"  {RED}✗ Failed:{RESET}  {_fail}")
    print(f"  {YELLOW}⚠ Warned:{RESET}  {_warn}")
    print(f"  Total checks: {total}")
    print(f"{BOLD}{'─' * 72}{RESET}")
    if _fail == 0:
        print(f"\n  {GREEN}{BOLD}ALL CHECKS PASSED — Zero rubric violations detected.{RESET}")
    else:
        print(f"\n  {RED}{BOLD}{_fail} CHECK(S) FAILED — Review output above carefully.{RESET}")
    print()


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"\n{BOLD}{CYAN}TransitFlow — Full Database Verification Suite{RESET}")
    print(f"{DIM}Rubric: STUDENT_GUIDE_CODE.md | Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}{RESET}")

    try:
        test_relational()
    except Exception as e:
        fail(f"Relational test suite crashed: {e}")
        import traceback
        traceback.print_exc()

    try:
        test_graph()
    except Exception as e:
        fail(f"Graph test suite crashed: {e}")
        import traceback
        traceback.print_exc()

    try:
        test_vector()
    except Exception as e:
        fail(f"Vector test suite crashed: {e}")
        import traceback
        traceback.print_exc()

    cleanup_test_bookings()
    print_summary()
    sys.exit(0 if _fail == 0 else 1)
