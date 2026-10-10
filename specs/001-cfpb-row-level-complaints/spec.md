# Feature Specification: Row-Level CFPB Complaints

**Feature Branch**: `feat/cfpb-complaints-rows`
**Created**: 2026-10-09
**Status**: Draft
**Input**: User description: "Row-level CFPB complaints for the 5 banks in the bank_dim seed (JPMorgan Chase plus 4 peers). Land complaints from the history start date into Parquet under data/raw/, keeping only these banks as they are downloaded, either from the CFPB bulk zip or from a per-bank API export. Notes on the API: it ignores `frm` offsets but returns up to 10k rows per request, so pagination must page by date window. Deduplicate on complaint_id. Record every landed file in data/raw/_manifest.json, reusing the existing helpers in scripts/fetch_data.py. Add a dbt seed, cfpb_taxonomy_map, that maps the 2023 product/issue renames to one current taxonomy. Build stg_cfpb__complaints on top of it, with the 60-day maturity flag and synthetic=false lineage, and dbt tests for uniqueness and accepted values. This unblocks fct_complaints_daily and eval questions Q2–Q6. Open questions for the clarify step: (1) history start date: config says 2019, the project plan says 2015; (2) consumer narratives (complaint_what_happened, consent-only) in the core table or in a separate table; (3) bulk zip vs per-bank API export as the source of record."

## Context

Today the warehouse only knows *how many* complaints each bank received per month (API count
queries). The benchmark questions Q02–Q06 need the *why*: product, issue, sub-issue, state,
channel, company response, and timeliness per complaint. This feature lands one row per complaint
for the five banks in the bank seed and exposes a clean, deduplicated, taxonomy-consistent staging
table that a later `fct_complaints_daily` mart builds on. The mart itself is out of scope.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Land row-level complaints with provenance (Priority: P1)

As the project maintainer, I run the data pull and get every CFPB complaint for the five tracked
banks since the history start date, stored locally as a compact columnar file, with each landed
file recorded in the provenance manifest.

**Why this priority**: Nothing downstream (staging, marts, evals Q02–Q06) can exist without the
rows, and the constitution requires every number to trace back to a recorded pull.

**Independent Test**: Run the pull for one bank and a short date range; confirm the landed file
contains only that bank's complaints for that range, has no duplicate complaint IDs, and appears in
the manifest with source, timestamp, row count, and checksum.

**Acceptance Scenarios**:

1. **Given** the five banks in the bank seed, **When** the full pull runs, **Then** the landed data
   contains complaints only for those banks' CFPB company names, from the history start date to the
   latest available date.
2. **Given** a complaint that appears more than once in the source, **When** it is landed, **Then**
   exactly one row per complaint ID is kept.
3. **Given** a completed pull, **When** the manifest is inspected, **Then** every landed file has an
   entry with source URL, pull timestamp, row count, and checksum.
4. **Given** a source window that would exceed the per-request row cap, **When** the pull runs,
   **Then** the window is split so no rows are silently truncated.

---

### User Story 2 - Consistent product/issue taxonomy (Priority: P2)

As an analyst (or the agent), I can compare a product/issue combination across years even though
CFPB renamed products and issues in 2023, because every complaint carries a current-taxonomy
product and issue alongside the original values.

**Why this priority**: Trend and anomaly questions (Q02, Q05) span the rename date; without a
mapping, a renamed issue looks like one series ending and another starting.

**Independent Test**: Pick a pre-2023 complaint with a renamed product/issue; confirm it maps to the
current name, the original value is preserved, and every product/issue value seen in the data is
covered by the mapping.

**Acceptance Scenarios**:

1. **Given** a complaint filed under a pre-2023 product or issue name, **When** it is staged,
   **Then** it shows the current-taxonomy name and still exposes the original name.
2. **Given** a product/issue value with no mapping entry, **When** data tests run, **Then** they
   fail and name the unmapped value.

---

### User Story 3 - Analysis-ready staging table (Priority: P3)

As the agent's analytics layer, I query one staging table of complaints that uses the project's
bank identifiers, flags immature recent data, and is labeled as real (non-synthetic) data.

**Why this priority**: It is the contract the daily mart and Q02–Q06 depend on; it delivers value
only once Stories 1–2 exist.

**Independent Test**: Build the staging table and run its data tests: one row per complaint ID,
every row joins to a known bank, maturity flag set for complaints received within the last 60 days
of the data, and the synthetic label is false on every row.

**Acceptance Scenarios**:

1. **Given** landed complaints, **When** the staging table is built, **Then** each row carries the
   bank identifier from the bank seed, received date, current and original product/issue/sub-issue,
   state, submission channel, company response, timely-response flag, and whether a narrative
   exists.
2. **Given** a complaint received within the maturity window, **When** it is staged, **Then** it is
   flagged immature.
3. **Given** the staging table, **When** its data tests run, **Then** uniqueness of complaint ID,
   non-null keys, valid bank identifiers, and accepted values for categorical fields all pass.
4. **Given** the daily total per bank from staging, **When** it is summed to months, **Then** it
   reconciles with the existing monthly counts for mature months within an agreed tolerance.

---

### Edge Cases

- Company name variants in the source (e.g., a holding company vs. a national association) must
  match exactly the CFPB company names in the bank seed; unknown variants are reported, not dropped
  silently.
- Complaints with missing state, ZIP, or sub-issue are kept, with nulls, not discarded.
- A complaint may be updated after first publication (e.g., company response added); the most
  recent version wins on dedupe.
- Re-running the pull must be idempotent: the same inputs produce the same rows and checksum.
- A pull interrupted mid-way must not leave a partial file that looks complete.
- New product/issue names introduced after this feature ships must fail the mapping coverage test
  rather than pass through unmapped.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The pull MUST land complaints for exactly the banks in the bank seed, identified by
  their seed CFPB company names (no separate bank list).
- **FR-002**: The pull MUST cover complaints received from the history start date through the latest
  available date. History start: [NEEDS CLARIFICATION: 2019-01-01 (current config and dbt var) or
  2015 (earlier planning estimate)? 2015 also spans CFPB's 2017 product overhaul, so the taxonomy map
  would need those renames too.]
- **FR-003**: Landed data MUST be stored as Parquet under `data/raw/` and never committed to git.
- **FR-004**: The landed data MUST contain at most one row per complaint ID; when duplicates exist,
  the most recently updated version is kept.
- **FR-005**: Every landed file MUST be recorded in `data/raw/_manifest.json` (source URL, pull
  timestamp, row count, checksum) using the existing fetch helpers.
- **FR-006**: The source of record MUST be [NEEDS CLARIFICATION: the CFPB bulk zip filtered to the
  five banks as it is read, or a per-bank API export paged by date window (the API ignores offsets
  and caps each request at 10k rows)?]. Whichever is chosen, no window may be silently truncated.
- **FR-007**: Consumer narrative text (present only with consumer consent) MUST be stored
  [NEEDS CLARIFICATION: as a column in the core complaints table, or in a separate narratives table
  keyed by complaint ID?]. The core table MUST expose a has-narrative flag either way.
- **FR-008**: A `cfpb_taxonomy_map` seed MUST map every original product/issue pair seen in the
  landed data to a current-taxonomy product/issue, including the 2023 renames.
- **FR-009**: `stg_cfpb__complaints` MUST expose one row per complaint with: complaint ID, bank ID
  (from the bank seed), received date, sent-to-company date, original and current product,
  sub-product, issue, sub-issue, state, ZIP, submission channel, company response, timely-response
  flag, consumer-disputed flag, tags, has-narrative flag, an immaturity flag driven by
  `var('cfpb_maturity_days')`, and `synthetic = false`.
- **FR-010**: Data tests MUST cover: unique and non-null complaint ID; bank ID relationship to the
  bank seed; accepted values for submission channel, company response, and timely flag; full
  taxonomy-map coverage.
- **FR-011**: Tests MUST NOT call live APIs; the date-window splitting and dedupe logic each get one
  fixture-based test.
- **FR-012**: The pull MUST support the existing smoke mode (one bank, short range) for fast checks.

### Key Entities

- **Complaint**: one consumer complaint to CFPB about a tracked bank. Key: complaint ID. Attributes:
  dates, product taxonomy (original and current), geography, channel, company response, timeliness,
  narrative presence.
- **Taxonomy mapping**: original product/issue pair → current product/issue pair, with the date
  range or reason for the rename.
- **Bank** (existing seed): bank ID, CFPB company name, focal flag; the join key from complaints to
  the rest of the warehouse.
- **Manifest entry** (existing): provenance for each landed file.
- **Narrative** (conditional on FR-007): free text for a complaint, consent-only.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every mature month since the history start, each bank's staged complaint count is
  within 1% of the existing monthly count for that bank and month.
- **SC-002**: 100% of staged complaints have a current-taxonomy product and issue (zero unmapped).
- **SC-003**: Zero duplicate complaint IDs in the landed data and in staging.
- **SC-004**: A maintainer can answer "which product/issue combinations changed most for bank X over
  the last 6 mature months" from staging with a single query, unblocking eval questions Q02–Q06.
- **SC-005**: A full refresh completes unattended in under 30 minutes on a home connection; the smoke
  run completes in under 1 minute.
- **SC-006**: The full test suite stays fast (no measurable increase beyond a few seconds) and makes
  no network calls.

## Assumptions

- The five banks and their CFPB company names in the bank seed are correct; holding-company vs.
  subsidiary caveats are already documented and carry over.
- The 60-day maturity rule and its dbt var apply unchanged to row-level data.
- Data volume for five banks is in the low millions of rows at most and fits comfortably in local
  DuckDB.
- CFPB data is CC0; landing it locally has no licensing constraints, but it is still never committed.
- `fct_complaints_daily`, anomaly detection, and narrative retrieval (RAG) are out of scope; this
  feature only delivers landing, taxonomy mapping, and staging.
- Snowflake loading of the new raw files is out of scope (tracked separately).
