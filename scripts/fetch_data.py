"""Pull raw public data for the Bank Operations Intelligence Agent into data/raw/.

Usage:
    python scripts/fetch_data.py --smoke                 # tiny pull from every source (~1 min)
    python scripts/fetch_data.py --source fdic fred      # full pull of selected sources
    python scripts/fetch_data.py --source cfpb --cfpb-bulk   # ~350 MB bulk complaints file

Every file written is recorded in data/raw/_manifest.json (url, pulled_at, rows, sha256).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CONFIG = yaml.safe_load((ROOT / "config" / "institutions.yaml").read_text())
# dbt seeds are the single source of truth for banks and FRED series.
SEEDS = ROOT / "dbt" / "seeds"
BANKS = {r["bank_id"]: r for r in csv.DictReader((SEEDS / "bank_dim.csv").open())}
FOCAL = next(r for r in BANKS.values() if r["is_focal"] == "true")
FRED_SERIES = [r["series_id"] for r in csv.DictReader((SEEDS / "fred_series_dim.csv").open())]

BROWSER_UA = {"User-Agent": "Mozilla/5.0 (bank-ops-ai-agent research)"}
# SEC requires a descriptive UA with contact info — set SEC_CONTACT_EMAIL in your env / .env.
SEC_CONTACT = os.getenv("SEC_CONTACT_EMAIL", "contact@example.com")
SEC_UA = {"User-Agent": f"bank-ops-ai-agent research {SEC_CONTACT}"}

CFPB_API = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"
CFPB_BULK = "https://files.consumerfinance.gov/ccdb/complaints.csv.zip"
FDIC_API = "https://api.fdic.gov/banks/financials"
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"
ECFR_TITLES = "https://www.ecfr.gov/api/versioner/v1/titles.json"
ECFR_PART = "https://www.ecfr.gov/api/versioner/v1/full/{date}/title-12.xml?part={part}"

_manifest: list[dict] = []


def _write(path: Path, data: bytes, url: str, rows: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    _manifest.append(
        {
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "url": url,
            "pulled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "rows": rows,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    )
    print(f"  wrote {path.relative_to(ROOT)}  rows={rows}  bytes={len(data):,}")


def _get(url: str, headers: dict | None = None, **kw) -> requests.Response:
    for attempt in range(3):
        r = requests.get(url, headers=headers or BROWSER_UA, timeout=120, **kw)
        if r.status_code == 200:
            return r
        time.sleep(2**attempt)
    r.raise_for_status()
    return r


def _months(start: date, end: date) -> list[tuple[date, date]]:
    """(first_day, last_day) per month. CFPB date_received_max is INCLUSIVE."""
    out, cur = [], date(start.year, start.month, 1)
    while cur <= end:
        nxt = date(cur.year + (cur.month == 12), cur.month % 12 + 1, 1)
        out.append((cur, nxt - timedelta(days=1)))
        cur = nxt
    return out


# --------------------------------------------------------------------------- CFPB
def fetch_cfpb_monthly_counts(smoke: bool) -> None:
    """Monthly complaint counts per peer bank via the API (cheap; no row download)."""
    print("CFPB monthly counts")
    today = date.today()
    start = today - timedelta(days=62) if smoke else date.fromisoformat(CONFIG["history_start"])
    rows = []
    for bank_id, b in BANKS.items():
        for m_start, m_end in _months(start, today):
            url = (
                f"{CFPB_API}?size=0&no_aggs=true&company={quote(b['cfpb_company'])}"
                f"&date_received_min={m_start}&date_received_max={m_end}"
            )
            n = _get(url).json()["hits"]["total"]["value"]
            rows.append({"bank_id": bank_id, "month": m_start.isoformat(), "complaints": n})
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["bank_id", "month", "complaints"])
    w.writeheader()
    w.writerows(rows)
    _write(RAW / "cfpb" / "monthly_counts.csv", buf.getvalue().encode(), CFPB_API, len(rows))


def fetch_cfpb_sample(smoke: bool) -> None:
    """Row-level sample from the API for the focal bank (schema exploration)."""
    print("CFPB row sample")
    url = (
        f"{CFPB_API}?size={25 if smoke else 1000}&no_aggs=true"
        f"&company={quote(FOCAL['cfpb_company'])}&sort=created_date_desc"
    )
    hits = _get(url).json()["hits"]["hits"]
    data = json.dumps([h["_source"] for h in hits], indent=1).encode()
    _write(RAW / "cfpb" / "sample_focal.json", data, url, len(hits))


def fetch_cfpb_bulk() -> None:
    print("CFPB bulk (~350 MB) — this takes a while")
    r = _get(CFPB_BULK, stream=True)
    path = RAW / "cfpb" / "complaints.csv.zip"
    path.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    with path.open("wb") as f:
        for chunk in r.iter_content(1 << 20):
            f.write(chunk)
            h.update(chunk)
    _manifest.append(
        {
            "path": "data/raw/cfpb/complaints.csv.zip",
            "url": CFPB_BULK,
            "pulled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "rows": None,
            "bytes": path.stat().st_size,
            "sha256": h.hexdigest(),
        }
    )
    print(f"  wrote {path.relative_to(ROOT)}  bytes={path.stat().st_size:,}")


# --------------------------------------------------------------------------- FDIC
def fetch_fdic(smoke: bool) -> None:
    print("FDIC financials")
    certs = " OR ".join(b["fdic_cert"] for b in BANKS.values())
    fields = ",".join(["CERT"] + CONFIG["fdic_fields"])
    url = (
        f"{FDIC_API}?filters=CERT:({quote(certs)})&fields={fields}"
        f"&sort_by=REPDTE&sort_order=DESC&limit={20 if smoke else 10000}"
    )
    recs = [d["data"] for d in _get(url).json()["data"]]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["CERT"] + CONFIG["fdic_fields"], extrasaction="ignore")
    w.writeheader()
    w.writerows(recs)
    _write(RAW / "fdic" / "financials.csv", buf.getvalue().encode(), url, len(recs))


# --------------------------------------------------------------------------- FRED
def fetch_fred(smoke: bool) -> None:
    print("FRED series")
    series = FRED_SERIES[: 2 if smoke else None]
    for s in series:
        url = FRED_CSV.format(s)
        # FRED stalls on browser-like UAs; the default library UA works.
        body = _get(url, {"User-Agent": "python-requests"}).content
        _write(RAW / "fred" / f"{s}.csv", body, url, body.count(b"\n") - 1)


# --------------------------------------------------------------------------- SEC EDGAR
def fetch_edgar(smoke: bool) -> None:
    print("SEC EDGAR filings index + latest 10-K")
    banks = list(BANKS.items())[: 1 if smoke else None]
    for bank_id, b in banks:
        cik = b["sec_cik"]
        idx_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        recent = _get(idx_url, SEC_UA).json()["filings"]["recent"]
        filings = [
            {"form": f, "filingDate": d, "accession": a, "doc": p}
            for f, d, a, p in zip(
                recent["form"],
                recent["filingDate"],
                recent["accessionNumber"],
                recent["primaryDocument"],
                strict=True,
            )
            if f in ("10-K", "10-Q")
        ][:5]
        _write(
            RAW / "edgar" / bank_id / "filings_index.json",
            json.dumps(filings, indent=1).encode(),
            idx_url,
            len(filings),
        )
        if smoke:
            continue
        for f in filings:
            doc_url = (
                f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                f"{f['accession'].replace('-', '')}/{f['doc']}"
            )
            _write(
                RAW / "edgar" / bank_id / f"{f['form']}_{f['filingDate']}.htm",
                _get(doc_url, SEC_UA).content,
                doc_url,
            )
            time.sleep(0.2)  # SEC fair-access: stay well under 10 req/s


# --------------------------------------------------------------------------- eCFR
def fetch_ecfr(smoke: bool) -> None:
    print("eCFR regulations")
    issue = next(
        t["latest_issue_date"] for t in _get(ECFR_TITLES).json()["titles"] if t["number"] == 12
    )
    parts = list(CONFIG["regulations"])[: 1 if smoke else None]
    for part in parts:
        url = ECFR_PART.format(date=issue, part=part)
        # eCFR returns 406 unless the client accepts a compressed response.
        body = _get(url, {**BROWSER_UA, "Accept-Encoding": "gzip"}).content
        _write(RAW / "ecfr" / f"12cfr{part}.xml", body, url)


SOURCES = {
    "cfpb": lambda s: (fetch_cfpb_monthly_counts(s), fetch_cfpb_sample(s)),
    "fdic": fetch_fdic,
    "fred": fetch_fred,
    "edgar": fetch_edgar,
    "ecfr": fetch_ecfr,
}


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--source", nargs="+", choices=list(SOURCES), default=list(SOURCES))
    ap.add_argument("--smoke", action="store_true", help="tiny pull from each source")
    ap.add_argument(
        "--cfpb-bulk", action="store_true", help="also download the full CFPB CSV (~350 MB)"
    )
    args = ap.parse_args()

    failed = []
    for name in args.source:
        try:
            SOURCES[name](args.smoke)
        except Exception as e:  # keep going so one flaky source doesn't sink the run
            print(f"  !! {name} failed: {type(e).__name__}: {e}")
            failed.append(name)
    if args.cfpb_bulk:
        fetch_cfpb_bulk()

    manifest_path = RAW / "_manifest.json"
    existing = json.loads(manifest_path.read_text()) if manifest_path.exists() else []
    by_path = {m["path"]: m for m in existing} | {m["path"]: m for m in _manifest}
    manifest_path.write_text(json.dumps(list(by_path.values()), indent=1))
    print(f"manifest: {manifest_path.relative_to(ROOT)} ({len(by_path)} files)")
    if failed:
        raise SystemExit(f"failed sources: {', '.join(failed)}")


if __name__ == "__main__":
    main()
