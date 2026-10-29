"""Reconstruct all cohort, mask, point and interval exports independently in SQL/Q."""

import argparse
import csv
from fractions import Fraction as Q
import gzip
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]


def verify(phase, root=ROOT):
    root = Path(root)
    config = json.loads((root / "protocol.json").read_text(encoding="utf-8"))
    db = sqlite3.connect(":memory:")
    db.execute(
        "CREATE TABLE facts(agency TEXT, service TEXT, year INT, month INT, upt INT, PRIMARY KEY(agency,service,year,month))"
    )
    with gzip.open(root / "data/source/counts.csv.gz", "rt", newline="") as stream:
        for row in csv.DictReader(stream):
            db.execute(
                "INSERT INTO facts VALUES(?,?,?,?,?)",
                (
                    row["agency"],
                    row["service"],
                    int(row["year"]),
                    int(row["month"]),
                    None if row["upt"] == "" else int(row["upt"]),
                ),
            )
    db.execute(
        "CREATE TABLE baseline AS SELECT agency,service,SUM(upt) AS volume FROM facts WHERE year=2019 GROUP BY agency,service HAVING COUNT(*)=12 AND COUNT(upt)=12 AND SUM(upt)>0"
    )
    roster = list(
        db.execute("SELECT agency,service FROM baseline ORDER BY agency,service")
    )
    years = (
        config["development_years"] if phase == "development" else config["held_years"]
    )
    tables = {}
    keys = {
        "cohorts": ["year", "agency", "service"],
        "masks": ["year", "fraction", "ranking", "masked_side", "agency", "service"],
        "points": ["year", "month", "fraction", "ranking", "masked_side", "view"],
        "bounds": ["year", "month", "fraction", "ranking", "masked_side", "gamma"],
    }
    for name, fields in keys.items():
        with (root / "results" / (phase + "-" + name + ".csv")).open(
            encoding="utf-8", newline=""
        ) as stream:
            rows = list(csv.DictReader(stream))
        mapping = {tuple(row[f] for f in fields): row for row in rows}
        assert len(mapping) == len(rows), ("duplicate export", name)
        tables[name] = mapping
    checks = 0

    def check(name, expected):
        nonlocal checks
        row = tables[name].pop(tuple(str(expected[f]) for f in keys[name]))
        canonical = {
            key: "" if value is None else str(value) for key, value in expected.items()
        }
        assert row == canonical, (name, canonical, row)
        checks += len(canonical)

    def direction(value):
        if value is None:
            return "undefined"
        if value == 0:
            return "zero"
        return "negative" if value < 0 else "positive"

    for year in years:
        db.execute("DROP TABLE IF EXISTS eligible")
        db.execute(
            "CREATE TEMP TABLE eligible AS SELECT f.agency,f.service FROM facts f JOIN baseline b USING(agency,service) WHERE f.year IN (?,?) GROUP BY f.agency,f.service HAVING COUNT(*)=24 AND COUNT(f.upt)=24",
            (year - 1, year),
        )
        cohort = list(
            db.execute("SELECT agency,service FROM eligible ORDER BY agency,service")
        )
        n = len(cohort)
        assert n > 0
        for agency, service in roster:
            expected = dict(
                year=year,
                agency=agency,
                service=service,
                eligible=int((agency, service) in cohort),
            )
            for label, y in [("prior", year - 1), ("current", year)]:
                count, nonnull = db.execute(
                    "SELECT COUNT(*),COUNT(upt) FROM facts WHERE agency=? AND service=? AND year=?",
                    (agency, service, y),
                ).fetchone()
                expected[label + "_absent"] = 12 - count
                expected[label + "_null"] = count - nonnull
            check("cohorts", expected)
        baseline_sum = db.execute(
            "SELECT SUM(volume) FROM eligible JOIN baseline USING(agency,service)"
        ).fetchone()[0]
        vectors = {
            month: list(
                db.execute(
                    "SELECT e.agency,e.service,p.upt,c.upt,b.upt FROM eligible e JOIN facts p ON p.agency=e.agency AND p.service=e.service AND p.year=? AND p.month=? JOIN facts c ON c.agency=e.agency AND c.service=e.service AND c.year=? AND c.month=p.month JOIN facts b ON b.agency=e.agency AND b.service=e.service AND b.year=2019 AND b.month=p.month",
                    (year - 1, month, year),
                )
            )
            for month in range(1, 13)
        }
        for fraction in config["mask_fractions"]:
            q = Q(fraction)
            count = -(-q.numerator * n // q.denominator)
            for ranking in config["rankings"]:
                order = {
                    "baseline_volume_desc": "volume DESC,agency,service",
                    "baseline_volume_asc": "volume ASC,agency,service",
                    "identifier": "agency,service",
                }[ranking]
                ranked = list(
                    db.execute(
                        "SELECT agency,service,volume,ROW_NUMBER() OVER (ORDER BY "
                        + order
                        + ") AS rnk FROM eligible JOIN baseline USING(agency,service)"
                    )
                )
                hidden = {(a, s) for a, s, v, rank in ranked if rank <= count}
                hidden_share = Q(
                    sum(v for a, s, v, rank in ranked if rank <= count), baseline_sum
                )
                for side in config["masked_sides"]:
                    hp = hidden if side != "current" else set()
                    hc = hidden if side != "prior" else set()
                    for agency, service in hidden:
                        check(
                            "masks",
                            dict(
                                year=year,
                                fraction=fraction,
                                ranking=ranking,
                                masked_side=side,
                                agency=agency,
                                service=service,
                            ),
                        )
                    for month, vector in vectors.items():
                        bp = sum(r[2] for r in vector)
                        ac = sum(r[3] for r in vector)
                        truth = None if bp == 0 else Q(ac - bp, bp)
                        common = dict(
                            year=year,
                            month=month,
                            fraction=fraction,
                            ranking=ranking,
                            masked_side=side,
                            units=n,
                            hidden_units=count,
                            hidden_baseline_volume_fraction=hidden_share,
                            truth_prior=bp,
                            truth_current=ac,
                            truth_growth=truth,
                            truth_sign=direction(truth),
                        )
                        pknown = sum(p for a, s, p, c, b in vector if (a, s) not in hp)
                        cknown = sum(c for a, s, p, c, b in vector if (a, s) not in hc)
                        np = n - len(hp)
                        nc = n - len(hc)
                        paired = [r for r in vector if r[:2] not in hp | hc]
                        pm = sum(r[2] for r in paired)
                        cm = sum(r[3] for r in paired)
                        estimates = {
                            "zero_fill": (
                                None if pknown == 0 else Q(cknown - pknown, pknown)
                            ),
                            "count_rescaled": (
                                None
                                if pknown == 0 or np == 0 or nc == 0
                                else Q(cknown * np - pknown * nc, pknown * nc)
                            ),
                            "matched_panel": None if pm == 0 else Q(cm - pm, pm),
                        }
                        for view, value in estimates.items():
                            error = (
                                None
                                if value is None or truth is None
                                else (value - truth) * 100
                            )
                            check(
                                "points",
                                dict(
                                    **common,
                                    view=view,
                                    growth=value,
                                    growth_sign=direction(value),
                                    error_pp=error,
                                    abs_error_pp=None if error is None else abs(error),
                                    squared_error_pp=(
                                        None if error is None else error**2
                                    ),
                                    sign_error=(
                                        None
                                        if error is None
                                        else int(direction(value) != direction(truth))
                                    ),
                                    false_growth=(
                                        None
                                        if error is None
                                        else int(value > 0 and truth <= 0)
                                    ),
                                    missed_growth=(
                                        None
                                        if error is None
                                        else int(value <= 0 and truth > 0)
                                    )
                                ),
                            )
                        for gamma in config["bound_multipliers"]:
                            g = int(gamma)
                            pu = pknown + g * sum(
                                b for a, s, p, c, b in vector if (a, s) in hp
                            )
                            cu = cknown + g * sum(
                                b for a, s, p, c, b in vector if (a, s) in hc
                            )
                            violations = sum(
                                int(p > g * b)
                                for a, s, p, c, b in vector
                                if (a, s) in hp
                            ) + sum(
                                int(c > g * b)
                                for a, s, p, c, b in vector
                                if (a, s) in hc
                            )
                            if pu == 0:
                                lo, hi, state = None, None, "undefined_reference"
                            else:
                                lo = Q(cknown - pu, pu)
                                hi = (
                                    Q(cu - pknown, pknown)
                                    if pknown > 0
                                    else (Q(-1) if cu == 0 else None)
                                )
                                state = "unbounded_upper" if hi is None else "finite"
                            contains = (
                                None
                                if truth is None or lo is None
                                else int(lo <= truth and (hi is None or truth <= hi))
                            )
                            positive = int(lo is not None and lo > 0)
                            check(
                                "bounds",
                                dict(
                                    **common,
                                    gamma=gamma,
                                    prior_lower=pknown,
                                    prior_upper=pu,
                                    current_lower=cknown,
                                    current_upper=cu,
                                    lower=lo,
                                    upper=hi,
                                    state=state,
                                    violated_components=violations,
                                    width=None if lo is None or hi is None else hi - lo,
                                    truth_contained=contains,
                                    assumptions_valid=int(violations == 0),
                                    conditional_positive_lower=positive,
                                    assumption_supported_positive_lower=int(
                                        positive and violations == 0
                                    )
                                ),
                            )
    assert not any(tables.values()), "Unexpected export rows"
    return dict(
        status="PASS",
        phase=phase,
        exact_export_scalar_checks=checks,
        baseline_roster_units=len(roster),
        scope="Independent SQLite eligibility/window ranking and integer/rational reconstruction; no production analysis imports or future-performance claim.",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["development", "held"])
    args = parser.parse_args()
    result = verify(args.phase)
    (ROOT / "results" / (args.phase + "-VERIFICATION.json")).write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result))
