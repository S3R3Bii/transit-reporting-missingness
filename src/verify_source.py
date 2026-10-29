"""Independently reconcile selected JSON facts, CSV projection and server controls."""

import csv
from decimal import Decimal
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3

ROOT = Path(__file__).resolve().parents[1]


def integer(text):
    value = Decimal(text)
    assert value.is_finite() and value == value.to_integral_value() and value >= 0
    return int(value)


def verify(root=ROOT):
    dest = Path(root) / "data/source"
    manifest = json.loads((dest / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["metadata"]["id"] == "5ti2-5uiv" and manifest["metadata"]["license"] == "PUBLIC_DOMAIN"
    con = sqlite3.connect(":memory:")
    for table in ["original", "projected"]:
        con.execute(f"CREATE TABLE {table}(agency TEXT,service TEXT,year INT,month INT,upt INT,PRIMARY KEY(agency,service,year,month))")
    controls = {}
    scalar_checks = 0
    for request in manifest["requests"]:
        packed = (dest / request["name"]).read_bytes()
        assert hashlib.sha256(packed).hexdigest() == request["compressed_sha256"]
        data = gzip.decompress(packed)
        assert hashlib.sha256(data).hexdigest() == request["response_sha256"]
        records = json.loads(data)
        if not request["name"].startswith("rows-"):
            controls[request["name"]] = records
            continue
        for record in records:
            assert set(record) <= {"_5_digit_ntd_id", "type_of_service", "year", "month_year", "ridership"}
            match = re.fullmatch(r"(\d{4})-(\d{2})-01T00:00:00(?:\.000)?", record["month_year"])
            assert match
            year, month = map(int, match.groups())
            assert year == integer(record["year"]) and 2019 <= year <= 2025 and 1 <= month <= 12
            agency, service = record["_5_digit_ntd_id"], record["type_of_service"]
            assert re.fullmatch(r"\d{5}", agency) and service
            count = None if record.get("ridership") is None else integer(record["ridership"])
            con.execute("INSERT INTO original VALUES(?,?,?,?,?)", (agency, service, year, month, count))
    packed = (dest / "counts.csv.gz").read_bytes()
    assert hashlib.sha256(packed).hexdigest() == manifest["projection"]["sha256"]
    for row in csv.DictReader(io.StringIO(gzip.decompress(packed).decode())):
        con.execute("INSERT INTO projected VALUES(?,?,?,?,?)", (row["agency"], row["service"], int(row["year"]), int(row["month"]), None if row["upt"] == "" else integer(row["upt"])))
        scalar_checks += 5
    assert not con.execute("SELECT * FROM original EXCEPT SELECT * FROM projected").fetchall()
    assert not con.execute("SELECT * FROM projected EXCEPT SELECT * FROM original").fetchall()
    size = con.execute("SELECT COUNT(*) FROM original").fetchone()[0]
    assert size == manifest["projection"]["rows"]
    control_checks = 0
    for name, fields in [("monthly-controls.json.gz", ["year", "month"]), ("agency-year-controls.json.gz", ["agency", "service", "year"])]:
        group = ",".join(fields)
        actual = {tuple(row[:len(fields)]): tuple(row[len(fields):]) for row in con.execute(f"SELECT {group},COUNT(*),COUNT(upt),SUM(upt) FROM projected GROUP BY {group}")}
        expected = {}
        for row in controls[name]:
            if fields == ["year", "month"]:
                key = (integer(row["year"]), int(row["month_year"][5:7]))
            else:
                key = (row["_5_digit_ntd_id"], row["type_of_service"], integer(row["year"]))
            assert key not in expected
            expected[key] = (integer(row["rows"]), integer(row["nonnull"]), None if row.get("upt") is None else integer(row["upt"]))
        assert actual == expected, name
        control_checks += len(expected) * 3
    quality = [dict(year=y, rows=n, nonnull=known, explicit_null=n-known, reported_zero=zero, published_upt=total) for y,n,known,zero,total in con.execute("SELECT year,COUNT(*),COUNT(upt),SUM(CASE WHEN upt=0 THEN 1 ELSE 0 END),SUM(upt) FROM projected GROUP BY year ORDER BY year")]
    return dict(status="PASS", source_rows=size, independent_projection_scalar_checks=scalar_checks, independent_server_control_checks=control_checks, annual_source_quality=quality,
                limits="Controls reconcile the captured publication; individual ridership accuracy, actual service eligibility, provenance flags and original historical vintages remain unverified.")


if __name__ == "__main__":
    result = verify()
    (ROOT / "data/source/VERIFICATION.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
