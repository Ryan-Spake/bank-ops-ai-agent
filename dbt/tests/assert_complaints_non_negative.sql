select * from {{ ref('fct_complaints_monthly') }} where complaints < 0
