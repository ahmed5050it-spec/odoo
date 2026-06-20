# website_sale — Reverse-Engineering Brief

`website_sale` (manifest name **eCommerce**, category Website/Website, `application: true`, `auto_install: false`) is the Odoo online storefront: it sells `product.template` records over the web and turns each web session into a `sale.order`. It is the **bridge** that joins two value-configurations — it sits on top of `website` (the CMS/value-network) and `sale` (the order chain), wiring the storefront, cart, checkout and online payment together so anonymous and portal visitors can self-serve an order. It is a large module (10 own models, 26 inherit-only extensions, 58 routes, ~18.8k Python LOC, ~12k XML LOC) and a true integration hub rather than a leaf bridge.

## Role & Dependencies

Why it depends on each listed module (top of `depends`):
- **website** — provides the CMS, public users, snippets and the `/shop` frontend it renders into.
- **sale** — provides `sale.order`/`sale.order.line`; website_sale reuses the quotation as the eCommerce cart.
- **website_payment** — the online payment leg (`payment.provider`/`payment.transaction`) used at `/shop/payment`.
- **delivery** — shipping carriers and rate computation chosen during checkout.
- **portal_rating** — customer reviews/ratings on product pages (`rating.mixin` on `product.template`).
- **digest / website_mail** — KPI digests (eCommerce total) and templated cart-recovery / confirmation emails.

Capability added on top: a **public, browsable, searchable catalog + cart + multi-step checkout + online payment**, plus merchandising (categories, ribbons, cross/up-sell), abandoned-cart recovery, and a Google Merchant Center feed.

## Data Model (the ERM)

| _name | _description | #fields | Key relations |
|-------|-------------|---------|---------------|
| product.template | (ext) storefront product | 19 | public_categ_ids→product.public.category, website_ribbon_id→product.ribbon, product_template_image_ids→product.image |
| sale.order | (ext) eCommerce cart | 8 | website_id→website, website_order_line→sale.order.line |
| product.public.category | Website Product Category | 14 | parent_id (self), product_tmpl_ids→product.template |
| product.image | Product Image | 8 | product_tmpl_id→product.template, product_variant_id→product.product |
| product.feed | Product Feed (GMC) | 12 | website_id→website, pricelist_id→product.pricelist |
| website.checkout.step | Website Checkout Step | 6 | website_id→website |

Central/aggregate models: the **extended `sale.order`** (the cart aggregate, +52 methods here) and the **extended `product.template`** (the merchandised catalog item, +52 methods). The module is dominated by **mixin/extension** records — 26 `_inherit`-without-`_name` extensions of `website`, `sale.order(.line)`, `product.product`, `res.config.settings`, `crm.team`, `digest`, `account.move`, etc. — confirming it is a bridge that decorates existing hubs rather than introducing a big new schema. Field-type distribution is **attribute-/config-heavy** (29 Char, 25 Selection, 24 Boolean, 17 Integer) over relational (28 Many2one, 9 Many2many): most new fields are storefront layout/visibility toggles and `res.config.settings` switches, not new entities.

## Behavior & Surfaces

- **Routes:** 58, the largest surface of any sale-side module. Mostly `auth='public'`; HTTP routes render storefront pages (`/shop`, `/shop/cart`, `/shop/checkout`, `/shop/address`, `/shop/payment`, `/shop/confirmation`, `/gmc.xml`) while JSON-RPC routes drive the SPA-like interactions (`/shop/cart/add|update|quantity|clear`, configurator, delivery-method, pickup-location).
- **Views:** form (12), list (6), kanban (3), search (3), graph (1) — but the real UX is **frontend QWeb + OWL/JS** (83 JS files, 6 OWL components, ~38 registry registrations dominated by `public.interactions` for cart/checkout/snippets, plus `cart` and `cartNotificationService` services; 46 entries in `web.assets_frontend`). Backend views are for catalog/config admin; shopping happens on the website.
- **Security posture:** 71 access rules, 6 record rules, 5 groups — record rules enforce per-website publish/visibility scoping and the `ecommerce_access` (public vs logged-in) gate.

Behavioral facts read from source (beyond metadata):
- `/shop/cart` renders a draft `sale.order` as the cart; `request.cart` *is* the cart. `_cart_add` → `_cart_find_product_line` (dedupe) → `_cart_update_line_quantity` or `_create_new_cart_line`/`_prepare_order_line_values` (variant resolution).
- Checkout is a state machine over one order: `/shop/checkout` → `/shop/address` → `/shop/payment` → `/shop/payment/validate` (`_validate_order` confirms the order → state `sale`) → `/shop/confirmation`.
- Abandoned-cart recovery: `is_abandoned_cart` + `_cart_recovery_email_send` send the website template and set `cart_recovery_email_sent`.

## Value-Configuration Classification

- **value_model: network** (primary). website_sale is a **BRIDGE** connecting **website (network) → sale (chain) → payment (network)**. Its own value logic is mediation/matchmaking over shared channel infrastructure (publish, browse, search, cart, recover) — Stabell & Fjeldstad *value network* — serving many anonymous/portal visitors over a common platform. It is not classified `chain` because it does not itself perform the linear transform-to-order of `sale`; instead it *feeds* that chain: at `/shop/payment/validate` it calls `sale.order._validate_order` to emit a confirmed order into the sale chain (delivery + invoice), while `website_payment` supplies the payment-network leg.
- **activity_class: primary** — a revenue- and customer-facing sales channel, not a back-office support function.

## APQC PCF Hint

**3.0 Market and Sell Products and Services** — website_sale is the **eCommerce sell-side channel** (online storefront, cart, self-service order capture); it realizes the "sell products/services" processes through a web channel, with the resulting order handed to the sale chain (3.5 order management) downstream.

## How to Drive It

Use the **run-odoo** skill. The storefront is public, so it can be curled without auth; carts and catalog can be inspected via `odoo shell`.

- `curl -s http://localhost:8069/shop` — render the public storefront (auth=public).
- `env['sale.order'].search([('website_id','!=',False)], limit=5).mapped(('name','state','cart_quantity'))` — list eCommerce carts/orders.
- `env['sale.order'].search([('is_abandoned_cart','=',True)]).mapped('partner_id.email')` — abandoned carts eligible for recovery.
- `env['product.template'].search([('is_published','=',True)], limit=5).mapped('name')` — published storefront products.

## Open Questions

- Exact `sale.order._validate_order` semantics vs `sale.action_confirm`: which downstream `stock.picking`/`account.move` documents an eCommerce order creates, and when invoicing is automatic (not in static facts).
- How the `website_payment` `payment.transaction` lifecycle (authorize/capture/error) gates `_validate_order` and the confirmation email.
- The full variant-generation path: how `/shop/cart/add` + configurator routes resolve dynamic/`no_variant` combinations into the final `sale.order.line` product.

---
*Provenance: structural facts from `extract_module.py` (`facts/website_sale.facts.json`) + `extract_frontend.py` (`frontend/website_sale.frontend.json`); behavioral notes are code-read from `addons/website_sale/controllers/main.py`, `models/sale_order.py`, `models/product_template.py`. Odoo 19.0.*
