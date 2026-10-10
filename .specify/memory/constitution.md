<!--
Sync Impact Report
- Version change: template → 1.0.0 (initial ratification)
- Principles defined: I. Traceable Numbers; II. Honest Data Labels; III. Comparable Metrics;
  IV. Live Eval Oracles; V. Single Source of Truth; VI. Lean Code
- Sections added: Data & Agent Constraints; Development Workflow & Quality Gates; Governance
- Templates: plan-template.md ✅ (Constitution Check gates are derived from this file at plan time;
  no edit needed) · spec-template.md ✅ no change · tasks-template.md ✅ no change
- Deferred TODOs: none
-->

# Bank Ops AI Agent Constitution

An AI agent that explains bank operational metrics (focal bank JPMorgan Chase vs. four peers) from
public CFPB, FDIC, FRED, SEC EDGAR, and eCFR data plus a clearly labeled synthetic ops layer.
Auditability is the product: an answer that cannot be traced is a wrong answer.

## Core Principles

### I. Traceable Numbers (NON-NEGOTIABLE)

- Every number the agent states, and every number in a README, report, or eval, MUST be
  reproducible from SQL against dbt models, and every raw input MUST be recorded in
  `data/raw/_manifest.json` (url, pulled_at, rows, sha256).
- dbt owns every transform; `scripts/fetch_data.py` only downloads and records provenance.
- Agent tools query only the `marts.*` schema, read-only, through an allow-listed surface.

*Rationale*: the target audience (bank ops, model risk / SR 11-7) trusts only what it can audit.

### II. Honest Data Labels

- Synthetic data (internal ops, planted anomalies, synthetic documents) MUST carry
  `synthetic=true` at the row/table level and be disclosed as synthetic wherever it surfaces.
- Known caveats MUST travel with the number (e.g., CFPB `company` may be a holding company while
  FDIC deposits are the bank subsidiary, so per-deposit rates are approximate).
- The agent MUST NOT present synthetic data as describing a real institution's internals.

### III. Comparable Metrics

- **CFPB 60-day maturity rule**: complaint months younger than `var('cfpb_maturity_days')`
  (60) are immature; "this month"/"latest" means the latest *mature* month. Immature data MUST
  NOT drive trend or anomaly claims.
- **Peer comparisons are normalized per $1B deposits** (as-of join to the latest quarter-end FDIC
  deposits). Raw counts may be shown, never used alone to rank banks.
- Units and time grains are fixed in staging (FDIC $ thousands → dollars, YTD → quarterly flows,
  inclusive CFPB date bounds) so downstream code and the LLM never re-derive them.
- Calendar effects (days in month) MUST be considered before calling a month-over-month change.

### IV. Live Eval Oracles

- Eval expected values come from **reference SQL executed at eval time**, never hard-coded.
- Recorded `snapshot:` values are context for authors, not an answer key.
- Tests make no live API or LLM calls; use fixtures and recorded responses.

*Rationale*: CFPB data keeps changing; a frozen answer key silently goes stale.

### V. Single Source of Truth

- **dbt seeds are the single source of truth** for banks (`bank_dim`) and FRED series
  (`fred_series_dim`); Python reads the seeds rather than keeping its own lists. New reference
  mappings (e.g., taxonomy renames) are seeds too.
- `config/` holds fetch settings only, never duplicated entity lists.
- The benchmark question text has one canonical home (`evals/questions.yaml`).

### VI. Lean Code

- No speculative abstractions, plugin layers, or config knobs without a current caller.
- Reuse existing helpers before adding new ones (e.g., `_get`, `_write`, `_record`, `_csv`,
  `_months` in `scripts/fetch_data.py`).
- Each non-trivial piece of logic ships with exactly one runnable check (a pytest test or a dbt
  test) that would fail if the logic were wrong.
- Dependencies are added in the PR that first imports them.

## Data & Agent Constraints

- Raw and derived data files are never committed (`check-added-large-files`, `.gitignore`).
- Secrets live only in `.env`; pre-commit blocks API keys and passwords from being committed.
- API etiquette is respected (e.g., SEC EDGAR descriptive User-Agent and ≤10 req/s).
- Out-of-scope questions (e.g., stock prices, investment advice) are refused without tool calls.
- Regulatory claims cite the governing text (eCFR section) and must not conflate distinct
  standards (e.g., CFPB "timely response" is not Reg E error-resolution compliance).
- DuckDB is the dev warehouse; SQL stays portable to the Snowflake target.

## Development Workflow & Quality Gates

- All work lands via feature branch + pull request into `main`.
- Gates that MUST pass before merge (locally via pre-commit/pre-push and again in CI):
  `ruff check` + `ruff format --check`, `pytest`, and `dbt parse`.
- Spec Kit artifacts: `specs/<feature>/` holds per-feature requirements, plans, and decisions;
  the maintainer's decision log remains the cross-project record of *why*. A feature decision that
  changes a principle here requires a constitution amendment, not just a plan note.
- This constitution and `specs/` are public: keep credentials, personal details, and private
  notes out of them.

## Governance

- This constitution supersedes conflicting practice. Every `/speckit-plan` Constitution Check and
  every PR review verifies compliance; deviations are recorded in the plan's Complexity Tracking
  table with the simpler alternative that was rejected.
- Amendments land by PR that updates this file, the Sync Impact Report, and any affected templates.
- Versioning: MAJOR = principle removed or redefined incompatibly; MINOR = principle or section
  added or materially expanded; PATCH = wording or clarification only.

**Version**: 1.0.0 | **Ratified**: 2026-10-09 | **Last Amended**: 2026-10-09
