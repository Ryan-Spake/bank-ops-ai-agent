-- GOLD: quarterly bank financials with true quarterly flows and YoY deltas.
select
    q.bank_id || '|' || strftime(q.report_date, '%Y-%m-%d')                as bank_quarter_key,
    q.*,
    b.bank_name,
    b.is_focal,
    q.efficiency_ratio_pct   - lag(q.efficiency_ratio_pct, 4)   over w     as efficiency_ratio_yoy_pp,
    q.net_chargeoff_rate_pct - lag(q.net_chargeoff_rate_pct, 4) over w     as net_chargeoff_rate_yoy_pp
from {{ ref('int_fdic__quarterly_flows') }} q
join {{ ref('bank_dim') }} b using (bank_id)
window w as (partition by q.bank_id order by q.report_date)
