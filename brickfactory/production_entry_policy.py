"""Server-enforced production and sales entry window in factory time."""
from datetime import timedelta
from fastapi import HTTPException
from batch_stock import factory_today
from services import get_text_setting

KEY = 'manager_production_backdate_days'

def entry_window(cursor):
    days = int(get_text_setting(cursor, KEY, '1'))
    today = factory_today()
    cursor.execute('SELECT cutover_date FROM brick_batch_state WHERE id=1')
    row = cursor.fetchone()
    earliest = today - timedelta(days=days)
    # Older stock was finalized by the opening-stock import, not daily entry.
    if row:
        earliest = max(earliest, row['cutover_date'] + timedelta(days=1))
    return {'backdate_days': days, 'today': today, 'earliest_date': earliest}

def validate_entry_date(cursor, target=None):
    window = entry_window(cursor)
    target = target or window['today']
    if target < window['earliest_date'] or target > window['today']:
        raise HTTPException(403, 'Select an entry date from '
            + window['earliest_date'].strftime('%d-%m-%Y') + ' to '
            + window['today'].strftime('%d-%m-%Y') + '. The admin controls the previous-day allowance; finalized opening history is protected.')
    return target
