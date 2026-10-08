-- FDIC income-statement fields are year-to-date. De-cumulate to quarterly flows:
-- Q1 = YTD value; Q2-Q4 = YTD minus prior quarter's YTD within the same year.
with fin as (
    select
        f.*,
        b.bank_id
    from {{ ref('stg_fdic__financials') }} f
    join {{ ref('bank_dim') }} b using (fdic_cert)
)

select
    bank_id,
    report_date,
    total_assets_usd,
    total_deposits_usd,
    net_loans_usd,
    {% for col in ['net_income', 'noninterest_income', 'noninterest_expense', 'provision'] %}
    {{ col }}_ytd_usd - coalesce(
        lag({{ col }}_ytd_usd) over (partition by bank_id, year(report_date) order by report_date), 0
    ) as {{ col }}_qtr_usd,
    {% endfor %}
    roa_pct,
    roe_pct,
    net_interest_margin_pct,
    efficiency_ratio_pct,
    net_chargeoff_rate_pct,
    noncurrent_loan_rate_pct
from fin
