"""PostgreSQL database connection helper for Workforce AI Assistant."""

import os
from pathlib import Path
import psycopg2
from dotenv import load_dotenv

# Always load .env located in the backend folder, regardless of CWD
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)


def get_connection():
    """Create and return a psycopg2 connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "workforce_intelligence"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )
