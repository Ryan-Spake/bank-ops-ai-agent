-- Every mature month (after the first FDIC quarter we hold) must find deposits,
-- otherwise per-$1B normalization silently goes null.
select *
from {{ ref('fct_complaints_monthly') }}
where is_mature
  and total_deposits_usd is null
  and month_end >= (select min(report_date) from {{ ref('stg_fdic__financials') }})
