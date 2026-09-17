import unittest
from decimal import Decimal
from sales_tax import breakdown
class SalesTaxTests(unittest.TestCase):
 def test_confirmed_rate(self):
  d=breakdown(1000,'8.40');self.assertEqual(d['taxable_amount'],7500);self.assertEqual(d['gst_amount'],900);self.assertEqual(d['total_amount'],8400)
 def test_invoice_rounding_reconciles(self):
  d=breakdown(3,'9.99','10.01');self.assertEqual(d['total_amount'],Decimal('39.98'));self.assertEqual(d['taxable_amount']+d['gst_amount'],d['total_amount'])
 def test_no_double_tax(self):
  self.assertEqual(breakdown(1,'8.40')['total_amount'],Decimal('8.40'))
if __name__=='__main__':unittest.main()
