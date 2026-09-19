import unittest
from decimal import Decimal
from pydantic import ValidationError
from schemas import BrickSaleRequest
from sales_tax import breakdown,transport_total

class TransportTests(unittest.TestCase):
    def test_per_brick_delivered_price(self):
        fee=transport_total(1000,'per_brick','0.75')
        sale=breakdown(1000,'8.40',transport_amount=fee)
        self.assertEqual(fee,Decimal('750.00'))
        self.assertEqual(sale['amount_due'],8400)
        self.assertEqual(sale['total_amount'],9150)
        self.assertEqual(sale['taxable_amount']+sale['gst_amount'],9150)
    def test_flat_fee_is_not_multiplied(self):
        self.assertEqual(breakdown(1000,'8.40',transport_amount=transport_total(1000,'flat',500))['total_amount'],8900)
    def test_none_preserves_existing_totals(self):
        self.assertEqual(breakdown(1000,'8.40',50,transport_amount=transport_total(1000,'none'))['total_amount'],8450)
    def test_rate_validation(self):
        base=dict(customer_name='Test',bricks_purchased=10,cost_per_brick=8.4,amount_paid=0)
        for mode,rate in [('none',1),('per_brick',0),('flat',-1),('flat','NaN'),('per_brick','0.751')]:
            with self.subTest(mode=mode,rate=rate),self.assertRaises(ValidationError):
                BrickSaleRequest(**base,transport_mode=mode,transport_rate=rate)
    def test_optional_for_older_clients(self):
        self.assertIsNone(BrickSaleRequest(customer_name='Test',bricks_purchased=1,cost_per_brick=8.4,amount_paid=0).transport_mode)
