
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def get_connection():
    """Create a PostgreSQL database connection."""

    required_variables = [
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    ]

    missing_variables = [
        variable
        for variable in required_variables
        if not os.getenv(variable)
    ]

    if missing_variables:
        raise EnvironmentError(
            f"Missing environment variables: {', '.join(missing_variables)}"
        )

    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5434"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        row_factory=dict_row,
    )


def get_user_recommendations(user_id, limit=10):
    """Retrieve ranked destination recommendations for a user."""

    query = """
        SELECT
            r.user_id,
            r.destination_id,
            d.destination_name,
            d.country,
            r.predicted_probability,
            r.rank_position
        FROM recommendations AS r
        JOIN destinations AS d
            ON d.destination_id = r.destination_id
        WHERE r.user_id = %s
        ORDER BY r.rank_position ASC
        LIMIT %s;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (user_id, limit))
            return cursor.fetchall()
