-- Raw FRED files are wide (one value column per file); reshape to long.
with src as (
    select * from {{ source('raw_fred', 'observations') }}
),

long as (
    unpivot src
    on columns(* exclude (observation_date, filename))
    into name series_id value value
)

select
    series_id,
    cast(observation_date as date)  as observation_date,
    try_cast(nullif(value, '.') as double) as value  -- FRED marks missing as '.'
from long
where try_cast(nullif(value, '.') as double) is not null
