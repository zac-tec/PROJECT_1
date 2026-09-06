# Database setup

The application uses PostgreSQL. Keep the Raspberry Pi database as the source
of truth until the VPS migration is complete. Never run `schema.sql` against
the live Pi database or a restored database.

## Required order

`database_setup.sh` applies the files in this order:

1. `schema.sql` (fresh mode only)
2. `migration_password_hash.sql`
3. `migration_add_brick_sales.sql`
4. `migration_add_stock_adjustments.sql`
5. `migration_material_rates.sql`
6. `migration_client_whatsapp.sql`
7. `migration_fixed_overhead.sql`
8. `migration_cost_history.sql`
9. `migration_brick_batches.sql`
10. `migration_activity_events.sql`

The order matters because brick batches reference sales and stock-adjustment
tables, while cost snapshots reference `production_log`; all of those base
tables must exist first. The migration files use `IF NOT EXISTS` or conflict
guards where practical and do not drop existing application tables.

## Fresh empty installation

Create a new, empty database and set `DATABASE_URL` to that database. Do not
point this command at the Pi database:

```sh
createdb brick_factory_new
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/brick_factory_new ./database_setup.sh fresh
```

Then provision accounts with operator-supplied passwords. Passwords are
hashed with bcrypt and are not stored in SQL or shell history:

```sh
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/brick_factory_new \
    python provision_user.py admin admin
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/brick_factory_new \
    python provision_user.py manager manager
```

Copy `.env.example` to `.env`, set real local values, and point `DB_NAME` at
the new database. Run the isolated test before using the database.

## Restore the existing Pi database

1. Take a verified PostgreSQL dump on the Pi, preferably in custom format.
2. Create a new empty target database on the VPS.
3. Restore the dump into that target database with `pg_restore`.
4. Run migrations only, never `schema.sql`:

```sh
pg_restore --clean --if-exists --no-owner --dbname="$DATABASE_URL" pi.dump
DATABASE_URL="$DATABASE_URL" ./database_setup.sh restore
```

The `--clean` option applies only to the new restore target. Do not use it
against the live Pi database. Keep the Pi unchanged for rollback until login,
production, sales, stock, reports, and record counts have been verified on the
VPS.

`migration_password_hash.sql` preserves existing user rows and renames a
legacy `system_users.password_value` column to `password_hash` when needed.
After restore, run the rehash utility before starting the application:

```sh
DATABASE_URL="$DATABASE_URL" python rehash_passwords.py
```

Do not recreate the live database with the fresh schema. Provision or reset
admin and manager accounts only after the target schema is confirmed.

## Isolated verification

Create a disposable database and pass its connection URL to the test. The
test applies the fresh schema and every migration, checks required tables and
columns, inserts representative production and sales rows, and verifies a
bcrypt password. It does not use the application `DB_NAME` unless you
explicitly point `TEST_DATABASE_URL` there, which must never be done for a live
database.

```sh
createdb brick_factory_setup_test
TEST_DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/brick_factory_setup_test \
    venv/bin/python tests/test_database_setup.py
dropdb brick_factory_setup_test
```

The test database is disposable. Run it again after migrations or restore
procedures change.