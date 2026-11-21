import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

from src.yahoo_capture import capture

class FakeFrame:
    empty=False
    columns=("Open","High","Low","Close","Volume")
    def iterrows(self):
        yield datetime(2026,11,19), {"Open":10,"High":11,"Low":9,"Close":10.5,"Volume":100}

class CaptureTests(unittest.TestCase):
    def test_stages_without_certifying(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"stage.json"
            n=capture("ABC.PA","EUR","2026-11-19","2026-11-20",path,fetcher=lambda *a,**k:FakeFrame())
            self.assertEqual(n,1)
            data=json.loads(path.read_text())
            self.assertFalse(data["paper_eligible"])
            self.assertFalse(data["point_in_time_verified"])
            self.assertEqual(data["observations"][0]["quality_status"],"staged_unverified")
    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"stage.json"
            path.write_text("protected")
            with self.assertRaises(FileExistsError):
                capture("ABC.PA","EUR","2026-11-19","2026-11-20",path,fetcher=lambda *a,**k:FakeFrame())
            self.assertEqual(path.read_text(),"protected")
    def test_invalid_data_no_output(self):
        class BadFrame(FakeFrame):
            def iterrows(self):
                yield datetime(2026,11,19), {"Open":10,"High":9,"Low":9,"Close":10.5,"Volume":100}
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"stage.json"
            with self.assertRaises(ValueError):
                capture("ABC.PA","EUR","2026-11-19","2026-11-20",path,fetcher=lambda *a,**k:BadFrame())
            self.assertFalse(path.exists())
