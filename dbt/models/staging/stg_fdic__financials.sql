-- FDIC reports dollars in thousands; convert to dollars here so no downstream
-- consumer (or LLM) has to remember the unit.
select
    cast("CERT" as integer)                         as fdic_cert,
    strptime(cast("REPDTE" as varchar), '%Y%m%d')::date as report_date,
    "ASSET"  * 1000.0                               as total_assets_usd,
    "DEP"    * 1000.0                               as total_deposits_usd,
    "LNLSNET"* 1000.0                               as net_loans_usd,
    "NETINC" * 1000.0                               as net_income_ytd_usd,
    "NONII"  * 1000.0                               as noninterest_income_ytd_usd,
    "NONIX"  * 1000.0                               as noninterest_expense_ytd_usd,
    "ELNATR" * 1000.0                               as provision_ytd_usd,
    "ROA"                                           as roa_pct,
    "ROE"                                           as roe_pct,
    "NIMY"                                          as net_interest_margin_pct,
    "EEFFR"                                         as efficiency_ratio_pct,
    "NTLNLSR"                                       as net_chargeoff_rate_pct,
    "NCLNLSR"                                       as noncurrent_loan_rate_pct
from {{ source('raw_fdic', 'financials') }}
