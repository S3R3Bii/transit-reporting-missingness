"""Summarize the full fixed comparison grid without selecting a method or case."""

import csv
from fractions import Fraction as Q
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name, root=ROOT):
    with (Path(root) / "results" / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def summarize(phase, root=ROOT):
    points = read(phase + "-points.csv", root)
    bounds = read(phase + "-bounds.csv", root)
    setting = []
    primary = []
    intervals = []
    configurations = sorted(
        {(r["fraction"], r["ranking"], r["masked_side"], r["view"]) for r in points}
    )

    def summary(rows):
        values = [r for r in rows if r["abs_error_pp"] != ""]
        n = len(values)
        return dict(
            n=n,
            undefined=len(rows) - n,
            mae_pp="" if not n else str(sum(Q(r["abs_error_pp"]) for r in values) / n),
            mse_pp=(
                "" if not n else str(sum(Q(r["squared_error_pp"]) for r in values) / n)
            ),
            sign_errors=sum(int(r["sign_error"]) for r in values),
            false_growth=sum(int(r["false_growth"]) for r in values),
            missed_growth=sum(int(r["missed_growth"]) for r in values),
        )

    for fraction, ranking, side, view in configurations:
        rows = [
            r
            for r in points
            if (r["fraction"], r["ranking"], r["masked_side"], r["view"])
            == (fraction, ranking, side, view)
        ]
        setting.append(
            dict(
                fraction=fraction,
                ranking=ranking,
                masked_side=side,
                view=view,
                **summary(rows)
            )
        )
    for year in sorted({r["year"] for r in points}) + ["ALL"]:
        for view in ["zero_fill", "count_rescaled", "matched_panel"]:
            rows = [
                r
                for r in points
                if r["fraction"] == "1/10"
                and r["ranking"] == "baseline_volume_desc"
                and r["masked_side"] == "prior"
                and r["view"] == view
                and (year == "ALL" or r["year"] == year)
            ]
            primary.append(dict(year=year, view=view, **summary(rows)))
    for gamma in ["1", "2", "4"]:
        for side in ["prior", "current", "both"]:
            rows = [
                r for r in bounds if r["gamma"] == gamma and r["masked_side"] == side
            ]
            intervals.append(
                dict(
                    gamma=gamma,
                    masked_side=side,
                    n=len(rows),
                    finite=sum(r["state"] == "finite" for r in rows),
                    assumptions_valid=sum(int(r["assumptions_valid"]) for r in rows),
                    truth_contained=sum(int(r["truth_contained"]) for r in rows),
                    violated_components=sum(
                        int(r["violated_components"]) for r in rows
                    ),
                    conditional_positive_lowers=sum(
                        int(r["conditional_positive_lower"]) for r in rows
                    ),
                    assumption_supported_positive=sum(
                        int(r["assumption_supported_positive_lower"]) for r in rows
                    ),
                )
            )
    return {
        "setting-summary": setting,
        "primary-summary": primary,
        "bound-summary": intervals,
    }


if __name__ == "__main__":
    for phase in ["development", "held"]:
        for name, records in summarize(phase).items():
            with (ROOT / "results" / (phase + "-" + name + ".csv")).open(
                "w", encoding="utf-8", newline=""
            ) as stream:
                writer = csv.DictWriter(
                    stream, fieldnames=list(records[0]), lineterminator="\n"
                )
                writer.writeheader()
                writer.writerows(records)
    print("All fixed point/bound and primary summaries exported; no selection")
