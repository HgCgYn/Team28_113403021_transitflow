# TASK 6 EXTENSION: Test script for verifying compensation eligibility logic
import os
import sys
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from databases.relational.queries import query_compensation_eligibility, _connect

BOOKING_ID = "TEST-BK-VERIFY-01"
TRAVEL_DATE = "2024-10-15"
SCHEDULE_ID = "NR_SCH01"

if __name__ == '__main__':
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM national_rail_bookings LIMIT 1")
            user_id = cur.fetchone()[0]

            cur.execute(
                "SELECT station_id, stop_order FROM national_rail_schedule_stops WHERE schedule_id = %s ORDER BY stop_order",
                (SCHEDULE_ID,)
            )
            stops = cur.fetchall()
            origin_station_id = stops[0][0]
            destination_station_id = stops[-1][0]
            stops_travelled = stops[-1][1] - stops[0][1]

            cur.execute(
                "SELECT first_train_time FROM national_rail_schedules WHERE schedule_id = %s",
                (SCHEDULE_ID,)
            )
            departure_time = cur.fetchone()[0]

            cur.execute(
                "SELECT s.seat_id, s.coach FROM seats s JOIN seat_layouts sl ON s.layout_id = sl.layout_id WHERE sl.schedule_id = %s LIMIT 1",
                (SCHEDULE_ID,)
            )
            seat_id, coach = cur.fetchone()

            amount_usd = 8.50
            print('Inserting test booking for compensation verification...')
            cur.execute(
                "INSERT INTO national_rail_bookings (booking_id, user_id, schedule_id, origin_station_id, destination_station_id, travel_date, departure_time, ticket_type, fare_class, coach, seat_id, stops_travelled, amount_usd, status) VALUES (%s, %s, %s, %s, %s, %s::date, %s, %s, %s, %s, %s, %s, %s, 'confirmed')",
                (
                    BOOKING_ID,
                    user_id,
                    SCHEDULE_ID,
                    origin_station_id,
                    destination_station_id,
                    TRAVEL_DATE,
                    departure_time,
                    'single',
                    'standard',
                    coach,
                    seat_id,
                    stops_travelled,
                    amount_usd,
                )
            )
            conn.commit()

    try:
        result = query_compensation_eligibility(BOOKING_ID, str(user_id))
        print('compensation eligibility result:')
        print(result)
    finally:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM national_rail_bookings WHERE booking_id = %s", (BOOKING_ID,))
                conn.commit()
                print('Cleaned up test booking.')
