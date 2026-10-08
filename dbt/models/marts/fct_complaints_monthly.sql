-- GOLD: monthly complaint volume per bank, normalized by deposits and flagged
-- for CFPB reporting lag. The agent's primary "operational volume" table.
with counts as (
    select * from {{ ref('stg_cfpb__monthly_counts') }}
),

deposits as (
    select bank_id, report_date, total_deposits_usd
    from {{ ref('int_fdic__quarterly_flows') }}
),

joined as (
    -- As-of join: use the latest quarter-end deposits on or before month end.
    select
        c.bank_id,
        c.month_start,
        c.month_end,
        c.complaints,
        d.report_date        as deposits_as_of,
        d.total_deposits_usd
    from counts c
    asof left join deposits d
        on c.bank_id = d.bank_id
       and c.month_end >= d.report_date
),

final as (
    select
        bank_id || '|' || strftime(month_start, '%Y-%m')          as complaint_month_key,
        j.bank_id,
        b.bank_name,
        b.is_focal,
        month_start,
        month_end,
        complaints,
        total_deposits_usd,
        deposits_as_of,
        complaints / nullif(total_deposits_usd / 1e9, 0)          as complaints_per_1b_deposits,
        month_end + interval {{ var('cfpb_maturity_days') }} day < current_date as is_mature,
        lag(complaints, 1)  over w                                as complaints_prior_month,
        lag(complaints, 12) over w                                as complaints_prior_year
    from joined j
    join {{ ref('bank_dim') }} b using (bank_id)
    window w as (partition by j.bank_id order by month_start)
)

select
    *,
    round(100.0 * (complaints - complaints_prior_month) / nullif(complaints_prior_month, 0), 2) as mom_pct_change,
    round(100.0 * (complaints - complaints_prior_year)  / nullif(complaints_prior_year, 0), 2)  as yoy_pct_change
from final
