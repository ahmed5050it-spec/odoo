# website_sale_wishlist — Reverse-Engineering Brief

`website_sale_wishlist` (manifest name **Shopper's Wishlist**, category Website/Website, `application: false`, `auto_install: true`) adds the storefront "add to wishlist" feature to the Odoo online shop: shoppers mark `product.product` variants they want to buy later and find them again on a dedicated `/shop/wishlist` page. It is a thin **engagement add-on** that decorates `website_sale` (its only dependency) — one own model (`product.wishlist`) plus five small extensions, four public routes, ~350 Python LOC and ~682 XML LOC. The wishlist is saved per customer/visitor and is designed to drive return visits and convert saved interest into cart orders.

## Role & Dependencies

Why it depends on the listed module:
- **website_sale** — provides the eCommerce storefront, the public/portal users, the published `product.template`/`product.product` catalog, pricelists/currency per website, and the `/shop/cart` flow the wishlist feeds. The wishlist is meaningless without the shop.

Capability added on top: **save-for-later**. A shopper can add/remove products to a personal list that survives across sessions, works for anonymous visitors (session-scoped) and logged-in customers (partner-scoped), remembers the price at add-time, and offers a one-click **move-to-cart** back into the browse-to-order flow.

## Data Model (the ERM)

| _name | _description | #fields | Key relations |
|-------|-------------|---------|---------------|
| product.wishlist | Product Wishlist | 7 | partner_id→res.partner, product_id→product.product, website_id→website, pricelist_id→product.pricelist, currency_id→res.currency |

Plus five `_inherit`-without-`_name` extensions: `product.product` and `product.template` (`_is_in_wishlist` helpers), `res.partner` (`wishlist_ids` One2many), `res.users` (merge session wishlist on login), and `website` (four wishlist-page layout settings: grid/mobile columns, gap, design classes). The single own entity, **`product.wishlist`**, is the join: one row per (product, owner) — enforced by a `UNIQUE(product_id, partner_id)` SQL constraint — carrying the `website_id` (required, `ondelete='cascade'`), the `pricelist_id`, and a `price` Monetary snapshot of the variant price when it was added (currency related to `website_id.currency_id`).

## Behavior & Surfaces

- **Routes:** 4, all `auth='public'`, `website=True`. One HTTP page route (`/shop/wishlist`) renders the wishlist QWeb template; three JSON-RPC routes drive the interactions: `/shop/wishlist/add`, `/shop/wishlist/remove/<int:wish_id>`, and `/shop/wishlist/get_product_ids` (readonly, used to mark already-wishlisted products in the grid).
- **Views:** none in the backend (0 form/list/kanban/search). The entire UX is **frontend QWeb + public interactions**: 6 JS files, 0 OWL components, 4 `public.interactions` registry adds (`add_product_to_wishlist_button`, `product_detail`, `product_wishlist`, `wishlist_navbar`); 3 entries in `web.assets_frontend`, a `web.assets_tests` bundle, and a `website.website_builder_assets` bundle exposing wishlist-page grid options in the builder.
- **Security posture:** 4 ACLs + 2 record rules, 0 new groups. Public users get read-only access (session wishlist via sudo); portal and internal users get CRUD. Record rule **"See own Wishlist"** limits portal/internal users to `partner_id = user.partner_id`; **"See all wishlist"** grants `sales_team.group_sale_manager` full visibility.

Behavioral facts read from source (beyond metadata):
- **per partner / per website:** `/shop/wishlist/add` reads the variant price via `_get_combination_info_variant()['price']` and calls `product.wishlist._add_to_wishlist(...)`; `/shop/wishlist/remove/<wish_id>` unlinks one entry.
- **guest vs logged-in:** `request.website.is_public_user()` branches — anonymous wishes are created `sudo()` with `partner_id=False` and the id is pushed into `request.session['wishlist_ids']`; logged-in wishes are owned by `request.env.user.partner_id` and scoped to the website. `current()` filters out unpublished / non-add-to-cart products.
- **merge on login:** `res.users._check_credentials` → `_check_wishlist_from_session()` reassigns session wishes to the partner, dropping duplicates to respect the UNIQUE constraint, then pops `wishlist_ids`.
- **price snapshot:** the as-saved `price` + `pricelist_id` are kept so the wishlist page can compare saved vs current price (price-drop indication).
- **move-to-cart + GC:** the wishlist page interactions push products into the `website_sale` cart; `@api.autovacuum _gc_sessions` purges partner-less guest wishlists older than ~5 weeks.

Fit-to-standard out of the box: add-to-wishlist button on product pages/tiles, a per-customer wishlist persisted across sessions, anonymous session wishlist merged on login, the `/shop/wishlist` page (list + remove + add-to-cart), a price snapshot vs current price per stored pricelist/currency, a configurable wishlist grid in the website builder, and GC of stale guest wishlists. Common gaps usually needing config/dev: wishlist **sharing** / public or social wishlists, **multiple named wishlists** or gift registries, automated **price-drop / back-in-stock notification emails** (only the price snapshot is stored — no mailing here), and wishlist **demand analytics** beyond raw `product.wishlist` rows.

## Value-Configuration Classification

- **value_model: network** (primary). The wishlist is a storefront **mediation/engagement feature of the `website_sale` value network**: it lets the shared eCommerce platform remember each visitor's product interest (session-scoped when anonymous, partner-scoped once logged in, merged on login) and re-engage them. Its value logic is *network* (Stabell & Fjeldstad) — increasing the value of the website_sale platform through matchmaking and return-visit/conversion engagement over shared channel infrastructure — not a linear transform chain. It owns no order/document chain; it decorates website_sale's catalog and cart and hands converted interest back to the `/shop/cart` browse-to-order flow.
- **activity_class: primary** — a revenue- and customer-facing online merchandising/engagement capability on the sell-side channel, not a back-office support function.

## APQC PCF Hint

**3.0 Market and Sell Products and Services** — the wishlist is an **eCommerce merchandising / customer-engagement** capability: it captures and retains buyer interest on the online channel and nudges it toward purchase (move-to-cart), supporting the sell-side processes; any resulting order is handed to `website_sale` → the sale chain downstream.

## How to Drive It

Use the **run-odoo** skill. The wishlist page and routes are public, so they can be curled without auth; entries can be inspected via `odoo shell`.

- `curl -s http://localhost:8069/shop/wishlist` — render the wishlist page (auth=public).
- `env['product.wishlist'].search([], limit=5).mapped(('partner_id.name','product_id.display_name','price','website_id.name'))` — list saved wishlist entries.
- `env['product.wishlist'].search([('partner_id','=',False)])` — guest/session wishlists awaiting merge-on-login or autovacuum GC.
- `curl jsonrpc /shop/wishlist/add {product_id}` — add a product variant to the wishlist (auth=public).

## Open Questions

- Whether the stored `price`/`pricelist_id` snapshot drives a visible price-drop badge on the wishlist page or is informational only (template-level, not in the Python facts).
- How move-to-cart resolves product variants/options into the `website_sale` `sale.order.line` (delegated to website_sale's cart-add path).
- Whether any downstream module (e.g. marketing/automation) consumes `product.wishlist` as a re-engagement trigger; none is present in this module.

---
*Provenance: structural facts from `extract_module.py` (`facts/website_sale_wishlist.facts.json`) + `extract_frontend.py` (`frontend/website_sale_wishlist.frontend.json`); behavioral notes are code-read from `addons/website_sale_wishlist/models/product_wishlist.py`, `controllers/main.py`, `models/res_users.py`, `models/website.py`. Odoo 19.0.*
