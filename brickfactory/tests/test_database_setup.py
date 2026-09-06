"""Verify fresh database setup in a disposable PostgreSQL database.

Run only with TEST_DATABASE_URL pointing at a temporary database. The test
never reads the application's DB_NAME configuration.
"""

import os
from pathlib import Path

import psycopg2

from auth_utils import hash_password, verify_password


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = (
    "migration_password_hash.sql",
    "migration_add_brick_sales.sql",
    "migration_add_stock_adjustments.sql",
    "migration_material_rates.sql",
    "migration_client_whatsapp.sql",
    "migration_fixed_overhead.sql",
    "migration_cost_history.sql",
    "migration_brick_batches.sql",
    "migration_activity_events.sql",
)

REQUIRED_TABLES = {
    "materials_inventory",
    "recipe",
    "rate_history",
    "making_charges",
    "making_charges_history",
    "production_log",
    "utility_bills",
    "settings",
    "system_users",
    "outlet_stock",
    "brick_sales",
    "outlet_stock_adjustments",
    "material_rate_versions",
    "app_settings_text",
    "production_cost_snapshots",
    "production_revision_history",
    "monthly_overhead_versions",
    "brick_batch_state",
    "brick_batches",
    "brick_sale_allocations",
    "brick_batch_movements",
    "factory_activity_events",
}


def execute_file(cursor, filename: str) -> None:
    cursor.execute((ROOT / filename).read_text())


def main() -> None:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        raise SystemExit("Set TEST_DATABASE_URL to a disposable PostgreSQL database.")

    connection = psycopg2.connect(url)
    try:
        connection.autocommit = True
        with connection.cursor() as cursor:
            execute_file(cursor, "schema.sql")
            for migration in MIGRATIONS:
                execute_file(cursor, migration)

            cursor.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
            tables = {row[0] for row in cursor.fetchall()}
            missing = REQUIRED_TABLES - tables
            assert not missing, f"Missing tables: {sorted(missing)}"

            cursor.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'system_users'"
            )
            user_columns = {row[0] for row in cursor.fetchall()}
            assert "password_hash" in user_columns
            assert "password_value" not in user_columns

            password = "temporary-test-password"
            password_hash = hash_password(password)
            cursor.execute(
                "INSERT INTO system_users (username, password_hash, user_role) "
                "VALUES (%s, %s, %s)",
                ("setup-test-admin", password_hash, "admin"),
            )
            assert verify_password(password, password_hash)

            cursor.execute(
                "INSERT INTO production_log "
                "(production_date, timestamp_entered, mixes_run, bricks_made, "
                "labourers_present) VALUES (DATE '2099-01-01', TIME '08:00', 1, 182, 1)"
            )
            cursor.execute(
                "INSERT INTO brick_sales "
                "(sale_date, sale_timestamp, customer_name, customer_mobile, "
                "bricks_purchased, cost_per_brick, amount_due, amount_paid) "
                "VALUES (DATE '2099-01-01', TIME '09:00', 'Setup Test', '0000000000', "
                "10, 7.50, 75.00, 75.00)"
            )
            cursor.execute(
                "SELECT COUNT(*) FROM production_log WHERE production_date = DATE '2099-01-01'"
            )
            assert cursor.fetchone()[0] == 1
            cursor.execute(
                "SELECT COUNT(*) FROM brick_sales WHERE sale_date = DATE '2099-01-01'"
            )
            assert cursor.fetchone()[0] == 1
    finally:
        connection.close()

    print("PASS: fresh schema, ordered migrations, bcrypt user, production and sale rows")


if __name__ == "__main__":
    main()