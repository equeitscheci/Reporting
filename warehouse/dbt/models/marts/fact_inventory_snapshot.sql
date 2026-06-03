select
    {{ dbt_utils.generate_surrogate_key(['i.tenant_id', 'i.sku', 'i.location', 'i.snapshot_date']) }} as inventory_key,
    i.tenant_id,
    cast(to_char(i.snapshot_date, 'YYYYMMDD') as integer) as date_key,
    dp.product_key,
    dp.product_group,
    i.location,
    i.qty_on_hand,
    i.unit_cost,
    (i.qty_on_hand * i.unit_cost) as inventory_value
from {{ source('canonical', 'inventory_level') }} i
left join {{ ref('dim_product') }} dp
    on i.tenant_id = dp.tenant_id and i.sku = dp.sku
