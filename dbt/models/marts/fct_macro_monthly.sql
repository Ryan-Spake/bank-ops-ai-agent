-- GOLD: FRED series on a common monthly grain. Weekly series are averaged;
-- quarterly series are carried forward (flagged) so every month has a value.
with monthly as (
    select
        series_id,
        date_trunc('month', observation_date)::date as month_start,
        avg(value)                                  as value
    from {{ ref('stg_fred__observations') }}
    group by all
),

grid as (
    select cast(m.range as date) as month_start, s.*
    from range(
        date '{{ var("history_start") }}',
        date_trunc('month', current_date) + interval 1 month,
        interval 1 month
    ) m
    cross join {{ ref('fred_series_dim') }} s
),

filled as (
    select
        g.*,
        last_value(mo.value ignore nulls) over (
            partition by g.series_id order by g.month_start
            rows between unbounded preceding and current row
        )                         as value,
        mo.value is null          as is_carried_forward
    from grid g
    left join monthly mo using (series_id, month_start)
)

select
    series_id || '|' || strftime(month_start, '%Y-%m') as series_month_key,
    *
from filled
where value is not null
