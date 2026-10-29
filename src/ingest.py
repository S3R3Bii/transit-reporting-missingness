"""Capture only protocol-approved monthly service facts and independent controls."""

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal
import gzip
import hashlib
import io
import json
from pathlib import Path
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VIEW = "https://data.transportation.gov/api/views/5ti2-5uiv.json"
API = "https://data.transportation.gov/resource/5ti2-5uiv.json"
FIELDS = ["_5_digit_ntd_id", "type_of_service", "year", "month_year", "ridership"]
WHERE = "mode='MB' AND year between 2019 and 2025"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ResearchPortfolio-source-capture/1.0"})
    with urllib.request.urlopen(req, timeout=120) as response:
        return response.read()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical_metadata(data):
    value = json.loads(data)
    return dict(id=value["id"], name=value["name"], license=value.get("licenseId"),
                rowsUpdatedAt=value["rowsUpdatedAt"], viewLastModified=value["viewLastModified"],
                columns=[dict(field=c["fieldName"], type=c["dataTypeName"])
                         for c in value["columns"] if c["fieldName"] in FIELDS])


def source_row(row):
    assert set(row) <= set(FIELDS), "Unexpected source field"
    agency, service = row["_5_digit_ntd_id"], row["type_of_service"]
    assert agency.isdigit() and len(agency) == 5 and service, "Invalid service key"
    year = Decimal(row["year"])
    assert year == int(year) and 2019 <= int(year) <= 2025
    date = datetime.fromisoformat(row["month_year"])
    assert date.year == int(year) and date.day == 1 and date.hour == date.minute == date.second == 0
    count = row.get("ridership")
    if count is not None:
        count = Decimal(count)
        assert count.is_finite() and count >= 0 and count == int(count), "Invalid UPT"
        count = int(count)
    return [agency, service, int(year), date.month, "" if count is None else count]


def capture(private_dir):
    private_dir = Path(private_dir)
    private_dir.mkdir(parents=True, exist_ok=False)
    dest = ROOT / "data/source"
    before = fetch(VIEW)
    (private_dir / "metadata-before.json").write_bytes(before)
    metadata = canonical_metadata(before)
    assert metadata["license"] == "PUBLIC_DOMAIN"
    requests, rows = [], []
    seen = set()

    def query(name, params):
        url = API + "?" + urllib.parse.urlencode(params)
        data = fetch(url)
        (private_dir / name).write_bytes(data)
        public_name = name + ".gz"
        packed = gzip.compress(data, mtime=0)
        (dest / public_name).write_bytes(packed)
        requests.append(dict(name=public_name, url=url, response_sha256=digest(data),
                             compressed_sha256=digest(packed), bytes=len(data)))
        return json.loads(data)

    for page in range(16):
        values = query(f"rows-{page:03d}.json", {"$select": ",".join(FIELDS), "$where": WHERE,
                       "$order": "_5_digit_ntd_id,type_of_service,year,month_year", "$limit": 50000, "$offset": page * 50000})
        for value in values:
            row = source_row(value)
            assert tuple(row[:4]) not in seen, "Duplicate full source key"
            seen.add(tuple(row[:4])); rows.append(row)
        if len(values) < 50000:
            break
    else:
        raise RuntimeError("Bounded page budget exhausted")
    for name, group in [("monthly", "year,month_year"), ("agency-year", "_5_digit_ntd_id,type_of_service,year")]:
        query(name + "-controls.json", {"$select": group + ",count(*) as rows,count(ridership) as nonnull,sum(ridership) as upt",
              "$where": WHERE, "$group": group, "$order": group, "$limit": 50000})
    after = fetch(VIEW)
    (private_dir / "metadata-after.json").write_bytes(after)
    assert canonical_metadata(after) == metadata, "Source revision changed during capture"
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["agency", "service", "year", "month", "upt"])
    writer.writerows(sorted(rows, key=lambda r: r[:4]))
    data = gzip.compress(buffer.getvalue().encode(), mtime=0)
    (dest / "counts.csv.gz").write_bytes(data)
    manifest = dict(retrieved_utc=datetime.now(timezone.utc).isoformat(), metadata=metadata,
                    metadata_before_sha256=digest(before), metadata_after_sha256=digest(after), requests=requests,
                    projection=dict(path="counts.csv.gz", sha256=digest(data), rows=len(rows)),
                    scope="Only protocol-selected public federal agency-service/month UPT facts. No safety, passenger-level or contact fields.")
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(state="CAPTURE_COMPLETE_CHECKS_PENDING", source_rows=len(rows), pages=page + 1,
                         projection_sha256=digest(data), source_revision=metadata["rowsUpdatedAt"])))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("private_dir")
    capture(parser.parse_args().private_dir)
