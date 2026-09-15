"""Shared production display metrics; positive halves round upwards."""

def average_bricks_per_mix(bricks, mixes):
    if mixes <= 0:
        return None
    return (2 * bricks + mixes) // (2 * mixes)


def daily_averages(bricks, mixes, working_hours):
    from decimal import Decimal, ROUND_HALF_UP
    from cost_history import labour_cost_for_hours
    average=float((Decimal(str(bricks))/Decimal(str(mixes))).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)) if mixes else None
    labour=labour_cost_for_hours(working_hours) if working_hours is not None else None
    per_brick=float((Decimal(str(labour))/Decimal(str(bricks))).quantize(Decimal('0.0001'),rounding=ROUND_HALF_UP)) if bricks and labour is not None else None
    return dict(avg_bricks_per_mix=average,labour_cost_per_brick=per_brick)
