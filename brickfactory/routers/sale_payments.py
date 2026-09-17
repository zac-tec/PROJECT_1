"""Admin settlement of existing invoices; never changes stock or revenue."""
from decimal import Decimal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from dependencies import require_admin
from database import get_connection
router=APIRouter(prefix='/admin/sales',tags=['sale payments'])
class Settlement(BaseModel):
    expected_total: Decimal = Field(ge=0,max_digits=12,decimal_places=2)
    expected_paid: Decimal = Field(ge=0,max_digits=12,decimal_places=2)

@router.post('/{sale_id}/mark-paid')
def mark_paid(sale_id:int,body:Settlement,user=Depends(require_admin)):
    conn=get_connection()
    try:
        with conn.cursor() as c:
            c.execute('SELECT total_amount,amount_paid FROM brick_sales WHERE sale_id=%s FOR UPDATE',(sale_id,))
            row=c.fetchone()
            if not row:raise HTTPException(404,'Sale not found.')
            total,paid=row['total_amount'],row['amount_paid']
            if paid>=total:return {'message':'Already fully paid.','amount_paid':paid,'balance':0}
            if total!=body.expected_total or paid!=body.expected_paid:
                raise HTTPException(409,'This invoice changed. Refresh and check the balance before marking it paid.')
            c.execute('UPDATE brick_sales SET amount_paid=total_amount WHERE sale_id=%s',(sale_id,))
            c.execute('INSERT INTO sale_payment_audit(sale_id,recorded_by,previous_paid,new_paid) VALUES(%s,%s,%s,%s)',(sale_id,user['username'],paid,total))
        conn.commit()
        return {'message':'Invoice marked fully paid.','amount_paid':total,'balance':0}
    except Exception:conn.rollback();raise
    finally:conn.close()
