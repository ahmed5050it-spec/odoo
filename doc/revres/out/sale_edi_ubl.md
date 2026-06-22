# sale_edi_ubl — Architecture Brief

> Module: `sale_edi_ubl` · Category: Sales/Sales · Depends: `sale`, `account_edi_ubl_cii` · `auto_install: true`
> Value model: **chain** · Activity class: **primary** · APQC: **3.0 Market and Sell Products and Services**
> Odoo 19.0 · Facts: `doc/revres/facts/sale_edi_ubl.facts.json` · Frontend: `doc/revres/frontend/sale_edi_ubl.frontend.json`

## 1. Summary

`sale_edi_ubl` is the **SELL-side electronic-ordering bridge**: it serialises a
`sale.order` into a **Peppol BIS Ordering 3** UBL document and, inbound, turns a
customer's BIS3 purchase-order XML (or a PDF carrying embedded XML) into a
`sale.order`. It owns **one AbstractModel** — `sale.edi.xml.ubl_bis3`
(`_inherit` `account.edi.xml.ubl_bis3`, **32 methods**, no fields) — reusing the
`account_edi_ubl_cii` UBL machinery but pointing it at the **sales order**
document instead of the invoice. Two small inherits wire it in: `sale.order`
(file-type sniffing, decoder, builder registration) and `product.product`
(variant matching by `ExtendedID`). On import it **retrieves/creates the buyer
and delivery partner**, matches products (incl. variants), discards the buyer's
PO note/prices, and **re-prices lines from the seller's own pricelist**.
Footprint: **1 own model + 2 inherits, 0 routes, 0 ACLs, 0 views, ~589 py LOC,
0 JS**. The substance metadata misses is entirely in the UBL build/parse Python
(export node tree, inbound dispatch, partner/product matching, seller re-pricing).

## 2. Structure (evidence)

- **Models (1 own + 2 inherit):** `sale.edi.xml.ubl_bis3` (AbstractModel,
  `_inherit` `account.edi.xml.ubl_bis3`, "Sale BIS Ordering 3.5", 0 fields,
  ~32 methods — the builder/importer); `sale.order` (no fields — `_get_edi_builders`,
  `_get_import_file_type`, `_get_edi_decoder`, `_create_activity_set_details`,
  `_get_line_vals_list`); `product.product` (no fields — variant `ExtendedID`
  search plan).
- **Routes:** **0** — it rides the existing Sales/account import surface.
- **Security:** 0 ACLs, 0 record rules, 0 groups — an abstract engine with no
  stored records of its own.
- **Views:** **none** (`views {}` in facts). UI is the Sales order list
  upload/create-from-attachment flow and the portal/print Download-Order action
  exposed by `_get_edi_builders`.

## 3. Frontend (gap #3)

**0 JS / 0 XML templates, no OWL components, no registry adds, no asset bundles**
(`present:false`). A headless EDI builder driven entirely from the existing Sales
UI. (Verbatim `frontend_gap3`: `present:false`, all counts 0.)

## 4. Behavior (beyond metadata)

- **Outbound BIS3 Order export (code-read):** `_export_order(sale_order)` builds a
  structured `document_node` via `_get_sale_order_node`, renders it with
  `dict_to_xml(template=Order, nsmap=...)` and returns UTF-8 bytes.
  `_get_sale_order_node` prepares base lines from `order_line` (non-`display_type`)
  through `account.tax._add_tax_details_in_base_lines` + rounding, forces item net
  prices positive (`[BR-27]`), turns "emptying" taxes into allowance/charge lines,
  then emits the header (CustomizationID `urn:fdc:peppol.eu:poacc:trns:order:3`,
  ProfileID `…:bis:ordering:3`, `cbc:ID`=order name, IssueDate=`create_date`,
  OrderTypeCode `220`, DocumentCurrencyCode, ValidityPeriod/EndDate=`validity_date`,
  OriginatorDocumentReference=`client_order_ref`), BuyerCustomerParty,
  SellerSupplierParty, Delivery, PaymentTerms, OrderLine items, AllowanceCharge
  (incl. early-payment-discount), TaxTotal and an **AnticipatedMonetaryTotal**.
  (Round-trip verified by `tests/test_sale_order_edi_gen.py` against
  `tests/data/test_so_edi.xml`.)
- **Inbound dispatch (code-read):** `sale.order._get_import_file_type` sniffs the
  XML tree for CustomizationID == `urn:fdc:peppol.eu:poacc:trns:order:3` →
  `'sale.edi.xml.ubl_bis3'` (else `super()`); `_get_edi_decoder` returns
  `{'priority':20, 'decoder': sale.edi.xml.ubl_bis3._import_order_ubl}`;
  `_get_edi_builders` appends the builder to the (empty in core `sale`) list so it
  appears on the Download-Order surface. Uploading/pasting a BIS3 order file routes
  it here.
- **Inbound XML → sale.order vals (code-read):** `_retrieve_order_vals` calls
  `super()` then **pops `note`** (the SO Terms & Conditions win over the PO note),
  retrieves the **BuyerCustomer** partner via `_import_partner` (VAT / Peppol
  EAS+endpoint matching) into `partner_id`, sets `client_order_ref`=ID,
  `origin`=`QuotationDocumentReference/ID`, and a **Delivery** partner into
  `partner_shipping_id`. It imports allowance/charges and lines from
  `./OrderLine/LineItem` (`tax_type='sale'`), adapts each to `sale.order.line`
  (drops `deferred_start/end_date` and any `discount`), logs
  *"Could not retrieve the product named: …"* when no product matched, appends
  allowance/charge lines, and writes `order_line` as `[Command.create(...)]`. The
  parent `_import_order_ubl` writes the vals, posts a chatter note and a **to-do
  activity** listing the logs.
- **Seller re-pricing (code-read):** `_import_order_ubl` override, after `super()`,
  takes `order.order_line.filtered('product_id')` and calls `_compute_price_unit()`
  then `_compute_discount()`. Since the PO price/discount were stripped during
  `_retrieve_order_vals`, this **re-derives price and discount from the seller's
  own pricelist** for matched products — the seller's pricing, not the buyer's PO
  price, governs the resulting quotation.
- **Model-adaptation + variant matching (code-read):** `_retrieve_line_vals`
  renames the base `quantity` key to `product_uom_qty`; `_get_product_xpaths` adds
  `variant_barcode` (`Item/StandardItemIdentification/ExtendedID`) and
  `variant_default_code` (`Item/SellersItemIdentification/ExtendedID`).
  `product.product._get_product_domain_search_order` /
  `_get_retrieval_product_search_plan` inject ExtendedID lookups (`bisect.insort`
  at priorities 12/14) so `StandardItemIdentification.ID` matches
  `product.template.barcode` while `ExtendedID` matches the **variant**.
  `sale.order._get_line_vals_list` puts extra lines at `sequence=0` to sort above
  the real order lines.
- **Frontend (static, gap #3):** 0 JS / 0 OWL — backend only.

## 5. IT architecture

- **Application:** Peppol BIS3 order EDI builder/importer for `sale.order`,
  extending `account_edi_ubl_cii`.
- **Data objects:** `sale.edi.xml.ubl_bis3` (own AbstractModel) + inherits on
  `sale.order` and `product.product`.
- **Key relations:** `sale.edi.xml.ubl_bis3 → account.edi.xml.ubl_bis3`
  (`_inherit`); the builder reads/writes `sale.order` + `sale.order.line` and
  matches `res.partner` (BuyerCustomer/Delivery) and `product.product` (variant
  ExtendedID).
- **Flows:** `_export_order` → BIS3 Order XML bytes (portal/print download);
  inbound XML/PDF → `_get_import_file_type` → `_get_edi_decoder` →
  `_import_order_ubl` → `sale.order` + lines (+ partner retrieve/create, product
  match); `_import_order_ubl` → `_compute_price_unit`/`_compute_discount` re-derive
  seller pricing; `_retrieve_order_vals` drops the PO note and logs unmatched
  products as a to-do activity.

## 6. Business architecture

- **Capabilities (inferred):** export a sales order as Peppol BIS Ordering 3 UBL;
  import an inbound BIS3 PO XML/PDF into a `sale.order` (seller side);
  retrieve-or-create the buyer and delivery partner; match ordered products (incl.
  variants via ExtendedID); re-price imported lines from the seller's pricelist.
- **Value streams (inferred):** *Outbound* (draft/confirmed `sale.order` → BIS3 UBL
  Order XML → made available to the customer) and *Inbound* (customer BIS3 order
  XML/PDF → format detection → `sale.order` with buyer/delivery partner, matched
  products and seller-derived pricing).
- **Information concepts (auto):** `sale.order` (the order as a BIS3 document),
  `sale.order.line` (↔ UBL OrderLine/LineItem), `res.partner` (Buyer/Delivery),
  `product.product` (ordered item, matched by ID/ExtendedID).
- **Organization (auto):** none (no new groups).
- **Products (auto):** `product.product` matched from
  StandardItemIdentification/SellersItemIdentification, incl. variant ExtendedID.
- **Policies (inferred):** order format fixed to Peppol BIS Ordering 3 (routing
  keyed on its CustomizationID); imported PO note discarded for the SO Terms &
  Conditions; imported line prices/discounts re-derived from the seller pricelist;
  item net price forced non-negative (`[BR-27]`) with EN16931/PINT base-line
  rounding before serialisation.
- **Metrics (inferred):** none of its own.
- **Strategy:** `null` (human).

## 7. Classification

- **Value model: chain** — the module operates on the **sales order** document at
  order-capture time, advancing the **quote-to-cash** chain (Stabell & Fjeldstad
  *chain*; Porter primary *Marketing & Sales*). It depends on `sale`, lives in
  category *Sales/Sales*, and reads/writes `sale.order` + `sale.order.line` — not
  invoices.
- **Activity class: primary.**
- **APQC: 3.0 Market and Sell Products and Services** — electronic order capture /
  acknowledgement, the order-management (3.5 sales-order) leg. **Contrast with its
  parent** `account_edi_ubl_cii`, which is a *support/compliance* engine around
  `account.move` and classified **support / 9.0 Manage Financial Resources**:
  `sale_edi_ubl` reuses that UBL machinery (it `_inherit`s
  `account.edi.xml.ubl_bis3`) but applies it to the **sell-side order**, so it
  follows the sales order it serves. **9.0 Financial rejected** — the artefact is a
  sales order, not an invoice/ledger entry; the invoice-side EDI deliberately
  stays in `account_edi_ubl_cii`. (APQC number matches name: 3.0 = Market and Sell;
  the invoice-EDI sibling sits at 9.0, not chosen here.)

## 8. Fit-to-Standard

- **Standard:** export a `sale.order` as Peppol BIS Ordering 3 (UBL Order,
  OrderTypeCode 220); auto-detect inbound BIS3 order files from CustomizationID and
  import into a `sale.order`; retrieve-or-create buyer/delivery partners (VAT /
  Peppol EAS+endpoint); match products by ID and variant ExtendedID; re-derive
  imported line `price_unit`/`discount` from the seller pricelist; keep the
  seller's Terms & Conditions over the PO note; log unmatched products as an
  activity.
- **Typical fits:** B2B/e-procurement where the customer sends a BIS3 PO and the
  seller wants it auto-converted to a `sale.order`; returning a BIS3 order document
  to a customer from portal/print; catalogs using variant `ExtendedID`; sellers who
  must re-price an incoming PO against their own pricelist.
- **Common gaps:** **only Peppol BIS Ordering 3** is supported (no Order-Response,
  despatch advice or other order CIUS); **actual Peppol Access Point transmission**
  is out of scope (this only builds/parses XML — a separate Peppol module delivers);
  products that fail ID/ExtendedID matching are left without a `product_id` (logged)
  and need manual resolution; **imported PO pricing is overwritten** by the seller
  pricelist, so honouring buyer-agreed prices needs customisation.
- **Drive:**
  `so = env['sale.order'].search([('state','!=','draft')], limit=1);
  xml = env['sale.edi.xml.ubl_bis3']._export_order(so); print(xml[:400])` (BIS3
  Order XML head); `print(env['sale.order']._get_edi_builders())` (includes the
  builder); or in the Sales order list use Upload / New-from-file with a BIS3 order
  XML (or a PDF with embedded XML) to create a `sale.order` with partner, lines and
  seller pricing.
