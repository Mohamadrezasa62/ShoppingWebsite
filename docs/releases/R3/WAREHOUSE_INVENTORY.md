# Seller warehouse inventory checkpoint

This implements seller-owned stock locations, not milestone or launch acceptance.

## Delivered scope

Warehouses have a stable code, active flag and one default location per seller.
Offer balances hold physical quantity, reserved quantity and optimistic version.
Movements record adjustment, allocation, consumption, release, transfer and restock.
Checkout allocations are deterministic by balance ID, not geography or delivery SLA.
Reservations cannot be moved or removed by seller adjustments. Payment capture
with invalid allocations enters payment review instead of silently fulfilling.

Returns restore logical equal-SKU units to their original allocated locations.
Pre-activation paid orders lack location history and restore to the default
warehouse with an explicitly labeled legacy movement. This is not serial-number
or batch traceability. Transfers are immediate audited stock movements; in-transit
transfers, platform-operated fulfillment, per-warehouse shipments and carrier
integration remain outstanding.

## API and interface

All paths below are under `/api/v1/`. Seller membership is checked for reads;
active approved membership is checked again under transaction locks for writes.
Warehouse management requires store ownership. Mutation requests require CSRF.

| Path | Operations |
|---|---|
| `seller/stores/{sellerId}/warehouses/` | GET list, POST create |
| `seller/stores/{sellerId}/warehouses/{warehouseId}/` | PATCH name/active state |
| `seller/stores/{sellerId}/inventory/` | GET 25-offer cursor page |
| `seller/stores/{sellerId}/inventory/{offerId}/activate/` | POST legacy activation |
| `seller/stores/{sellerId}/inventory/{offerId}/adjust/` | POST version-checked physical count |
| `seller/stores/{sellerId}/inventory/{offerId}/transfer/` | POST UUID-deduplicated transfer |
| `seller/stores/{sellerId}/inventory/{offerId}/history/` | GET latest 100 movements |
| `seller/stores/{sellerId}/inventory-csv/` | GET 500-balance export page, POST atomic import |
| `operations/inventory/?seller_id={id}` | GET marketplace/system staff report |

Seller and administrator panels expose these operations. CSV columns are exactly
`sku,warehouse_code,quantity,version`. Imports accept at most 500 rows/256 KiB,
require an audit reason and request UUID, and reject missing references, duplicates,
foreign warehouses, stale versions or quantities below reserved stock. New
balances require version zero. Identical retries return the stored receipt;
changed files under the same request key conflict. Exported spreadsheet formula
prefixes are neutralized and must be reviewed before importing an edited file.

## Evidence

| Check | Local result |
|---|---|
| Warehouse/CSV/invariant regression tests | 25 tests passed |
| Complete backend suite | 202 discovered; 189 passed, 13 PostgreSQL tests skipped |
| Frontend | TypeScript and production webpack build passed |
| Migration rehearsal | 1,000 products, 2,000 legacy offers converted in 2.702 seconds |
| Rehearsal stock check | 2,000 managed offers/balances/movements; zero issues |

The rehearsal used a disposable synthetic SQLite database with two sellers and
no orders. Pending-order migration is covered by fixtures, not that rehearsal.
[Recorded result](inventory-migration-sqlite.json) is not a load benchmark,
PostgreSQL migration, backup restoration or production approval. Three added
PostgreSQL tests cover transfer/checkout, owner adjustment/checkout and warehouse
deactivation/restock contention; they remain unexecuted locally.

Movement immutability is enforced by model helpers and restricted API access,
not database triggers. Historical events are not invented for pre-migration paid
orders. Shipping still uses seller delivery records. Real courier, SMS and bank
integrations, document KYC and legal/business policy approval remain incomplete.
