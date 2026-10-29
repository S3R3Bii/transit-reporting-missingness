"""Export every fixed gap, point view and conditional bound without fitting."""

import argparse
import csv
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import time

from model import (
    baseline_roster,
    bounds,
    growth,
    load_counts,
    mask_units,
    pair_cohort,
    point_views,
    sign,
)

ROOT = Path(__file__).resolve().parents[1]


def write_csv(path, records):
    assert records
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=list(records[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(records)


def exact(value):
    return "" if value is None else str(value)


def run(phase, root=ROOT):
    started = time.perf_counter()
    root = Path(root)
    config = json.loads((root / "protocol.json").read_text(encoding="utf-8"))
    data = load_counts(root)
    roster = baseline_roster(data)
    years = (
        config["development_years"] if phase == "development" else config["held_years"]
    )
    cohorts, points, intervals, masks = [], [], [], []
    for year in years:
        cohort, exclusions = pair_cohort(data, roster, year)
        assert len(cohort) > 0
        cohorts.extend(exclusions)
        baseline_volume = sum(
            data[(*key, 2019, m)] for key in cohort for m in range(1, 13)
        )
        for fraction in config["mask_fractions"]:
            for ranking in config["rankings"]:
                hidden = mask_units(cohort, data, fraction, ranking)
                hidden_volume = sum(
                    data[(*key, 2019, m)] for key in hidden for m in range(1, 13)
                )
                for side in config["masked_sides"]:
                    ph = hidden if side in ["prior", "both"] else set()
                    ch = hidden if side in ["current", "both"] else set()
                    for key in sorted(hidden):
                        masks.append(
                            dict(
                                year=year,
                                fraction=fraction,
                                ranking=ranking,
                                masked_side=side,
                                agency=key[0],
                                service=key[1],
                            )
                        )
                    for month in range(1, 13):
                        prior = {key: data[(*key, year - 1, month)] for key in cohort}
                        current = {key: data[(*key, year, month)] for key in cohort}
                        baseline = {key: data[(*key, 2019, month)] for key in cohort}
                        truth = growth(sum(prior.values()), sum(current.values()))
                        common = dict(
                            year=year,
                            month=month,
                            fraction=fraction,
                            ranking=ranking,
                            masked_side=side,
                            units=len(cohort),
                            hidden_units=len(hidden),
                            hidden_baseline_volume_fraction=exact(
                                Q(hidden_volume, baseline_volume)
                            ),
                            truth_prior=sum(prior.values()),
                            truth_current=sum(current.values()),
                            truth_growth=exact(truth),
                            truth_sign=sign(truth),
                        )
                        for view, estimate in point_views(
                            prior, current, ph, ch
                        ).items():
                            error = (
                                None
                                if estimate is None or truth is None
                                else estimate - truth
                            )
                            points.append(
                                dict(
                                    **common,
                                    view=view,
                                    growth=exact(estimate),
                                    growth_sign=sign(estimate),
                                    error_pp=exact(
                                        None if error is None else 100 * error
                                    ),
                                    abs_error_pp=exact(
                                        None if error is None else 100 * abs(error)
                                    ),
                                    squared_error_pp=exact(
                                        None if error is None else 10000 * error * error
                                    ),
                                    sign_error=(
                                        ""
                                        if error is None
                                        else int(sign(estimate) != sign(truth))
                                    ),
                                    false_growth=(
                                        ""
                                        if error is None
                                        else int(estimate > 0 and truth <= 0)
                                    ),
                                    missed_growth=(
                                        ""
                                        if error is None
                                        else int(estimate <= 0 and truth > 0)
                                    )
                                )
                            )
                        for gamma in config["bound_multipliers"]:
                            bound = bounds(prior, current, baseline, ph, ch, int(gamma))
                            contains = (
                                None
                                if truth is None
                                or bound["state"] == "undefined_reference"
                                else (
                                    truth >= bound["lower"]
                                    and (
                                        bound["upper"] is None
                                        or truth <= bound["upper"]
                                    )
                                )
                            )
                            intervals.append(
                                dict(
                                    **common,
                                    gamma=gamma,
                                    **{
                                        key: (
                                            exact(value)
                                            if key
                                            not in ["state", "violated_components"]
                                            else value
                                        )
                                        for key, value in bound.items()
                                    },
                                    width=exact(
                                        None
                                        if bound["lower"] is None
                                        or bound["upper"] is None
                                        else bound["upper"] - bound["lower"]
                                    ),
                                    truth_contained=(
                                        "" if contains is None else int(contains)
                                    ),
                                    assumptions_valid=int(
                                        bound["violated_components"] == 0
                                    ),
                                    conditional_positive_lower=int(
                                        bound["state"] != "undefined_reference"
                                        and bound["lower"] > 0
                                    ),
                                    assumption_supported_positive_lower=int(
                                        bound["state"] != "undefined_reference"
                                        and bound["lower"] > 0
                                        and bound["violated_components"] == 0
                                    )
                                )
                            )
    output = root / "results"
    output.mkdir(exist_ok=True)
    for label, rows in [
        ("cohorts", cohorts),
        ("masks", masks),
        ("points", points),
        ("bounds", intervals),
    ]:
        write_csv(output / (phase + "-" + label + ".csv"), rows)
    execution = dict(
        phase=phase,
        elapsed_seconds=time.perf_counter() - started,
        baseline_roster_units=len(roster),
        cohort_unit_year_pairs=sum(row["eligible"] for row in cohorts),
        point_rows=len(points),
        bound_rows=len(intervals),
        mask_memberships=len(masks),
        scope="Fixed retrospective published-count benchmark with synthetic gaps; no fitting or empirical missingness mechanism claim.",
    )
    (output / (phase + "-execution.json")).write_text(
        json.dumps(execution, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(execution))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["development", "held"])
    args = parser.parse_args()
    run(args.phase)
