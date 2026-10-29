import sys
from pathlib import Path
import unittest
import gzip
import tempfile
from fractions import Fraction as Q

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from model import (
    baseline_roster,
    bounds,
    growth,
    interval,
    load_counts,
    mask_units,
    pair_cohort,
    point_views,
    sign,
)


class ReportingFixtures(unittest.TestCase):
    def test_duplicate_key_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "data/source"
            dest.mkdir(parents=True)
            (dest / "counts.csv.gz").write_bytes(
                gzip.compress(
                    b"agency,service,year,month,upt\n00001,DO,2019,1,1\n00001,DO,2019,1,2\n"
                )
            )
            with self.assertRaises(ValueError):
                load_counts(directory)

    def test_services_remain_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "data/source"
            dest.mkdir(parents=True)
            (dest / "counts.csv.gz").write_bytes(
                gzip.compress(
                    b"agency,service,year,month,upt\n00001,DO,2019,1,1\n00001,PT,2019,1,2\n"
                )
            )
            self.assertEqual(len(load_counts(directory)), 2)

    def test_zero_is_observed(self):
        data = {("00001", "DO", 2019, m): 0 for m in range(1, 13)}
        data["00001", "DO", 2019, 1] = 1
        self.assertEqual(baseline_roster(data), [("00001", "DO")])

    def test_null_excluded(self):
        data = {("00001", "DO", 2019, m): 1 for m in range(1, 13)}
        data["00001", "DO", 2019, 2] = None
        self.assertEqual(baseline_roster(data), [])

    def test_absent_and_null_separate(self):
        data = {("00001", "DO", y, m): 1 for y in [2019, 2020] for m in range(1, 13)}
        del data["00001", "DO", 2020, 1]
        data["00001", "DO", 2020, 2] = None
        keys, rows = pair_cohort(data, [("00001", "DO")], 2020)
        self.assertEqual(
            (keys, rows[0]["current_absent"], rows[0]["current_null"]), ([], 1, 1)
        )

    def test_fraction_rounds_up(self):
        keys = [("00001", "DO"), ("00002", "DO"), ("00003", "DO")]
        data = {(*k, 2019, m): 1 for k in keys for m in range(1, 13)}
        self.assertEqual(len(mask_units(keys, data, "1/10", "identifier")), 1)

    def test_volume_tie_identifier(self):
        keys = [("00002", "DO"), ("00001", "DO")]
        data = {(*k, 2019, m): 1 for k in keys for m in range(1, 13)}
        self.assertEqual(
            mask_units(keys, data, "1/2", "baseline_volume_desc"), {("00001", "DO")}
        )

    def test_no_denominator(self):
        self.assertIsNone(growth(0, 4))

    def test_signs(self):
        self.assertEqual(
            [sign(x) for x in [None, -1, 0, 1]],
            ["undefined", "negative", "zero", "positive"],
        )

    def test_point_views(self):
        p = {"a": 100, "b": 10}
        c = {"a": 80, "b": 20}
        v = point_views(p, c, {"a"}, set())
        self.assertEqual(v, dict(zero_fill=9, count_rescaled=4, matched_panel=1))

    def test_both_masking(self):
        p = {"a": 100, "b": 10}
        c = {"a": 80, "b": 20}
        v = point_views(p, c, {"a"}, {"a"})
        self.assertEqual(set(v.values()), {Q(1)})

    def test_interval_finite(self):
        self.assertEqual(interval(10, 20, 5, 30), (Q(-3, 4), Q(2), "finite"))

    def test_interval_unbounded(self):
        self.assertEqual(interval(0, 20, 5, 30), (Q(-3, 4), None, "unbounded_upper"))

    def test_interval_no_reference(self):
        self.assertEqual(interval(0, 0, 0, 30), (None, None, "undefined_reference"))

    def test_interval_zero_current(self):
        self.assertEqual(interval(0, 20, 0, 0), (Q(-1), Q(-1), "finite"))

    def test_component_violation_retained(self):
        b = bounds({"a": 12}, {"a": 9}, {"a": 10}, {"a"}, set(), 1)
        self.assertEqual(b["violated_components"], 1)


if __name__ == "__main__":
    unittest.main()
