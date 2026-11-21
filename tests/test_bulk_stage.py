import csv
import json
import tempfile
import unittest
from pathlib import Path
from src.bulk_stage import run

class BulkTests(unittest.TestCase):
    def manifest(self, directory, rows):
        p=Path(directory)/"manifest.csv"
        with p.open("w",newline="") as f:
            w=csv.writer(f);w.writerow(["symbol","currency"]);w.writerows(rows)
        return p
    def test_bounded_and_resumable(self):
        with tempfile.TemporaryDirectory() as d:
            m=self.manifest(d,[("SAMPO.HE","EUR"),("ABC.PA","EUR")])
            calls=[]
            def fake(symbol,currency,start,end,target):
                calls.append(symbol)
                Path(target).write_text(json.dumps({"source_symbol":symbol,"currency":currency,
                    "request_start":start,"request_end_exclusive":end,
                    "paper_eligible":False,"point_in_time_verified":False,
                    "observations":[{"quality_status":"staged_unverified"}]}))
            args=dict(max_symbols=1,delay=1,capture_fn=fake,sleep_fn=lambda _:None)
            first=run(m,Path(d)/"out","2026-11-17","2026-11-21",**args)
            second=run(m,Path(d)/"out","2026-11-17","2026-11-21",**args)
            self.assertEqual((first["success"],second["skipped"],calls),(1,1,["SAMPO.HE"]))
    def test_duplicate_manifest_rejected_before_fetch(self):
        with tempfile.TemporaryDirectory() as d:
            m=self.manifest(d,[("ABC.PA","EUR"),("abc.pa","EUR")])
            with self.assertRaisesRegex(ValueError,"duplicate"):
                run(m,Path(d)/"out","2026-11-17","2026-11-21")
    def test_invalid_currency_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            m=self.manifest(d,[("ABC.PA","ZZZ")])
            with self.assertRaisesRegex(ValueError,"invalid manifest"):
                run(m,Path(d)/"out","2026-11-17","2026-11-21")
    def test_failure_isolated(self):
        with tempfile.TemporaryDirectory() as d:
            m=self.manifest(d,[("ABC.PA","EUR"),("SAMPO.HE","EUR")])
            def fail(*a): raise ValueError("provider offline")
            r=run(m,Path(d)/"out","2026-11-17","2026-11-21",
                  max_symbols=2,delay=1,capture_fn=fail,sleep_fn=lambda _:None)
            self.assertEqual(r["failed"],2)
            self.assertFalse(r["paper_eligible"])
