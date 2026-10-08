-- Milestone M1 check: mature-month complaints per $1B deposits, last 12 months, by bank.
select bank_name, round(avg(complaints_per_1b_deposits), 2) as avg_per_1b, sum(complaints) as complaints
from {{ ref('fct_complaints_monthly') }}
where is_mature and month_start >= current_date - interval 14 month
group by bank_name
order by avg_per_1b desc
