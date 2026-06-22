# website_sale_comparison — Architecture Brief

*Odoo 19.0 · category Website/Website · `auto_install=true` on `website_sale` · DEEP record*

## 1. Overview

`website_sale_comparison` (Product Comparison) lets eCommerce shoppers compare
products side-by-side on the storefront. It renders an attribute comparison
table at `/shop/compare` that aligns each product's attribute values row-by-row
and groups them into merchant-curated sections. It is a thin, auto-installed
add-on of `website_sale`: 4 ACLs, 2 routes, ~540 py LOC, one new model plus
three model extensions, with most of the UX delivered as frontend OWL/JS.

## 2. Domain & Data Model

- **product.attribute.category** (new): `name`, `sequence` (indexed),
  `attribute_ids` (one2many to `product.attribute`). `_order = sequence, id`.
  This is the comparison/spec **grouping** concept — sections in the table.
- **product.attribute** (extension): adds `category_id` ("eCommerce Category"),
  the back-link that files an attribute under a comparison section.
- **product.product / product.template.attribute.line** (extensions): add no
  fields, only helper methods that assemble the comparison/spec grids.

ERM: `product.attribute.category 1—* product.attribute`; compared
`product.product` rows resolve to `product.template.attribute.value` per
attribute.

## 3. Services / Routes

- `GET /shop/compare` (http, public) — renders the comparison table. Reads a
  `products` CSV of `product.product` ids from the **query string**, filters to
  digits, redirects to `/shop` if empty, and uses `search([('id','in',ids)])`
  (not `browse`) so the public read ACL is enforced per record.
- `/shop/compare/get_product_data` (jsonrpc, public) — returns per-product
  price/display data (`display_name`, `website_url`, image_1024 url, `price`,
  `currency`, strikethrough/`compare_list_price`) via
  `_get_combination_info_variant()` to hydrate the compare bar.

## 4. Behavioral Notes (code-read)

- **Comparison-grid builder** — `product.product._prepare_categories_for_display`
  nests `OrderedDict` category → attribute → {product: [values]} over the
  products' valid attribute lines; uncategorized attributes go to an empty
  category bucket; categories/attributes are `.sorted()`; `no_variant`
  attributes fall back to `attribute_line_ids.value_ids` (show all values). This
  is the actual row/column attribute-value diffing.
- **`/shop/compare` rendering** — server holds no session list; the id set is
  supplied by the frontend through the query string and access-checked via
  `search`.
- **Grouping + spec-table reuse** — `product.attribute.category` +
  `category_id` model the sections; `product.template.attribute.line.`
  `_prepare_categories_for_display(_in_specs_table)` reuses the same grouping
  on the product page, filtering single custom-value lines.
- **Compare list = browser cookie (gap #3)** — `comparison_product_ids` cookie
  (JSON array, MAX 4) with add/remove/clear + EventBus; the `product_comparison`
  interaction wires the add/remove buttons (creating variants via
  `/sale/create_product_variant`), enforces max-4/dup warnings, mounts the
  `ProductComparisonBottomBar`, and redirects to `/shop/compare?products=<csv>`.
  This client state is invisible to Python metadata.

## 5. Frontend (gap #3) & Integrations (gap #7)

- 5 JS files, 4 XML templates; OWL components `ProductComparisonBottomBar` and
  `ProductRow`; 2 `public.interactions` registry adds (`comparison_page`,
  `product_comparison`); bundles `web.assets_frontend` (4),
  `web.assets_tests` (1), `website.website_builder_assets` (1). No patches,
  no services.
- Integrations: none — no HTTP call sites, no SDK imports, no API keys, no
  external endpoints.

## 6. Business Architecture

- **Capabilities** (inferred): side-by-side product comparison; attribute
  categorization for merchandising; add/remove to a comparison list;
  comparison-aware storefront engagement (compare bar).
- **Value stream** (inferred): Browse-to-Compare-to-Decide — add to compare →
  view aligned attribute/price table → proceed to product page / cart;
  supports the `website_sale` Browse-to-Order stream.
- **Organization** (auto): `base.group_public` / `base.group_portal` /
  `base.group_user` read attribute categories; `sales_team.group_sale_manager`
  has full CRUD.
- **Policies** (inferred): 4 ACLs / 0 record rules; client cap of 4 products,
  de-dup on add; `search()` enforces per-record public read.
- **Strategy**: null (human). **Metrics**: comparison engagement is not
  server-modelled (would need web analytics).

## 7. Classification

- **value_model: network** — storefront merchandising/engagement feature of the
  `website_sale` value network; mediates many anonymous/portal visitors over
  shared catalog infrastructure rather than running a document chain. Inherits
  `website_sale`'s network classification.
- **activity_class: primary** — customer-facing, revenue-channel functionality
  that supports the purchase decision.
- **apqc_category: 3.0 Market and Sell Products and Services** — eCommerce
  merchandising on the online sell-side channel.

## 8. Fit-to-Standard & Open Questions

Out-of-box: public comparison page; attribute alignment grouped by configurable
eCommerce category; add/remove buttons; cookie list capped at 4; live compare
bar; spec-table reuse; `no_variant` shows all values. Common gaps: persistent /
cross-device lists, comparing >4 or across taxonomies, comparison analytics,
non-attribute comparison facts, bespoke table layout. Open questions: cookie ↔
logged-in partner reconciliation; pricelist/discount context in the compare
bar; whether merchants actually curate attribute categories.
