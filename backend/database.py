
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

# Load the TigerData credentials
load_dotenv(Path(__file__).parent / ".env")

def get_connection():
    database_url = os.getenv("TIMESCALE_SERVICE_URL")

    if not database_url:
        raise ValueError("TIMESCALE_SERVICE_URL not found in .env")

    return psycopg.connect(database_url)

