select
    cast(bank_id as varchar)        as bank_id,
    cast(month as date)             as month_start,
    last_day(cast(month as date))   as month_end,
    cast(complaints as integer)     as complaints
from {{ source('raw_cfpb', 'monthly_counts') }}
