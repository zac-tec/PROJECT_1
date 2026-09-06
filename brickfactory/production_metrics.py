"""Shared production display metrics; positive halves round upwards."""

def average_bricks_per_mix(bricks, mixes):
    if mixes <= 0:
        return None
    return (2 * bricks + mixes) // (2 * mixes)
