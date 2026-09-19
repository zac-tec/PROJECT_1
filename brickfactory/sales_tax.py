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
