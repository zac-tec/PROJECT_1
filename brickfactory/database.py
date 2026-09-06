"""
DATABASE
The simplest possible way to connect to Postgres: open a connection,
run a query, close it. No connection pooling yet, no ORM — just plain
psycopg2, so it's easy to read line by line.
"""

import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "brick_factory")
DB_USER = os.getenv("DB_USER", "sachusamuel")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    """
    Opens a fresh connection to the brick_factory database.
    cursor_factory=RealDictCursor means rows come back as dictionaries
    (e.g. row["material_name"]) instead of plain tuples — much easier
    to turn into JSON for the API to return.
    """
    connection_args = {"cursor_factory": psycopg2.extras.RealDictCursor}
    if DATABASE_URL:
        connection_args["dsn"] = DATABASE_URL
    else:
        connection_args.update(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
    return psycopg2.connect(**connection_args)
