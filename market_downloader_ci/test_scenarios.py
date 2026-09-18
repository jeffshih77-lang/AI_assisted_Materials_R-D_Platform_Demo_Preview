from __future__ import annotations
import unittest
from datetime import date,timedelta
def bounded_range(start,end,max_days=7):
    if end<start: raise ValueError("reverse range")
    if (end-start).days>max_days: raise ValueError("range too large")
    return [start+timedelta(days=i) for i in range((end-start).days+1)]
def auto_fill(d,max_backscan=7):
    if max_backscan<0 or max_backscan>14: raise ValueError("unsafe backscan")
    return [d-timedelta(days=i) for i in range(max_backscan+1)]
def exact_guard(requested,observed): return observed==requested
class ScenarioTests(unittest.TestCase):
    def test_different_dates(self):
        a,b=date(2026,9,15),date(2026,9,16)
        self.assertTrue(exact_guard(a,a)); self.assertTrue(exact_guard(b,b)); self.assertFalse(exact_guard(a,b))
    def test_boundary(self):
        self.assertEqual(date(2026,9,13).weekday(),6); self.assertFalse(exact_guard(date(2026,9,13),date(2026,9,11)))
    def test_bounded_range(self):
        self.assertEqual(len(bounded_range(date(2026,9,14),date(2026,9,16))),3)
        with self.assertRaises(ValueError): bounded_range(date(2026,9,1),date(2026,9,20))
        with self.assertRaises(ValueError): bounded_range(date(2026,9,16),date(2026,9,15))
    def test_wrong_day(self): self.assertFalse(exact_guard(date(2026,9,15),date(2026,9,16)))
    def test_auto_fill(self):
        xs=auto_fill(date(2026,9,17),7); self.assertEqual(xs[0],date(2026,9,17)); self.assertEqual(xs[-1],date(2026,9,10)); self.assertEqual(len(xs),8)
    def test_repeat_idempotence_model(self):
        store={}
        def put(k,payload):
            old=store.get(k)
            if old is None: store[k]=payload; return "NEW"
            if old==payload: return "REUSE"
            store[k+"#r2"]=payload; return "REVISION"
        self.assertEqual(put("TPEX/2026-09-15",b"same"),"NEW"); self.assertEqual(put("TPEX/2026-09-15",b"same"),"REUSE"); self.assertEqual(len(store),1)
        self.assertEqual(put("TPEX/2026-09-15",b"changed"),"REVISION"); self.assertEqual(len(store),2)
if __name__=="__main__": unittest.main(verbosity=2)
