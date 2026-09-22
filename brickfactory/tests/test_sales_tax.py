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

class PreGstPricingTests(unittest.TestCase):
 def test_actual_delivered_bill(self):
  from sales_tax import price_sale
  d=price_sale(2500,'8.17',transport_mode='flat',transport_rate='2200',pricing_mode='delivered_base')
  self.assertEqual(d['brick_base_amount'],Decimal('18225'))
  self.assertEqual(d['base_unit_price'],Decimal('7.29'))
  self.assertEqual(d['transport_per_brick'],Decimal('0.88'))
  self.assertEqual(d['gst_amount'],Decimal('2451'))
  self.assertEqual(d['transport_gst'],Decimal('264'))
  self.assertEqual(d['total_amount'],Decimal('22876'))
  self.assertEqual(d['taxable_amount']-d['transport_base_amount'],Decimal('18225'))
 def test_methods_match(self):
  from sales_tax import price_sale
  a=price_sale(2500,'7.29',transport_mode='flat',transport_rate='2200',pricing_mode='brick_base')
  b=price_sale(2500,'8.17',transport_mode='flat',transport_rate='2200',pricing_mode='delivered_base')
  for key in ('total_amount','taxable_amount','gst_amount','brick_base_amount','transport_base_amount'):
   self.assertEqual(a[key],b[key])
 def test_original_brick_price_and_per_brick_transport(self):
  from sales_tax import price_sale
  d=price_sale(2500,'7.30',transport_mode='per_brick',transport_rate='.88',pricing_mode='brick_base')
  self.assertEqual(d['total_amount'],Decimal('22904'))
 def test_no_transport(self):
  from sales_tax import price_sale
  self.assertEqual(price_sale(100,'7.30',pricing_mode='brick_base')['total_amount'],Decimal('817.60'))
 def test_invalid_delivered_price(self):
  from sales_tax import price_sale
  with self.assertRaises(ValueError):price_sale(100,'1',transport_mode='flat',transport_rate=100,pricing_mode='delivered_base')
 def test_fractional_transport_does_not_round_unit_rate_before_total(self):
  from sales_tax import price_sale
  d=price_sale(3,'8.17',transport_mode='flat',transport_rate='1',pricing_mode='delivered_base')
  self.assertEqual(d['total_amount'],Decimal('27.45'))
  self.assertEqual(d['brick_base_amount'],Decimal('23.51'))
 def test_rounding_and_compatibility_fields_reconcile(self):
  from sales_tax import price_sale
  for mode in ('brick_base','delivered_base','legacy_inclusive'):
   d=price_sale(3,'8.17','.04','flat','.04',mode)
   self.assertEqual(d['amount_due']+d['transport_amount']+d['other_charges'],d['total_amount'])
   self.assertEqual(d['taxable_amount']+d['gst_amount'],d['total_amount'])
 def test_legacy_bill_unchanged(self):
  from sales_tax import price_sale
  d=price_sale(2500,'8.40',transport_mode='flat',transport_rate='2200')
  self.assertEqual(d['total_amount'],Decimal('23200'))
  self.assertIsNone(d['transport_base_amount'])

if __name__=='__main__':unittest.main()
