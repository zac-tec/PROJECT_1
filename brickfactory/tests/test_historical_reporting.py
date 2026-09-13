import unittest
from unittest.mock import patch
from historical_reporting import historical_cost_days, monthly_sales
class Cursor:
 def execute(self,*args):pass
 def fetchall(self):return [{'production_date':'2026-09-02'}]
class HistoricalReportingTests(unittest.TestCase):
 def test_estimates_use_mixes_and_exclude_live_dates(self):
  payload={'recipe':{'Chemical':0.35},'days':[
   {'date':'2026-09-01','mixes':3,'bricks':500},
   {'date':'2026-09-02','mixes':9,'bricks':1000},
   {'date':'2026-08-31','mixes':1,'bricks':200},
   {'date':'2026-09-03','mixes':0,'bricks':0}]}
  with patch('historical_reporting.applied_days',return_value=payload),patch('historical_reporting.get_rates',return_value={'Chemical':2}),patch('historical_reporting.get_charges',return_value={'Labour':0.8}):
   result=historical_cost_days(Cursor(),'2026-09')
  self.assertEqual(len(result),1)
  self.assertEqual(result[0]['materials']['Chemical'],1.05)
  self.assertEqual(result[0]['material_cost_total'],2.10)
  self.assertEqual(result[0]['making_cost_total'],400)
  self.assertIsNone(result[0]['labourers_present'])
class SalesReportingTests(unittest.TestCase):
 def test_historical_quantities_do_not_invent_invoice_revenue(self):
  class SalesCursor:
   def execute(self,*args):pass
   def fetchone(self):return dict(bricks=20,revenue=240,collected=100,count=1)
  payload={'days':[{'date':'2026-09-01','sales':[40,60]},{'date':'2026-08-31','sales':[500]}]}
  with patch('historical_reporting.applied_days',return_value=payload):
   r=monthly_sales(SalesCursor(),'2026-09')
  self.assertEqual(r['total_bricks_sold'],120)
  self.assertEqual(r['total_sales_count'],3)
  self.assertEqual(r['recorded_revenue'],240)
  self.assertEqual(r['historical_bricks'],100)
if __name__=='__main__':unittest.main()
