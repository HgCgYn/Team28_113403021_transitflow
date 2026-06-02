# TASK 6 EXTENSION: Test script for verifying delay records querying
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from databases.relational.queries import query_delay_records, _connect

if __name__ == '__main__':
    print('query_delay_records result:')
    result = query_delay_records('NR_SCH01', '2024-10-15')
    print(result)

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM delay_records')
            print('delay_records count:', cur.fetchone()[0])
            cur.execute('SELECT delay_id, schedule_id, travel_date, delay_min, reason FROM delay_records LIMIT 5')
            print('sample rows:')
            for row in cur.fetchall():
                print(row)
