"""Generate bundled sample ERP data for the offline demo.

Produces source-shaped JSON (vendor-flavored field names) under app/connectors/sample_data/.
The data spans 12 months and contains an intentional margin drop + inventory spike in the most
recent month so the insights engine has something real to detect.

Run:  python scripts/gen_sample_data.py
"""

from __future__ import annotations

import json
import pathlib
import random
from datetime import date, timedelta

random.seed(42)
OUT = pathlib.Path(__file__).resolve().parent.parent / "app" / "connectors" / "sample_data"
OUT.mkdir(parents=True, exist_ok=True)

CUSTOMERS = [
    {"CustNum": f"C{1000 + i}", "CustName": name, "Region": region, "Segment": seg,
     "ChangedDate": "2025-01-01"}
    for i, (name, region, seg) in enumerate(
        [
            ("Ridgeline Builders", "West", "Construction"),
            ("Apex Distributors", "Midwest", "Distribution"),
            ("Northgate Mfg", "Northeast", "OEM"),
            ("Summit Supply Co", "South", "Distribution"),
            ("Cedar Field Services", "West", "Service"),
            ("Harbor Equipment", "Northeast", "Dealer"),
            ("Lone Star Fabrication", "South", "OEM"),
            ("Cascade Wholesale", "West", "Distribution"),
        ]
    )
]

PRODUCTS = [
    {"PartNum": f"P{200 + i}", "Description": desc, "ProductGroup": grp,
     "StdUnitCost": cost, "ListPrice": price, "ChangedDate": "2025-01-01"}
    for i, (desc, grp, cost, price) in enumerate(
        [
            ("Steel Bracket A", "Brackets", 4.50, 9.00),
            ("Steel Bracket B", "Brackets", 5.25, 11.00),
            ("Hydraulic Valve", "Valves", 22.00, 48.00),
            ("Control Module", "Electronics", 65.00, 140.00),
            ("Drive Belt 1in", "Belts", 3.10, 7.50),
            ("Bearing Assembly", "Bearings", 12.40, 27.00),
            ("Conveyor Roller", "Rollers", 18.00, 39.00),
            ("Panel Enclosure", "Enclosures", 33.00, 72.00),
        ]
    )
]

START = date(2025, 6, 1)
order_rows: list[dict] = []
line_rows: list[dict] = []
invoice_rows: list[dict] = []
inventory_rows: list[dict] = []
order_no = 50000
inv_no = 80000

for m in range(12):  # 12 months
    month_start = (START.replace(day=1) + timedelta(days=31 * m)).replace(day=1)
    last_month = m == 11  # most recent month carries the anomaly
    n_orders = random.randint(40, 60)
    for _ in range(n_orders):
        order_no += 1
        cust = random.choice(CUSTOMERS)
        odate = month_start + timedelta(days=random.randint(0, 27))
        order_rows.append(
            {
                "OrderNum": order_no,
                "CustNum": cust["CustNum"],
                "OrderDate": odate.isoformat(),
                "OrderStatus": random.choice(["Open", "Shipped", "Shipped", "Closed"]),
                "ChangedDate": odate.isoformat(),
            }
        )
        for ln in range(random.randint(1, 4)):
            prod = random.choice(PRODUCTS)
            qty = random.randint(1, 40)
            # Margin compression in the final month: discount up, cost up.
            disc = random.uniform(0.0, 0.08) + (0.18 if last_month else 0.0)
            cost_infl = 1.0 + (0.12 if last_month else 0.0)
            unit_price = round(prod["ListPrice"] * (1 - disc), 2)
            unit_cost = round(prod["StdUnitCost"] * cost_infl, 2)
            line_rows.append(
                {
                    "OrderNum": order_no,
                    "LineNum": ln + 1,
                    "PartNum": prod["PartNum"],
                    "OrderQty": qty,
                    "UnitPrice": unit_price,
                    "UnitCost": unit_cost,
                    "ShipQty": qty if random.random() > (0.15 if last_month else 0.05) else qty - 1,
                }
            )
        inv_no += 1
        invoice_rows.append(
            {
                "InvoiceNum": inv_no,
                "OrderNum": order_no,
                "CustNum": cust["CustNum"],
                "InvoiceDate": (odate + timedelta(days=random.randint(1, 10))).isoformat(),
                "DueDate": (odate + timedelta(days=40)).isoformat(),
                "InvoiceAmt": 0.0,  # filled below
                "AmountPaid": 0.0,
                "ChangedDate": (odate + timedelta(days=1)).isoformat(),
            }
        )
    # Monthly inventory snapshot — final month has an inventory spike on slow movers.
    snap_date = (month_start + timedelta(days=27)).isoformat()
    for prod in PRODUCTS:
        base = random.randint(50, 400)
        if last_month and prod["ProductGroup"] in ("Enclosures", "Rollers"):
            base *= 4  # spike
        inventory_rows.append(
            {
                "PartNum": prod["PartNum"],
                "Warehouse": "MAIN",
                "SnapshotDate": snap_date,
                "QtyOnHand": base,
                "UnitCost": prod["StdUnitCost"],
            }
        )

# Fill invoice amounts from their order lines.
order_total: dict[int, float] = {}
for ln in line_rows:
    order_total[ln["OrderNum"]] = order_total.get(ln["OrderNum"], 0.0) + ln["OrderQty"] * ln["UnitPrice"]
for inv in invoice_rows:
    amt = round(order_total.get(inv["OrderNum"], 0.0), 2)
    inv["InvoiceAmt"] = amt
    inv["AmountPaid"] = amt if random.random() > 0.25 else round(amt * random.uniform(0, 0.7), 2)

files = {
    "customers": CUSTOMERS,
    "products": PRODUCTS,
    "sales_orders": order_rows,
    "order_lines": line_rows,
    "invoices": invoice_rows,
    "inventory_snapshots": inventory_rows,
}
for name, rows in files.items():
    (OUT / f"{name}.json").write_text(json.dumps(rows, indent=2))
    print(f"wrote {name}.json ({len(rows)} rows)")
