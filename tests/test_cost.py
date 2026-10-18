import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cost'))
from replay import calculate
class CostTests(unittest.TestCase):
 def test_exclusive_categories_and_repricing(self):
  c={'role':'enrich','outcome':'succeeded','wall_seconds':3,'review_ids':['x'],'input_tokens':100,'cached_input_tokens':20,'output_tokens':30,'model':'test','request_id':'x'}
  rates={('test','input'):.01,('test','cached_input'):.002,('test','output'):.02}
  a,_=calculate([c],rates); b,_=calculate([c],{k:2*v for k,v in rates.items()})
  self.assertAlmostEqual(a['enrich']['api_usd'],1.44)
  self.assertAlmostEqual(b['enrich']['api_usd'],2*a['enrich']['api_usd'])
  self.assertEqual(a['enrich']['call_seconds'],b['enrich']['call_seconds'])
 def test_missing_usage_is_visible(self):
  c={'role':'enrich','outcome':'failed','wall_seconds':2,'review_ids':['x'],'input_tokens':None,'output_tokens':None,'model':'test','request_id':'x'}
  _,missing=calculate([c],{});self.assertEqual(missing,['x'])
if __name__=='__main__':unittest.main()
