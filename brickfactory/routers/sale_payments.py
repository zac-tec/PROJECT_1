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
    raise HTTPException(409,'Use Customer Accounts to record a payment. Payments clear the oldest unpaid invoices first.')
