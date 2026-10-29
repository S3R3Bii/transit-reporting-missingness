"""Exact arithmetic for explicitly synthetic reporting gaps on a fixed snapshot."""

import csv
from fractions import Fraction as Q
import gzip
import io
from pathlib import Path


def load_counts(root):
    with gzip.open(
        Path(root) / "data/source/counts.csv.gz", "rt", newline=""
    ) as stream:
        result = {}
        for row in csv.DictReader(stream):
            key = (row["agency"], row["service"], int(row["year"]), int(row["month"]))
            if key in result:
                raise ValueError("Duplicate agency-service/month key")
            result[key] = None if row["upt"] == "" else int(row["upt"])
        return result


def baseline_roster(data):
    keys = sorted({key[:2] for key in data if key[2] == 2019})
    roster = []
    for key in keys:
        values = [data.get((*key, 2019, month)) for month in range(1, 13)]
        if all(value is not None for value in values) and sum(values) > 0:
            roster.append(key)
    return roster


def pair_cohort(data, roster, year):
    records, eligible = [], []
    for agency, service in roster:
        counts = {}
        for label, y in [("prior", year - 1), ("current", year)]:
            counts[label + "_absent"] = sum(
                (agency, service, y, m) not in data for m in range(1, 13)
            )
            counts[label + "_null"] = sum(
                (agency, service, y, m) in data and data[agency, service, y, m] is None
                for m in range(1, 13)
            )
        complete = not any(counts.values())
        records.append(
            dict(
                year=year,
                agency=agency,
                service=service,
                eligible=int(complete),
                **counts
            )
        )
        if complete:
            eligible.append((agency, service))
    return eligible, records


def mask_units(cohort, data, fraction, ranking):
    annual = {
        key: sum(data[(*key, 2019, month)] for month in range(1, 13)) for key in cohort
    }
    if ranking == "baseline_volume_desc":
        ordered = sorted(cohort, key=lambda key: (-annual[key], key))
    elif ranking == "baseline_volume_asc":
        ordered = sorted(cohort, key=lambda key: (annual[key], key))
    elif ranking == "identifier":
        ordered = sorted(cohort)
    else:
        raise ValueError("Unknown ranking")
    fraction = Q(fraction)
    count = (
        fraction.numerator * len(cohort) + fraction.denominator - 1
    ) // fraction.denominator
    return set(ordered[:count])


def growth(prior, current):
    return None if prior == 0 else Q(current) / prior - 1


def sign(value):
    return (
        "undefined"
        if value is None
        else "positive" if value > 0 else "negative" if value < 0 else "zero"
    )


def point_views(prior, current, prior_hidden, current_hidden):
    keys = set(prior)
    assert keys == set(current)
    n = len(keys)
    bp = sum(v for key, v in prior.items() if key not in prior_hidden)
    ac = sum(v for key, v in current.items() if key not in current_hidden)
    np, nc = n - len(prior_hidden), n - len(current_hidden)
    paired = keys - prior_hidden - current_hidden
    rescaled = None if not np or not nc else growth(Q(bp * n, np), Q(ac * n, nc))
    matched = growth(
        sum(prior[key] for key in paired), sum(current[key] for key in paired)
    )
    return dict(
        zero_fill=growth(bp, ac), count_rescaled=rescaled, matched_panel=matched
    )


def interval(prior_lower, prior_upper, current_lower, current_upper):
    assert 0 <= prior_lower <= prior_upper and 0 <= current_lower <= current_upper
    if prior_upper == 0:
        return None, None, "undefined_reference"
    lower = Q(current_lower, prior_upper) - 1
    if prior_lower == 0:
        return (
            lower,
            None if current_upper > 0 else Q(-1),
            "unbounded_upper" if current_upper > 0 else "finite",
        )
    return lower, Q(current_upper, prior_lower) - 1, "finite"


def bounds(prior, current, baseline, prior_hidden, current_hidden, gamma):
    pl = sum(v for key, v in prior.items() if key not in prior_hidden)
    cl = sum(v for key, v in current.items() if key not in current_hidden)
    pu = pl + gamma * sum(baseline[key] for key in prior_hidden)
    cu = cl + gamma * sum(baseline[key] for key in current_hidden)
    violations = sum(prior[key] > gamma * baseline[key] for key in prior_hidden)
    violations += sum(current[key] > gamma * baseline[key] for key in current_hidden)
    lower, upper, state = interval(pl, pu, cl, cu)
    return dict(
        prior_lower=pl,
        prior_upper=pu,
        current_lower=cl,
        current_upper=cu,
        lower=lower,
        upper=upper,
        state=state,
        violated_components=violations,
    )
