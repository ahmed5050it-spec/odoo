# website_sale_stock — Reverse-Engineering Brief

`website_sale_stock` (manifest name **Product Availability**, category Website/Website, `application: false`, **`auto_install: true`**) adds **real-time inventory availability** to the Odoo online storefront. It declares **no model of its own** — 10 `_inherit`-only extensions, ~1.6k Python LOC, 2 routes — and exists to make the `website_sale` shop *stock-aware*: it shows on-hand quantity on the product page, lets a merchant block or keep selling out-of-stock products, caps the cart to what is on hand, and offers a back-in-stock email waitlist. It is a focused extension layer between the `website_sale` storefront and `stock`, not a standalone capability (hence `auto_install`).

## Role & Dependencies

| Depends on | Why (inferred) |
|------------|----------------|
| `website_sale` | The storefront/cart it makes availability-aware (it overrides the cart-qty hook, the product-page configurator and the GMC feed). |
| `sale_stock` | The sale↔stock bridge that gives `sale.order`/`sale.order.line` their delivery semantics and `free_qty`; a confirmed cart flows into its delivery chain. |
| `stock_delivery` | Pulls in delivery/shipping context (`stock` + carriers) so availability ties to the warehouse that ships. |

`auto_install=True` means it activates automatically whenever `website_sale`, `sale_stock` and `stock_delivery` are all present — the hallmark of a glue/extension module.

## Data Model (the ERM — all extensions)

| Model (`_inherit`) | Adds | Key new fields / relations |
|--------------------|------|----------------------------|
| **`product.template`** | 4 fields, 4 methods | `allow_out_of_stock_order` (Bool, default **True**), `show_availability` (Bool), `available_threshold` (Float, default **5.0**), `out_of_stock_message` (Html, translatable) |
| **`product.product`** | 1 field, 6 methods | `stock_notification_partner_ids→res.partner` (M2M `stock_notification_product_partner_rel`); `_is_sold_out`, `_get_max_quantity`, `_send_availability_email` |
| **`sale.order`** | 10 methods | `_verify_updated_quantity` (cart clamp), `_get_cart_and_free_qty`, `_get_free_qty`, `_check_cart_is_ready_to_be_paid` |
| **`sale.order.line`** | 4 methods | `_check_availability`, `_get_max_available_qty`, `_set_shop_warning_stock` |
| **`website`** | 1 field | `warehouse_id→stock.warehouse`; `_get_product_available_qty` (the availability read) |
| **`res.config.settings`** | 4 fields | `default_allow_out_of_stock_order`, `default_available_threshold`, `default_show_availability`, `website_warehouse_id→stock.warehouse` |
| `stock.picking` | 1 field | `website_id→website` (related `sale_id.website_id`, stored) — eCommerce delivery tag |
| `product.ribbon` | 1 field | `assign` += `out_of_stock` (auto out-of-stock ribbon) |
| `product.combo` / `product.feed` | 1 method each | combo max-qty; GMC `out_of_stock` availability |

The whole module turns on two read primitives — **`website._get_product_available_qty(product)`** = `product.with_context(warehouse_id=website.warehouse_id.id).free_qty` (the storefront availability number) and **`sale.order._get_free_qty`** (the checkout-warehouse variant) — plus the per-product policy flag **`allow_out_of_stock_order`**. Note it deliberately uses **`free_qty`** (on-hand minus outgoing reservations), **not `virtual_available`**.

## Behavior & Surfaces (the metadata gap)

- **Display (stock → page).** `/website_sale/get_combination_info` is overridden (bare `@route()`) to set context `website_sale_stock_get_quantity=True`; that flag makes `product.template._get_additionnal_combination_info` emit the live payload — floor-rounded `free_qty`, `show_availability`, `out_of_stock_message`, and (only when `allow_out_of_stock_order=False`) `cart_qty`. The QWeb `website_sale_stock.product_availability` renders an "N <uom> in stock" warning badge once `free_qty ≤ available_threshold`, or an out-of-stock badge + back-in-stock form once `free_qty ≤ 0`.
- **Cart clamp (no over-ordering).** `website_sale`'s add/update routes call the hook `sale.order._verify_updated_quantity` (parent returns the qty unchanged). The override, for a storable product with `allow_out_of_stock_order=False`, caps the line to `allowed_line_qty = available_qty − other-lines-cart-qty` and sets `sale.order.line.shop_warning` ("You ask for X but only Y is available"). The cart can never exceed on-hand.
- **Confirmation gate.** `sale.order._check_cart_is_ready_to_be_paid` (called at checkout/payment) runs `sale.order.line._check_availability` per line and raises `ValidationError` (joining the warnings) if any line drifted out of stock between add and pay — blocking payment.
- **Out-of-stock fan-out.** `product._is_sold_out()` (sold-out iff storable, not allow-out-of-stock, and `free_qty ≤ 0`) drives quick-add hiding, the out-of-stock ribbon, the GMC feed, and schema.org `InStock`/`OutOfStock` markup. A back-in-stock subscription (`/shop/add/stock_notification`) appends a partner to `stock_notification_partner_ids`; an `ir.cron` (`_send_availability_email`) mails subscribers when the product is back and clears the M2M.
- **Routes:** 2, both `auth='public'` jsonrpc — `/shop/add/stock_notification` (waitlist) and the overridden `/website_sale/get_combination_info` (product-page availability recompute).
- **Views/Security:** no new view *records* (~390 XML LOC extend `website_sale`/`stock` forms in place); **0 ACLs / 0 record rules / 0 groups** — reuses parents' security; controller writes use `sudo()`.
- **Frontend (static, gap #3):** 10 JS files, 0 OWL components, 1 registry add; the availability UX is delivered by **patching** `website_sale`'s `WebsiteSale.prototype` (stock-notification handlers + post-add refresh), `Product`/`ProductCard`/`ProductProduct` and the configurator dialogs so the green/red state and qty caps follow `free_qty` live.

## Value-Configuration Classification

**Value model: `network` · activity_class: `primary` · APQC: 3.0 Market and Sell Products and Services.** As an extension of the `website_sale` storefront it inherits its value-network configuration — the online shop mediates many anonymous/portal visitors over shared catalog/channel infrastructure (Stabell & Fjeldstad). This module enriches that sell-side channel with real-time inventory signalling and demand-side guard-rails (availability display, low-stock thresholds, cart clamping, checkout gating, back-in-stock waitlist). It is **primary** (it directly shapes what a shopper can buy), classified **3.0 Market and Sell** like `website_sale`. A secondary **4.x Deliver** facet exists only as a touchpoint: the number it reads is `stock` `free_qty` for the website warehouse and a confirmed cart still flows into the `sale_stock` delivery chain (`stock.picking.website_id`) — but the module itself only *reads* stock to gate selling and performs no fulfilment.

## Business Architecture (confidence-tagged)

- **Capabilities** *(inferred)*: Real-Time Stock Display, Out-of-Stock Sales Policy, Cart Over-Order Prevention, Low-Stock/Out-of-Stock Messaging & Ribbons, Back-in-Stock Notification, Shop-Warehouse Selection.
- **Value streams** *(inferred)*: Browse-to-Order **availability leg** (live `free_qty` → cart clamped to on-hand → checkout re-check gates payment → order into `sale_stock`); out-of-stock → back-in-stock re-engagement.
- **Information concepts** *(auto)*: `product.template`, `product.product`, `sale.order`, `sale.order.line`, `website`, `stock.picking`.
- **Policies** *(inferred)*: `allow_out_of_stock_order` (per-product + website default) blocks/permits out-of-stock ordering; `available_threshold`/`show_availability` govern display; `_verify_updated_quantity` clamps, `_check_cart_is_ready_to_be_paid` gates checkout, the cron mails waitlists; `website.warehouse_id` selects the availability source.
- **Organization** *(auto)*: none (no new groups). **Products** *(auto)*: `product.template`/`product.product`/`product.combo` (availability-managed).
- **Strategy** *(human)*: `null`.

## Fit-to-Standard

**Out-of-box:** live product-page availability (`free_qty`, website warehouse); per-product "Sell when Out-of-Stock" + website default; configurable low-stock threshold and translatable out-of-stock message; cart qty capped to on-hand with `shop_warning`; checkout blocked on shortage; out-of-stock ribbon + schema.org/GMC availability; back-in-stock email waitlist; website source-warehouse selection. **Typical gaps:** multi-warehouse/per-location availability (→ `website_sale_collect`); true reservation of cart stock (cart is checked, not reserved, until confirmation); pre-order/lead-time messaging; bespoke ATP rules (e.g. show `virtual_available` instead of `free_qty`). **Drive (live):** `env['website'].get_current_website()._get_product_available_qty(p)` and `p._is_sold_out()` in `odoo shell`; `curl` jsonrpc `/shop/add/stock_notification` to subscribe.

## How to Drive It

Use the **run-odoo** skill. The storefront is public; availability is read off `stock` `free_qty`.

- `env['product.template'].search([('allow_out_of_stock_order','=',False)]).mapped(('name','show_availability','available_threshold'))` — products under stock control.
- `w = env['website'].get_current_website(); p = env['product.product'].search([('is_storable','=',True)], limit=1); print(w._get_product_available_qty(p), p._is_sold_out())` — the exact availability number the page shows.
- `env['product.product'].search([('stock_notification_partner_ids','!=',False)]).mapped('name')` — products with a back-in-stock waitlist.
- `curl` jsonrpc `http://localhost:8069/shop/add/stock_notification {product_id, email}` — subscribe to back-in-stock (auth=public).

## Open Questions

- **Reservation vs check:** cart qty is checked against `free_qty` at add and at checkout but **not reserved**, so two concurrent carts can both pass `_verify_updated_quantity` for the same units; final arbitration is only at order confirmation/procurement (`sale_stock`).
- How `website_sale_collect`/pickup overrides `_get_shop_warehouse_id`/`_get_free_qty` to use the chosen delivery warehouse rather than `website.warehouse_id`.
- Whether `free_qty` (vs `virtual_available`) is always the right ATP signal for backorder/MTO products, given the storefront reads `free_qty` only.

---
*Provenance: structural facts from `extract_module.py` (`facts/website_sale_stock.facts.json`) + `extract_frontend.py` (`frontend/website_sale_stock.frontend.json`); behavioral notes are code-read from `addons/website_sale_stock/controllers/{main,variant,website_sale}.py`, `models/{product_template,product_product,sale_order,sale_order_line,website,product_ribbon,product_feed,product_combo,res_config_settings,stock_picking}.py`, and `static/src/interactions/website_sale.js` + `static/src/xml/website_sale_stock_product_availability.xml`. Odoo 19.0.*
