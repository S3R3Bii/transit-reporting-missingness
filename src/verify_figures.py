"""Independently compare actual plot values with checked CSVs and text contrast."""

import csv
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify():
    def read(name):
        with (ROOT / "results" / name).open(encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream))

    points = read("held-points.csv")
    bounds = read("held-bounds.csv")
    values = json.loads(
        (ROOT / "figures/ARTIST_VALUES.json").read_text(encoding="utf-8")
    )
    checks = 0

    def same(a, b):
        nonlocal checks
        assert abs(float(a) - float(b)) <= 1e-10, (a, b)
        checks += 1

    for year in [2023, 2024, 2025]:
        for view in ["truth", "zero_fill", "count_rescaled", "matched_panel"]:
            rows = sorted(
                [
                    r
                    for r in points
                    if int(r["year"]) == year
                    and r["fraction"] == "1/10"
                    and r["ranking"] == "baseline_volume_desc"
                    and r["masked_side"] == "prior"
                    and r["view"] == ("zero_fill" if view == "truth" else view)
                ],
                key=lambda r: int(r["month"]),
            )
            actual = values["growth"][str(year)][view]
            assert len(actual["x"]) == len(actual["y"]) == len(rows) == 12
            for i, row in enumerate(rows):
                same(actual["x"][i], row["month"])
                same(
                    actual["y"][i],
                    100 * Q(row["truth_growth" if view == "truth" else "growth"]),
                )
    matrices = {}
    for view in ["zero_fill", "count_rescaled", "matched_panel"]:
        matrix = []
        for i, rank in enumerate(
            ["baseline_volume_desc", "baseline_volume_asc", "identifier"]
        ):
            line = []
            for j, fraction in enumerate(["1/20", "1/10", "1/5"]):
                rows = [
                    r
                    for r in points
                    if r["view"] == view
                    and r["ranking"] == rank
                    and r["fraction"] == fraction
                    and r["masked_side"] == "prior"
                ]
                expected = sum(
                    abs((Q(r["growth"]) - Q(r["truth_growth"])) * 100) for r in rows
                ) / len(rows)
                same(values["errors"][view][i][j], expected)
                line.append(float(expected))
            matrix.append(line)
        matrices[view] = matrix
    for gamma in ["1", "2", "4"]:
        for i, side in enumerate(["prior", "current", "both"]):
            rows = [
                r for r in bounds if r["gamma"] == gamma and r["masked_side"] == side
            ]
            assert len(rows) == 324
            for key in ["truth_contained", "assumptions_valid"]:
                same(
                    values["bounds"][gamma][key][i],
                    Q(100 * sum(int(r[key]) for r in rows), len(rows)),
                )

    def light(rgb):
        linear = [
            c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb
        ]
        return sum(a * b for a, b in zip(linear, [0.2126, 0.7152, 0.0722]))

    assert len(values["annotations"]) == 27
    minimum = 100
    for annotation in values["annotations"]:
        assert annotation["text"] == format(
            matrices[annotation["view"]][annotation["row"]][annotation["column"]], ".2f"
        )
        a, b = light(annotation["foreground"]), light(annotation["background"])
        contrast = (max(a, b) + 0.05) / (min(a, b) + 0.05)
        assert contrast >= 4.5
        minimum = min(minimum, contrast)
    manifest = json.loads((ROOT / "figures/MANIFEST.json").read_text(encoding="utf-8"))
    assert len(manifest) == 9
    for name, digest in manifest.items():
        assert (
            hashlib.sha256((ROOT / "figures" / name).read_bytes()).hexdigest() == digest
        )
    return dict(
        status="PASS",
        actual_artist_values=checks,
        annotation_and_contrast_checks=27,
        minimum_annotation_contrast=minimum,
        export_hashes=9,
    )


if __name__ == "__main__":
    result = verify()
    (ROOT / "figures/VERIFICATION.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result))
