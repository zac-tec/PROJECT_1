"""GST-inclusive sale arithmetic, rounded per invoice using Decimal."""
from decimal import Decimal, ROUND_HALF_UP

def transport_total(quantity, mode, rate=0):
    amount=Decimal(str(rate)) * (Decimal(quantity) if mode == 'per_brick' else 1)
    return Decimal('0.00') if mode in (None,'none') else amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def breakdown(quantity, inclusive_price, other_charges=0, gst_rate=12, transport_amount=0):
    price=Decimal(str(inclusive_price));rate=Decimal(str(gst_rate))
    rounded=lambda x:x.quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
    bricks=rounded(Decimal(quantity)*price)
    gross=rounded(bricks+Decimal(str(other_charges))+Decimal(str(transport_amount)))
    net=rounded(gross/(1+rate/100))
    return dict(amount_due=bricks,total_amount=gross,taxable_amount=net,
                gst_amount=gross-net,gst_rate=rate,
                base_unit_price=price/(1+rate/100))


def price_sale(quantity, unit_price, other_charges=0, transport_mode=None,
               transport_rate=0, pricing_mode='legacy_inclusive'):
    """One source of truth for preview/save. All amounts are invoice-rounded.

    Legacy fields remain GST-inclusive for existing consumers; explicit base
    amounts preserve the driver's payment and new invoice breakdown exactly.
    """
    rounded = lambda x: x.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    price = Decimal(str(unit_price))
    other = rounded(Decimal(str(other_charges)))
    transport = transport_total(quantity, transport_mode, transport_rate)
    if pricing_mode == 'legacy_inclusive':
        result = breakdown(quantity, price, other, transport_amount=transport)
        result.update(cost_per_brick=price, other_charges=other,
                      transport_amount=transport, brick_base_amount=None,
                      transport_base_amount=None, other_base_amount=None)
    else:
        if pricing_mode not in ('brick_base', 'delivered_base'):
            raise ValueError('Choose a valid pricing method.')
        bricks = rounded(Decimal(quantity) * price)
        if pricing_mode == 'delivered_base':
            bricks -= transport
        if bricks <= 0:
            raise ValueError('The delivered amount must be greater than the driver charge.')
        net = bricks + transport + other
        gst = rounded(net * Decimal('0.12'))
        transport_gst = rounded(transport * Decimal('0.12'))
        other_gst = rounded(other * Decimal('0.12'))
        brick_gst = gst - transport_gst - other_gst
        result = dict(amount_due=bricks + brick_gst, total_amount=net + gst,
                      taxable_amount=net, gst_amount=gst, gst_rate=Decimal(12),
                      base_unit_price=bricks / Decimal(quantity),
                      cost_per_brick=(bricks + brick_gst) / Decimal(quantity),
                      other_charges=other + other_gst,
                      transport_amount=transport + transport_gst,
                      brick_base_amount=bricks, transport_base_amount=transport,
                      other_base_amount=other, brick_gst=brick_gst,
                      transport_gst=transport_gst, other_gst=other_gst,
                      delivered_base_price=(bricks + transport) / Decimal(quantity),
                      transport_per_brick=transport / Decimal(quantity))
    if result['total_amount'] > Decimal('9999999999.99'):
        raise ValueError('Invoice amount is too large.')
    result.update(pricing_mode=pricing_mode, entered_unit_price=price)
    return result
