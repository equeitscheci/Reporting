-- Staging: enrich order lines with computed measures (revenue/cost/margin) at line grain.
with lines as (
    select * from {{ source('canonical', 'order_line') }}
),
orders as (
    select source_id, order_number, customer_id, order_date, status
    from {{ source('canonical', 'order') }}
)
select
    l.tenant_id,
    l.order_number,
    l.line_number,
    l.sku,
    o.customer_id,
    o.order_date,
    o.status                          as order_status,
    l.order_qty,
    l.ship_qty,
    l.unit_price,
    l.unit_cost,
    (l.order_qty * l.unit_price)                          as revenue,
    (l.order_qty * l.unit_cost)                           as cost,
    (l.order_qty * l.unit_price) - (l.order_qty * l.unit_cost) as gross_margin
from lines l
left join orders o
    on l.order_number = o.order_number
