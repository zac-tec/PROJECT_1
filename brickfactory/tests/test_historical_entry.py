import unittest
from datetime import date
from historical_entry import calculate
class HistoryTest(unittest.TestCase):
 def payload(self):return dict(start_date='2026-08-19',end_date='2026-09-12',opening_bricks=100,recipe={'Chemical':0.35,'Cement':1},days=[])
 def test_multiple_sales_fifo_and_decimal_usage(self):
  p=self.payload();p['days']=[dict(date='2026-08-19',mixes=3,bricks=40,sales=[30,20]),dict(date='2026-08-26',mixes=0,bricks=0,sales=[60])]
  r=calculate(p,date(2026,9,12));self.assertEqual(r['totals']['total'],30);self.assertEqual(r['materials']['Chemical'],1.05);self.assertEqual(r['batches'][1]['remaining'],30)
 def test_curing_rejected_at_sale_date(self):
  p=self.payload();p['opening_bricks']=0;p['days']=[dict(date='2026-08-19',mixes=1,bricks=40,sales=[1])]
  with self.assertRaises(ValueError):calculate(p,date(2026,9,12))
 def test_age_boundaries(self):
  p=self.payload();p['opening_bricks']=0;p['days']=[dict(date=d,mixes=1,bricks=10,sales=[]) for d in ['2026-08-29','2026-09-05','2026-09-06']]
  self.assertEqual(calculate(p,date(2026,9,12))['totals'],dict(curing=10,early_sale=10,fully_cured=10,total=30,saleable=20))
 def test_audit_damage_flows_into_next_day(self):
  p=self.payload();p['opening_bricks']=86793;p['days']=[dict(date='2026-08-31',mixes=0,bricks=0,sales=[],damaged=13376),dict(date='2026-09-01',mixes=1,bricks=100,sales=[])]
  r=calculate(p,date(2026,9,12));self.assertEqual(r['days'][0]['closing'],73417);self.assertEqual(r['days'][1]['opening'],73417)
 def test_damage_cannot_exceed_stock(self):
  p=self.payload();p['days']=[dict(date='2026-08-19',mixes=0,bricks=0,sales=[],damaged=101)]
  with self.assertRaises(ValueError):calculate(p,date(2026,9,12))
 def test_duplicate_dates_rejected(self):
  p=self.payload();p['days']=[dict(date='2026-08-19',mixes=0,bricks=0,sales=[])]*2
  with self.assertRaises(ValueError):calculate(p,date(2026,9,12))
if __name__=='__main__':unittest.main()
