select
    {{ dbt_utils.generate_surrogate_key(['tenant_id', 'source_id']) }} as customer_key,
    tenant_id,
    source_id      as customer_id,
    name           as customer_name,
    region,
    segment
from {{ source('canonical', 'customer') }}
