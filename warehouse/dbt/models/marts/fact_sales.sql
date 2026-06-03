-- Gold fact at order-line grain, joined to conformed dims. Powers job profitability, margin by
-- SKU/customer, revenue trend, and fill-rate metrics.
with lines as (
    select * from {{ ref('stg_order_lines') }}
)
select
    {{ dbt_utils.generate_surrogate_key(['l.tenant_id', 'l.order_number', 'l.line_number']) }} as sales_key,
    l.tenant_id,
    l.order_number,
    l.line_number,
    cast(to_char(l.order_date, 'YYYYMMDD') as integer) as date_key,
    dc.customer_key,
    dp.product_key,
    dc.customer_name,
    dc.region,
    dc.segment,
    dp.product_group,
    l.order_qty,
    l.ship_qty,
    l.revenue,
    l.cost,
    l.gross_margin
from lines l
left join {{ ref('dim_customer') }} dc
    on l.tenant_id = dc.tenant_id and l.customer_id = dc.customer_id
left join {{ ref('dim_product') }} dp
    on l.tenant_id = dp.tenant_id and l.sku = dp.sku
