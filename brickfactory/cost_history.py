"""Effective-dated material rates and immutable daily production costs."""
import json
from pathlib import Path

from services import get_bricks_per_mix, get_charges, get_rates, get_recipe


def initialize_cost_history():
    from database import get_connection

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(Path(__file__).with_name("migration_cost_history.sql").read_text())
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def production_cost_context(cursor, production_date):
    cursor.execute("SELECT * FROM production_cost_snapshots WHERE production_date=%s", (production_date,))
    existing = cursor.fetchone()
    if existing:
        return existing
    return dict(rates=get_rates(cursor, production_date), recipe=get_recipe(cursor),
                making_charges=get_charges(cursor), bricks_per_mix=get_bricks_per_mix(cursor),
                snapshot_source="recorded")


def capture_production_cost(cursor, production_date, mixes, bricks, context):
    rates = {k: float(v) for k, v in context['rates'].items()}
    recipe = {k: float(v) for k, v in context['recipe'].items()}
    charges = {k: float(v) for k, v in context['making_charges'].items()}
    bricks_per_mix = float(context['bricks_per_mix'])
    source = context['snapshot_source']
    material_per_mix = sum(quantity * rates.get(material, 0) for material, quantity in recipe.items())
    making_per_brick = sum(charges.values())
    cursor.execute(
        """INSERT INTO production_cost_snapshots
           (production_date, mixes_run, bricks_made, material_cost_total, making_cost_total,
            material_cost_per_mix, making_cost_per_brick, rates, recipe, making_charges,
            bricks_per_mix, snapshot_source, captured_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,CURRENT_TIMESTAMP)
           ON CONFLICT (production_date) DO UPDATE SET
             mixes_run=EXCLUDED.mixes_run, bricks_made=EXCLUDED.bricks_made,
             material_cost_total=EXCLUDED.material_cost_total,
             making_cost_total=EXCLUDED.making_cost_total,
             material_cost_per_mix=EXCLUDED.material_cost_per_mix,
             making_cost_per_brick=EXCLUDED.making_cost_per_brick,
             rates=EXCLUDED.rates, recipe=EXCLUDED.recipe,
             making_charges=EXCLUDED.making_charges, bricks_per_mix=EXCLUDED.bricks_per_mix,
             snapshot_source=EXCLUDED.snapshot_source, captured_at=CURRENT_TIMESTAMP""",
        (
            production_date, mixes, bricks, round(mixes * material_per_mix, 2),
            round(bricks * making_per_brick, 2), material_per_mix, making_per_brick,
            json.dumps(rates), json.dumps(recipe), json.dumps(charges), bricks_per_mix, source,
        ),
    )
