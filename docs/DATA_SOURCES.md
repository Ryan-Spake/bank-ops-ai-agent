# Data Sources: Field-Level Reference

All endpoints were tested live on 2026-10-08. `scripts/fetch_data.py` implements each one.

---

## 1. CFPB Consumer Complaint Database (core operational-volume signal)

- **Docs:** https://www.consumerfinance.gov/data-research/consumer-complaints/
- **API:** `https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/`
  - Example: `?company=JPMORGAN%20CHASE%20%26%20CO.&date_received_min=2025-01-01&size=0&no_aggs=true` returns the total count
  - `size=0` without `no_aggs` returns aggregations by `product, issue, timely, company_response, submitted_via, company, state, tags`
  - Send a browser-like `User-Agent`
- **Bulk:** `https://files.consumerfinance.gov/ccdb/complaints.csv.zip` (about 352 MB zipped, refreshed daily, about 18.3M rows)
- **License:** CC0 (public domain)

| Column (bulk CSV) | API field | Use |
|---|---|---|
| Date received | `date_received` | time axis |
| Product / Sub-product | `product`, `sub_product` | driver dimension |
| Issue / Sub-issue | `issue`, `sub_issue` | driver dimension |
| Consumer complaint narrative | `complaint_what_happened` | RAG / representative quotes (opt-in, PII-scrubbed) |
| Company public response | `company_public_response` | |
| Company | `company` | join key → `dbt/seeds/bank_dim.csv` |
| State, ZIP code | `state`, `zip_code` | geo driver |
| Tags | `tags` | "Older American", "Servicemember" segments |
| Submitted via | `submitted_via` | channel driver (Web, Phone, Referral…) |
| Date sent to company | `date_sent_to_company` | lag analysis |
| Company response to consumer | `company_response` | outcome mix |
| Timely response? | `timely` | compliance KPI |
| Complaint ID | `complaint_id` | primary key |

**Peer volumes since 2025-01-01 (checked live):** JPM 44,593 · BAC 37,954 · WFC 36,959 · Citi 37,884 · COF 60,723

**Quirks**
- Publication lag: the most recent 30–60 days are incomplete. Always compute `complete_through`.
- Narratives appear only with consumer consent, about 60 days after receipt.
- Product/issue taxonomy was revised (2017, 2023), so build a mapping table.
- The `company` value for parent companies vs. bank subsidiaries varies. Verify with `/search/api/v1/_suggest_company?text=...`.

---

## 2. FDIC BankFind Suite (bank financials)

- **Docs:** https://api.fdic.gov/banks/docs/
- **Financials:** `https://api.fdic.gov/banks/financials?filters=CERT:628&fields=...&sort_by=REPDTE&sort_order=DESC&limit=200`
- **Institutions:** `https://api.fdic.gov/banks/institutions?filters=CERT:628`
- **Failures** (optional context): `https://api.fdic.gov/banks/failures`
- No API key. **Dollar amounts are in $ thousands.**

| Field | Meaning |
|---|---|
| REPDTE | Report date (YYYYMMDD, quarter-end) |
| ASSET / DEP / LNLSNET | Total assets / deposits / net loans & leases |
| NETINC | Net income (YTD) |
| ROA / ROE / NIMY | Return on assets / equity / net interest margin (%) |
| EEFFR | Efficiency ratio (%): an operating-cost KPI |
| NTLNLSR | Net charge-offs / loans (%) |
| NCLNLSR | Noncurrent loans / loans (%) |
| ELNATR | Provision for loan & lease losses |
| NONII / NONIX | Non-interest income / expense |

Example (JPM, 2026-06-30): ASSET 4,091,315,000 → $4.09T; EEFFR 54.4%; ROE 18.55%.
Note that `NETINC`, `NONII`, and `NONIX` are **year-to-date**. Difference consecutive quarters to get quarterly flows.

---

## 3. FRED (macro context)

- CSV endpoint (no key): `https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES>`
- Series: see `dbt/seeds/fred_series_dim.csv`. Mixed frequencies (W/M/Q), so resample to monthly in the gold layer.
- For heavier use, get a free API key: https://fred.stlouisfed.org/docs/api/api_key.html

---

## 4. SEC EDGAR (filings for RAG and XBRL facts)

- **Requires** a descriptive `User-Agent` with contact email (SEC fair-access policy, max 10 req/s).
- Filing index: `https://data.sec.gov/submissions/CIK##########.json`
- XBRL concept: `https://data.sec.gov/api/xbrl/companyconcept/CIK##########/us-gaap/NoninterestExpense.json`
- Document URL: `https://www.sec.gov/Archives/edgar/data/<cik_no_zeros>/<accession_no_dashes>/<primaryDocument>`
- RAG targets: 10-K Item 1A (Risk Factors), Item 7 (MD&A), and the operational-risk sections.

---

## 5. Regulatory corpus (RAG)

| Doc | Source |
|---|---|
| Reg E, 12 CFR 1005 | `https://www.ecfr.gov/api/versioner/v1/full/<date>/title-12.xml?part=1005` (**must send `Accept-Encoding: gzip`**; get `<date>` from `/api/versioner/v1/titles.json`) |
| Reg Z, 12 CFR 1026 | same, `part=1026` (large) |
| Reg DD, 12 CFR 1030 | same, `part=1030` |
| CFPB Supervision & Examination Manual | https://www.consumerfinance.gov/compliance/supervision-examinations/ (PDF modules) |
| FDIC Risk Management Manual | https://www.fdic.gov/risk-management-manual-examination-policies |
| Fed SR 11-7 (model risk) | https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm (for `docs/MODEL_RISK.md`) |

---

## 6. Synthetic internal data (generated, Step 1)

| Table | Grain | Driven by | Injected anomalies |
|---|---|---|---|
| `call_center_contacts` | day × reason × channel | CFPB volume × multiplier + weekday seasonality | outage spike |
| `card_disputes` | day × reason_code × product × state | card complaint volume + FRED DRCCLACBS | outage spike, TX fraud ring |
| `digital_incidents` | incident | — | the outage itself (RAG doc + row) |
| internal docs (markdown) | doc | — | post-mortem, fee-change memo, dispute SOP |

The ground truth goes in `evals/ground_truth.yaml`. Label everything `synthetic=true`.

## Optional extras
- **HMDA** mortgage applications (https://ffiec.cfpb.gov/data-browser/) for mortgage-ops volume
- **FFIEC CDR** full call-report schedules (https://cdr.ffiec.gov/public/) for more granular financials
- **Kaggle IBM "Transactions for AML"** / **PaySim** for realistic synthetic transactions (needs a Kaggle login)
