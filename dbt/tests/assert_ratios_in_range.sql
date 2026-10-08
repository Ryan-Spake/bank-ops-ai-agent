select *
from {{ ref('fct_bank_quarterly') }}
where efficiency_ratio_pct not between 0 and 200
   or net_chargeoff_rate_pct not between -5 and 50
