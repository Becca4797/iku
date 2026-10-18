from pathlib import Path

from database import get_connection

sql = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")

with get_connection() as conn:
    with conn.cursor() as cursor:
        cursor.execute(sql)
    conn.commit()

print("Tables created.")