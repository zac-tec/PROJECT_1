import unittest
from customer_accounts import fifo_allocations
from schemas import BrickSaleRequest
from pydantic import ValidationError
class CustomerAllocationTests(unittest.TestCase):
 def test_partial_payment_oldest_first(self):self.assertEqual(fifo_allocations(0,26000,[25000,25000]),[25000,1000])
 def test_overpayment_capped_at_invoices(self):self.assertEqual(fifo_allocations(0,51000,[25000,25000]),[25000,25000])
 def test_credit_funds_next_purchase(self):self.assertEqual(fifo_allocations(0,51000,[25000,25000,800]),[25000,25000,800])
 def test_opening_debt_is_oldest(self):self.assertEqual(fifo_allocations(5000,26000,[25000,25000]),[21000,0])
 def test_opening_credit(self):self.assertEqual(fifo_allocations(-1000,0,[800]),[800])
 def test_name_or_phone(self):
  for identity in ({'customer_name':'Test'},{'customer_mobile':'9999999999'},{'customer_id':1}):BrickSaleRequest(**identity,bricks_purchased=1,cost_per_brick=8.4,amount_paid=0)
  with self.assertRaises(ValidationError):BrickSaleRequest(bricks_purchased=1,cost_per_brick=8.4,amount_paid=0)
if __name__=='__main__':unittest.main()
