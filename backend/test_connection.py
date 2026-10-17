
from database import get_connection

try:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT current_database();")
            result = cursor.fetchone()
            print("Connected to:", result[0])

    print("TigerData connection successful!")

except Exception as e:
    print("Connection failed:", type(e).__name__)

