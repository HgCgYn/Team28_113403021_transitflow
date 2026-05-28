import psycopg2
import psycopg2.extras
from skeleton.config import PG_DSN

conn = psycopg2.connect(PG_DSN)
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

schedule_id = 'NR_SCH05'
cur.execute("SELECT * FROM seat_layouts WHERE schedule_id = %s", (schedule_id,))
print("Layouts:", cur.fetchall())

cur.execute("SELECT layout_id FROM seat_layouts WHERE schedule_id = %s", (schedule_id,))
layouts = cur.fetchall()
if layouts:
    l_id = layouts[0]['layout_id']
    cur.execute("SELECT * FROM coaches WHERE layout_id = %s", (l_id,))
    print("Coaches:", cur.fetchall())
    
    cur.execute("SELECT count(*) FROM seats WHERE layout_id = %s", (l_id,))
    print("Seats:", cur.fetchall())
