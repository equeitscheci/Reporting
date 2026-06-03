select
    {{ dbt_utils.generate_surrogate_key(['tenant_id', 'sku']) }} as product_key,
    tenant_id,
    sku,
    description,
    product_group,
    standard_cost,
    list_price
from {{ source('canonical', 'product') }}
