#!/bin/sh
set -eu

MODE=${1:-}
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

case "$MODE" in
    fresh)
        echo "WARNING: fresh mode runs schema.sql, which drops the legacy tables in the target database."
        echo "Use it only against a newly created, empty database."
        psql "${DATABASE_URL:?Set DATABASE_URL to the empty target database}" -v ON_ERROR_STOP=1 -f "$APP_DIR/schema.sql"
        ;;
    restore)
        echo "Restore mode skips schema.sql and preserves the restored database contents."
        ;;
    *)
        echo "Usage: DATABASE_URL=postgresql://... $0 fresh|restore" >&2
        exit 2
        ;;
esac

for migration in \
    migration_password_hash.sql \
    migration_add_brick_sales.sql \
    migration_add_stock_adjustments.sql \
    migration_material_rates.sql \
    migration_client_whatsapp.sql \
    migration_fixed_overhead.sql \
    migration_cost_history.sql \
    migration_brick_batches.sql \
    migration_activity_events.sql \
    migration_historical_ledger.sql
do
    psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -f "$APP_DIR/$migration"
done

echo "Database schema and migrations applied successfully."
echo "Provision users with: python provision_user.py admin admin"
echo "Provision users with: python provision_user.py manager manager"