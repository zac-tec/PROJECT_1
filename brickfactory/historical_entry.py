"""Pure calculation for an explicitly dated historical reconstruction."""
from datetime import date, timedelta
from decimal import Decimal

def calculate(payload, today):
    start=date.fromisoformat(payload['start_date']); end=date.fromisoformat(payload['end_date'])
    if start>end or end>today: raise ValueError('Choose a valid period ending no later than today.')
    opening=payload['opening_bricks']
    if opening<0: raise ValueError('Opening stock cannot be negative.')
    batches=[dict(date=None,initial=opening,remaining=opening)]
    seen=set(); days=[]; consumption={k:Decimal('0') for k in payload['recipe']}
    for row in sorted(payload['days'],key=lambda r:r['date']):
        d=date.fromisoformat(row['date'])
        if d in seen or not start<=d<=end: raise ValueError('Dates must be unique and inside the session period.')
        seen.add(d)
        mixes=row['mixes']; bricks=row['bricks']; sales=row['sales']
        if min(mixes,bricks)<0 or any(q<=0 for q in sales):raise ValueError('Mixes/bricks cannot be negative; sales must be positive.')
        if bricks and not mixes:raise ValueError('Enter actual mixes for each production day to calculate material usage.')
        before=sum(b['remaining'] for b in batches)
        if bricks:batches.append(dict(date=d.isoformat(),initial=bricks,remaining=bricks))
        for qty in sales:
            left=qty
            for b in batches:
                if b['date'] and (d-date.fromisoformat(b['date'])).days<7:continue
                take=min(left,b['remaining']);b['remaining']-=take;left-=take
                if not left:break
            if left:raise ValueError(f'{d}: insufficient stock aged at least 7 days. Check opening stock, dates and sales; short by {left} bricks.')
        used={k:Decimal(str(v))*mixes for k,v in payload['recipe'].items()}
        for k,v in used.items():consumption[k]+=v
        days.append(dict(date=d.isoformat(),opening=before,mixes=mixes,production=bricks,sales=sum(sales),sale_entries=len(sales),closing=sum(b['remaining'] for b in batches),materials={k:float(v) for k,v in used.items()}))
    totals=dict(curing=0,early_sale=0,fully_cured=0)
    for b in batches:
        age=(today-date.fromisoformat(b['date'])).days if b['date'] else None
        stage='fully_cured' if age is None or age>=14 else 'early_sale' if age>=7 else 'curing'
        b.update(age_days=age,stage=stage);totals[stage]+=b['remaining']
    totals.update(total=sum(b['remaining'] for b in batches),saleable=totals['early_sale']+totals['fully_cured'])
    return dict(days=days,batches=batches,totals=totals,materials={k:float(v) for k,v in consumption.items()},as_of=today.isoformat())
