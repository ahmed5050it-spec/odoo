# website_sale_collect — Reverse-Engineering Brief

`website_sale_collect` (manifest name **Click & Collect**, category Website/Website, `application: false`, `auto_install: false`) adds an **in-store pickup** ("Click & Collect") delivery option to the Odoo online checkout: shoppers can check in-store stock, choose a store to collect from, and pay either online or **on site** (cash at the counter). It is a **bridge/option add-on**, not a hub: it ships **0 own models** — only **8 `_inherit`-without-`_name` extensions** — **2 JSON-RPC routes** and **~1626 Python LOC / ~483 XML LOC**, decorating the `website_sale_stock` cart with a warehouse-as-pickup-point concept and wiring in `base_geolocalize` (distance-sorted stores) and `payment_custom` (pay on site).

## Role & Dependencies

Why it depends on each listed module:
- **website_sale_stock** — provides the eCommerce storefront, the `sale.order` cart, the `delivery`-based pickup-location plumbing (`pickup_location_data`, `_get_pickup_locations`, `LocationSelectorDialog`) and the stock-aware product page that this module extends. Transitively pulls in `website_sale`, `stock`, `delivery`, `sale`.
- **base_geolocalize** — `res.partner.geo_localize()` geocodes store and shopper addresses so candidate stores can be sorted by **Haversine distance** (`utils.calculate_partner_distance`).
- **payment_custom** — the "manual/custom" payment provider that this module specializes into a `custom_mode='on_site'` **"Pay on site"** method for collect-and-pay-at-counter orders.

Capability added on top: a **published "Pick up in store" delivery method backed by warehouses**, a **geolocated store selector with per-store stock badges**, automatic **warehouse + tax pinning to the chosen store**, and a **pay-on-site completion path**.

## Data Model (the ERM)

The module owns no stored model; it extends eight (facts: `inherit_only_count: 8`). Key extensions:

| _name (inherit) | role added | new fields | Key relations |
|-----------------|-----------|-----------|---------------|
| delivery.carrier | `delivery_type='in_store'`; carrier = a Click&Collect store group | 2 | warehouse_ids→stock.warehouse ("Stores") |
| sale.order | warehouse/fiscal-position from the picked store; per-store stock checks | 0 (11 methods) | warehouse_id→stock.warehouse, carrier_id→delivery.carrier, `pickup_location_data` (Json, from `delivery`) |
| stock.warehouse | a warehouse becomes a **pickup point** | 1 | opening_hours→resource.calendar, partner_id→res.partner (geo) |
| website | `in_store_dm_id` computed Click&Collect carrier for the site | 1 | in_store_dm_id→delivery.carrier |
| product.template | Click&Collect availability data on the product page | 0 (1 method) | — |
| payment.provider | `custom_mode='on_site'` ("Pay on site") | 1 | — |
| payment.transaction | on-site confirm → picking | 0 (1 method) | sale_order_ids→sale.order |
| res.config.settings | admin shortcut to the in_store carriers | 0 (1 method) | — |

The design is **option-on-existing-hub**: the *carrier* doubles as the pickup-point catalog (`warehouse_ids`), the *warehouse* doubles as the pickup location (`_prepare_pickup_location_data`), and the *cart* (`sale.order`) carries the chosen store in the inherited `pickup_location_data` Json plus a pinned `warehouse_id`. Field additions are few and selection/relation-typed (facts: 2 Selection, 2 Many2one, 1 Many2many) — behavior lives in **30 inherited methods**, not new schema.

## Behavior & Surfaces

- **Routes (2, both jsonrpc / `auth='public'`):** `/website_sale/get_pickup_locations` is *overridden* (bare `@route()`, so it keeps the parent path) to force the in-store method onto the cart — or build a **transient `sale.order.new(...)` when there is no cart yet** — before listing stores; `/shop/set_click_and_collect_location` is *new* and is the product-page entry point (`request.cart or website._create_cart()` → set in_store carrier → `_set_pickup_location`). It is deliberately distinct from `website_sale`'s `/website_sale/set_pickup_location`, which is only used on the checkout page.
- **Views:** 6 inherit-only view files (no new menus/actions): a `stock.warehouse` form gains `opening_hours`; `delivery.carrier` gets an in_store form/list; `res.config.settings` gets the eCommerce-Shipping Click&Collect toggle + an action button; plus `stock.picking` and storefront QWeb (`templates.xml`, `delivery_form_templates.xml`).
- **Security:** **0 own ACLs / record rules / groups** — there is no new stored model, so access rides on the parent models' security; storefront routes are public, config is reached through Website settings.
- **Frontend:** 6 JS files, **1 OWL public component** `ClickAndCollectAvailability` (product page), 5 patches (`Checkout`, `LocationSelectorDialog` ×2, `PaymentForm`, `WebsiteSale`), 2 tours, 1 `web.assets_frontend` bundle.

Behavioral facts read from source (beyond metadata):
- **Store selection:** `_get_pickup_locations` dispatches reflectively to `delivery.carrier._in_store_get_close_locations`, which `geo_localize()`s the address, builds each warehouse's `_prepare_pickup_location_data()`, attaches per-store stock, and returns stores **sorted by Haversine distance**.
- **Warehouse/tax pinning:** `_set_pickup_location` sets `warehouse_id = pickup_location_data['id']`; `_compute_warehouse_id` is overridden to **not** clobber that choice; `_compute_fiscal_position_id` computes tax against the **store's** address (`delivery=warehouse_id.partner_id`).
- **Per-store availability:** stock is read as `product.with_context(warehouse_id=wh.id).free_qty`; the product page shows the **max across all in-store warehouses** before a store is picked, then the selected store's stock; shortages set `sale.order.line.shop_warning` and **block payment** (`_check_cart_is_ready_to_be_paid`, `_get_shop_payment_errors`).
- **Pay-in-store completion:** `payment.transaction._post_process` confirms the draft order (`action_confirm(send_email=True)`) **on a *pending* on_site transaction**, creating the `stock.picking` for later in-store cash payment; `_get_compatible_providers` only offers "Pay on site" for in_store orders with a physical (`consu`) product, and a controller guard raises `ValidationError` if it is used otherwise.

## Value-Configuration Classification

- **value_model: network** (primary). website_sale_collect inherits the value logic of its `website_sale(_stock)` parent: it is an **omnichannel eCommerce fulfilment option** on the online sell-side channel. Its work is **mediation over shared channel infrastructure** — matching a shopper to a nearby, in-stock store and binding the cart to that warehouse and a pay-on-site provider — not the linear transform-to-order of a chain. It owns no order/document chain; it decorates `website_sale`'s `sale.order` and hands off to the existing flow (`action_confirm` → `stock.picking`; cash leg via `payment_custom`).
- **activity_class: primary** — a revenue- and customer-facing channel/fulfilment capability, not a back-office support function.

## APQC PCF Hint

**3.0 Market and Sell Products and Services** — it extends the **eCommerce sell channel** with a click-and-collect option (matching the `website_sale` / `website_sale_wishlist` family). A real **secondary facet** touches **4.4 Operate outbound logistics / order fulfilment** (Deliver Physical Products) — it selects the fulfilling warehouse and triggers the pickup picking — but that fulfilment is *executed* by the underlying `stock` / `delivery` / `sale_stock` chain and merely *triggered* here, so 3.0 (sell) is the home category and 4.4 (deliver) is a downstream facet.

## How to Drive It

Use the **run-odoo** skill. The storefront is public; the carrier/provider config is inspectable via `odoo shell`.

- `env['delivery.carrier'].search([('delivery_type','=','in_store')]).mapped(('name','is_published','warehouse_ids.name'))` — the Click&Collect store groups.
- `env['website'].get_current_website().sudo().in_store_dm_id` — the computed in-store carrier gating every override.
- `env['payment.provider'].search([('code','=','custom'),('custom_mode','=','on_site')])` — the Pay-on-site provider.
- `curl` jsonrpc `/shop/set_click_and_collect_location {pickup_location_data: <json store>}` — set the in_store method + store on the cart (auth=public).
- `so = env['sale.order'].search([('carrier_id.delivery_type','=','in_store')], limit=1); so.read(['warehouse_id','pickup_location_data','fiscal_position_id'])` — inspect a pinned order.

## Open Questions

- Exact stock semantics between confirmation and collection: whether the pending on_site `action_confirm` *reserves* stock at the chosen warehouse or only creates the picking, and how counter-time oversell is handled.
- How a **mixed cart** (some lines in stock at the store, some not) is intended to resolve — the code *blocks* payment on any shortage rather than splitting shipped vs collected lines.
- Whether `opening_hours` / store capacity feed any pickup-scheduling beyond display, and how express-checkout (which **excludes** in_store methods) interacts with a shopper who wanted click-and-collect.

---
*Provenance: structural facts from `extract_module.py` (`facts/website_sale_collect.facts.json`) + `extract_frontend.py` (`frontend/website_sale_collect.frontend.json`); behavioral notes are code-read from `addons/website_sale_collect/controllers/{delivery,payment,main}.py` and `models/{sale_order,delivery_carrier,website,product_template,payment_provider,payment_transaction,stock_warehouse}.py` + `utils.py`, cross-read against `addons/delivery/models/sale_order.py` and `addons/website_sale/controllers/delivery.py`. Odoo 19.0.*
