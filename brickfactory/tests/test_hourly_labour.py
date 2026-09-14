import unittest
from cost_history import capture_production_cost,labour_cost_for_hours
class Cursor:
 def __init__(self):self.calls=[]
 def execute(self,sql,args):self.calls.append((sql,args))
class HourlyLabourTests(unittest.TestCase):
 def test_person_hours_and_currency_rounding(self):
  self.assertEqual(labour_cost_for_hours(32),2600)
  self.assertEqual(labour_cost_for_hours(1.3),105.63)
 def test_fixed_labour_not_double_counted(self):
  c=Cursor();context=dict(rates={'Sand':1},recipe={'Sand':250},making_charges={'Labour':.8,'Loading':.3,'Union':.1},bricks_per_mix=200,snapshot_source='recorded')
  capture_production_cost(c,'2026-09-14',2,400,context,32)
  self.assertEqual(c.calls[0][1][3],500)
  self.assertEqual(c.calls[0][1][4],2760) # 2600 hourly labour + 160 loading/union
  self.assertEqual(c.calls[1][1][:3],(32,81.25,2600))
if __name__=='__main__':unittest.main()
