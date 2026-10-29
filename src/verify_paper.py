"""Independent display, finite-claim, approved-byte and bounded PDF-action checks."""

import csv
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from pypdf import PdfReader
from verify_summaries import verify as verify_summaries

ROOT = Path(__file__).resolve().parents[1]


def display(value, places=3):
    q = Q(value)
    with localcontext() as context:
        context.prec = 100
        result = (Decimal(q.numerator) / Decimal(q.denominator)).quantize(
            Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN
        )
        return format(result, ",." + str(places) + "f")


def verify():
    assert verify_summaries(ROOT)["status"] == "PASS"

    def read(name):
        with (ROOT / "results" / name).open(encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream))

    tex = (ROOT / "paper/main.tex").read_text(encoding="utf-8")
    md = (ROOT / "DECISION_SUMMARY.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    checks = 0

    def row(fields, markdown=True):
        nonlocal checks
        fields = list(map(str, fields))
        assert " & ".join(fields) + " " + chr(92) * 2 in tex, fields
        checks += len(fields)
        if markdown:
            assert "| " + " | ".join(fields) + " |" in md, fields
            checks += len(fields)

    names = {
        "zero_fill": "Zero fill",
        "count_rescaled": "Count rescaled",
        "matched_panel": "Matched panel",
    }
    ranks = {
        "baseline_volume_desc": "Largest baseline",
        "baseline_volume_asc": "Smallest baseline",
        "identifier": "Identifier",
    }
    sides = {"prior": "Prior", "current": "Current", "both": "Both"}
    primary = read("held-primary-summary.csv")
    setting = read("held-setting-summary.csv")
    bound = read("held-bound-summary.csv")
    for r in primary:
        row(
            [
                r["year"] if r["year"] != "ALL" else "Pooled",
                names[r["view"]],
                display(r["mae_pp"]),
                r["sign_errors"],
                r["false_growth"],
                r["missed_growth"],
            ]
        )
    for fraction in ["1/20", "1/10", "1/5"]:
        for rank in ranks:
            for side in sides:
                values = [
                    next(
                        r
                        for r in setting
                        if r["fraction"] == fraction
                        and r["ranking"] == rank
                        and r["masked_side"] == side
                        and r["view"] == view
                    )
                    for view in names
                ]
                row(
                    [
                        display(100 * Q(fraction), 0),
                        ranks[rank],
                        sides[side],
                        *[display(r["mae_pp"]) for r in values],
                    ]
                )
    for r in bound:
        row(
            [
                r["gamma"],
                sides[r["masked_side"]],
                r["n"],
                r["truth_contained"],
                r["assumptions_valid"],
                r["violated_components"],
            ]
        )
    source = json.loads(
        (ROOT / "data/source/VERIFICATION.json").read_text(encoding="utf-8")
    )
    for r in source["annual_source_quality"]:
        row(
            [r["year"], format(r["rows"], ","), r["explicit_null"], r["reported_zero"]],
            False,
        )
    assert source["source_rows"] == 38584
    assert sum(r["explicit_null"] for r in source["annual_source_quality"]) == 50
    assert sum(r["reported_zero"] for r in source["annual_source_quality"]) == 185
    checks += 3
    cohorts = read("held-cohorts.csv")
    for year in ["2023", "2024", "2025"]:
        values = [r for r in cohorts if r["year"] == year]
        eligible = sum(int(r["eligible"]) for r in values)
        row(
            [
                year,
                eligible,
                len(values) - eligible,
                *[
                    sum(int(r[key]) for r in values)
                    for key in [
                        "prior_absent",
                        "current_absent",
                        "prior_null",
                        "current_null",
                    ]
                ],
            ],
            False,
        )
    points = read("held-points.csv")

    def key(r):
        return tuple(
            r[k] for k in ["year", "month", "fraction", "ranking", "masked_side"]
        )

    zero = {key(r): r for r in points if r["view"] == "zero_fill"}
    matched = {key(r): r for r in points if r["view"] == "matched_panel"}
    assert (
        sum(Q(matched[k]["abs_error_pp"]) < Q(zero[k]["abs_error_pp"]) for k in zero)
        == 648
    )
    assert (
        sum(Q(matched[k]["abs_error_pp"]) == Q(zero[k]["abs_error_pp"]) for k in zero)
        == 324
    )
    checks += 2
    both = {key(r) for r in points if r["masked_side"] == "both"}
    for k in both:
        assert len({r["growth"] for r in points if key(r) == k}) == 1
        checks += 1
    for year in ["2023", "2024", "2025"]:
        r = next(
            r
            for r in points
            if r["year"] == year
            and r["month"] == "1"
            and r["fraction"] == "1/10"
            and r["ranking"] == "baseline_volume_desc"
            and r["masked_side"] == "prior"
        )
        assert r["hidden_units"] + "/" + r["units"] in tex
        assert display(100 * Q(r["hidden_baseline_volume_fraction"])) + "\\%" in tex
        checks += 2
    g2 = [r for r in bound if r["gamma"] == "2"]
    g4 = [r for r in bound if r["gamma"] == "4"]
    assert (
        sum(int(r["n"]) for r in g2)
        == sum(int(r["truth_contained"]) for r in g2)
        == 972
    )
    assert sum(int(r["assumptions_valid"]) for r in g2) == 502
    assert 972 - 502 == 470 and sum(int(r["assumptions_valid"]) for r in g4) == 546
    checks += 4
    p = {r["view"]: r for r in primary if r["year"] == "ALL"}
    assert (
        p["zero_fill"]["false_growth"] == "4"
        and p["matched_panel"]["missed_growth"] == "1"
    )
    checks += 2
    for view, expected in [
        ("zero_fill", "319.349"),
        ("count_rescaled", "276.125"),
        ("matched_panel", "1.289"),
    ]:
        assert display(p[view]["mae_pp"]) == expected
        for document in [tex, md, readme]:
            assert expected in document
        checks += 4
    for phrase in [
        "reporting gaps are synthetic",
        "concentrated-volume stress",
        "not passenger truth",
        "changes population",
        "not random samples",
        "not a prospective availability test",
        "not empirically tuned",
        "not confidence intervals",
        "not probabilistic coverage estimates",
        "cap violations block",
        "nonnegativity alone supplies no finite",
        "visible without blinding",
        "not peer reviewed",
        "Formal-publication projects, including Azure optimization, remain private",
        "344,274",
        "346,434",
    ]:
        if phrase == "344,274":
            assert "172,866" in tex and "171,408" in tex
        elif phrase == "not a prospective availability test":
            assert "rather than a prospective availability test" in tex
        elif phrase == "not empirically tuned":
            assert "not empirically tuned settings" in tex
        else:
            assert phrase.lower() in tex.lower(), phrase
        checks += 1
    scope = json.loads(
        (ROOT / "paper/PUBLICATION_SCOPE.json").read_text(encoding="utf-8")
    )
    assert (
        scope["scope"] == "independent-program-study"
        and scope["formal_submission_target"] is False
        and len(scope["public_files"]) == 5
    )
    checks += 3
    for name, digest in scope["public_files"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
        checks += 1
    doc = PdfReader(ROOT / "paper/manuscript.pdf")
    assert len(doc.pages) == 7
    checks += 1
    text = re.sub(
        r"\s+",
        " ",
        unicodedata.normalize(
            "NFKC", " ".join(page.extract_text() for page in doc.pages)
        ),
    )
    for phrase in [
        "Decision brief",
        "319.349",
        "276.125",
        "1.289",
        "346,434",
        "470",
        "not peer reviewed",
        "Every declared gap setting",
        "972",
        "502",
        "546",
    ]:
        assert phrase.lower() in text.lower(), phrase
        checks += 1
    for command in [
        "python -m pip install -r requirements.txt",
        "python -m unittest discover -s tests -v",
        "python src/check_reproduction.py",
        "python src/verify_summaries.py",
        "python src/verify_figures.py",
        "python src/verify_paper.py",
        "python src/verify_public_package.py",
    ]:
        assert command in text, command
        checks += 1
    forbidden = [
        "/JavaScript",
        "/JS",
        "/Launch",
        "/EmbeddedFiles",
        "/RichMedia",
        "/AcroForm",
        "/AA",
    ]
    pdfs = [
        ROOT / "paper/manuscript.pdf",
        *sorted((ROOT / "paper/images").glob("*.pdf")),
    ]
    assert len(pdfs) == 4
    for path in pdfs:
        pdf = PdfReader(path)
        catalog = pdf.trailer["/Root"]
        assert not any(k in catalog for k in forbidden)
        assert "/EmbeddedFiles" not in catalog.get("/Names", {})
        action = catalog.get("/OpenAction")
        if hasattr(action, "get"):
            assert action.get("/S") not in ["/JavaScript", "/Launch"]
        for page in pdf.pages:
            assert not any(k in page for k in forbidden)
            for annotation in page.get("/Annots", []):
                item = annotation.get_object()
                assert not any(k in item for k in ["/AA", "/RichMedia"])
                if "/A" in item:
                    assert item["/A"].get("/S") == "/URI"
        checks += 1
    return dict(
        status="PASS",
        independent_paper_checks=checks,
        displayed_primary_rows=12,
        displayed_setting_rows=27,
        displayed_bound_rows=9,
        pdf_pages=7,
        pdf_active_content_checks=4,
        scope="Independent summary verification, displayed cells/claims/hashes and bounded PDF actions; rights and rendered readability reviewed separately.",
    )


if __name__ == "__main__":
    result = verify()
    (ROOT / "paper/VERIFICATION.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result))
