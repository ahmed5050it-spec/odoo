# pos_edi_ubl — Architecture Brief

> Module: `pos_edi_ubl` · Category: Sales/Point of Sale · Depends: `point_of_sale`, `account_edi_ubl_cii` · `auto_install: false`
> Value model: **support** · Activity class: **support** · APQC: **9.0 Manage Financial Resources**
> Odoo 19.0 · Facts: `doc/revres/facts/pos_edi_ubl.facts.json` · Frontend: `doc/revres/frontend/pos_edi_ubl.frontend.json` · DEEP record.

## 1. Summary

`pos_edi_ubl` is a **headless UBL 2.1 e-invoice builder for Point of Sale orders** — the
POS counterpart to `account_edi_ubl_cii`'s invoice builders. It owns exactly one
`AbstractModel`, `pos.edi.xml.ubl_21` (`_inherit account.edi.xml.ubl_21`, **0 fields, 27
methods, 220 py LOC**), whose single public entry point `_export_pos_order(pos_order)`
serialises a `pos.order` into a structured UBL 2.1 *Invoice* / *CreditNote* XML document
and returns a `(xml_bytes, errors_set)` tuple. It reuses the parent's EN16931
tax-detail and monetary-total machinery (`_add_document_*` / `_get_document_*`,
`dict_to_xml`) but re-maps the parties, journal and totals from a till order instead of an
`account.move`. Crucially it is a **library, not a flow**: nothing in the module calls
`_export_pos_order`, attaches the XML, or transmits it — the only consumer in the tree is the
Jordan localisation `l10n_jo_edi_pos`, which subclasses the builder, submits the XML to the
JoFotara clearance API and stores it as an `ir.attachment` on the order. Footprint: **1 own
abstract model, 0 routes, 0 ACLs, 0 views, 0 JS, no data files**, `auto_install=false`. This
is fiscal/e-invoicing **compliance scaffolding** — the substance metadata misses lives
entirely in the export pipeline's POS→UBL mapping.

## 2. Structure (evidence)

- **Models (1 own, abstract):** `pos.edi.xml.ubl_21` (`_inherit ['account.edi.xml.ubl_21']`
  → `account.edi.xml.ubl_20` → `account.edi.ubl` → `account.edi.common`). No `_name` table,
  no fields; 27 methods, all node/value builders for the UBL document.
- **Routes:** **0** — no web/RPC surface.
- **Security:** 0 ACLs, 0 record rules, 0 groups — an `AbstractModel` invoked server-side by
  consumers in sudo context.
- **Views:** none; **0 XML/data files** (`xml_loc=0`). Any download/submit UI is added by the
  consuming localisation.

## 3. Frontend (gap #3)

**0 JS / 0 XML templates, no OWL components, no registry adds, no patches, no asset bundles**
(`present:false`). The module is a pure server-side serialisation library. `integrations_gap7`
is empty — the actual network call to a tax authority lives in the consumer
(`l10n_jo_edi_pos` → JoFotara), not here.

## 4. Behavior (beyond metadata)

- **`_export_pos_order(pos_order)` (code-read):** mirrors `account.edi.xml.ubl_20._export_invoice`
  but over a `pos.order`. Re-contextualises to the customer's `lang`, builds the `document_node`
  via `_get_pos_order_node`, evaluates `_export_pos_order_constraints` into an errors set, picks an
  Invoice/CreditNote template + `cac/cbc/ext` nsmap, renders with
  `odoo.addons.account.tools.dict_to_xml`, and **returns `(xml_bytes, errors_set)`** so an invalid
  order is reported, not silently shipped.
- **POS→UBL mapping (`_add_pos_order_config_vals` / `_add_pos_order_base_lines_vals`, code-read):**
  `document_type = 'invoice' if amount_total >= 0 else 'credit_note'`; `supplier =
  company_id.partner_id.commercial_partner_id`; `customer = partner_id`; `journal =
  config_id.invoice_journal_id`. Tax base lines come from `pos.order._prepare_tax_base_line_values()`
  then `account.tax._add_tax_details_in_base_lines` / `_round_base_lines_tax_details` — the same
  EN16931 tax machinery the invoice path uses, applied to raw POS lines.
- **POS-specific totals + overridable constraints (code-read):** the `LegalMonetaryTotal` node gets
  `cbc:PrepaidAmount = tax_exclusive_amount − amount_paid` and `cbc:PayableAmount = amount_paid`,
  encoding that a POS sale is already tendered at the till. `_export_pos_order_constraints` returns
  **`{}`** by design — the base builder imposes **no** business rules, leaving EN16931/clearance
  checks to the localisation. Product lines become `InvoiceLine`/`CreditNoteLine`; allowance/charge
  lines become `AllowanceCharge`s.
- **Engine vs caller (code-read):** `_export_pos_order` has **no caller inside this module**. The
  sole consumer is `l10n_jo_edi_pos` (`depends ['l10n_jo_edi','pos_edi_ubl']`): it subclasses
  `_name='pos.edi.xml.ubl_21.jo'`, calls `env['pos.edi.xml.ubl_21.jo']._export_pos_order(order)[0]`,
  base64-encodes the bytes, POSTs to JoFotara, and stores the returned XML + `EINV_QR` as an
  `ir.attachment` on the `pos.order`. The "attach/transmit" side-effects live in the localisation.
- **Frontend (static, gap #3):** none — server-side only.

## 5. IT architecture

- **Application:** headless UBL 2.1 e-invoice builder for POS orders; an abstract serialisation
  library extending `account_edi_ubl_cii`.
- **Data objects:** `pos.edi.xml.ubl_21` (AbstractModel only).
- **Key relations:** `pos.edi.xml.ubl_21 → account.edi.xml.ubl_21` (`_inherit`); the builder
  consumes `pos.order` (+ lines, `pos.config.invoice_journal_id`, supplier/customer `res.partner`,
  `res.currency`, `account.tax` details).
- **Flows:** `depends` `point_of_sale` (the order + `_prepare_tax_base_line_values`) and
  `account_edi_ubl_cii` (the node builders + `dict_to_xml`); `pos.order → _export_pos_order →
  document_node → (UBL XML bytes, errors)`. **No own side-effect** — the tuple is returned to a
  caller. Consumer flow: `l10n_jo_edi_pos` → JoFotara POST → `ir.attachment` on the order.

## 6. Business architecture

- **Capabilities (inferred):** serialise a POS order to a UBL 2.1 e-invoice/credit-note; reuse
  Accounting's EN16931 tax-detail/monetary machinery over POS lines; encode POS tendering
  (Prepaid/Payable); provide an overridable constraints + node-builder framework for POS
  e-invoicing localisations.
- **Value streams (inferred):** *Provide-POS-UBL-Builder* — a localisation subclasses the builder,
  calls `_export_pos_order`, and clears/attaches the validated XML (no end-to-end flow inside this
  module).
- **Information concepts (auto):** `pos.edi.xml.ubl_21`, `pos.order`, `account.edi.xml.ubl_21`.
- **Organization (auto):** none (no groups).
- **Products (auto):** none.
- **Policies (inferred):** `auto_install=false` (opt-in, unlike its auto-installed parent);
  sign-driven invoice/credit-note; empty constraints by design; product→line, allowance→AllowanceCharge.
- **Metrics (inferred):** none.
- **Strategy:** `null` (human).

## 7. Classification

- **Value model: support — support activity.** `pos_edi_ubl` adds no primary-chain value: it owns
  one tableless `AbstractModel` that only **serialises an already-rung `pos.order` into a legally
  structured UBL 2.1 document**. That is infrastructure for fiscal/e-invoicing compliance
  (Stabell & Fjeldstad *support*), not a value chain that converts inputs to a sold output. Its
  centre of gravity is the EN16931/UBL document model it inherits from `account_edi_ubl_cii`.
- **APQC: 9.0 Manage Financial Resources** — the financial-document/e-invoice exchange family,
  exactly where its parent `account_edi_ubl_cii` sits. **3.0 (Market & Sell) was rejected:** the
  module performs no selling and is not even invoked in the sell flow (`_export_pos_order` has no
  caller here); the source document originates from a retail sale, but the module's own activity is
  compliance serialisation consumed by country localisations — support, not primary.

## 8. Fit-to-Standard

- **Standard:** produce a UBL 2.1 Invoice/CreditNote `document_node` from a `pos.order` (header,
  parties, allowance-charges, tax totals, lines); reuse `account.tax` tax-detail computation over
  POS base lines; encode tendered amounts as Prepaid/Payable; return `(xml, errors)`; offer an
  empty overridable `_export_pos_order_constraints` + per-node hooks.
- **Typical fits:** a country POS e-invoicing localisation needing UBL 2.1 output (e.g.
  `l10n_jo_edi_pos`/JoFotara); extending POS e-invoicing to a clearance regime by subclassing and
  overriding party/header/constraint hooks; producing an e-document for a POS order without first
  creating an `account.move`.
- **Common gaps:** **no end-to-end flow of its own** (a consumer must call, persist and submit);
  **no business-rule enforcement by default** (empty constraints); **not auto-installed / not
  POS-UI wired** (no button, no `pos.order` field); **UBL 2.1 only** (no CII/Factur-X path here);
  Prepaid/Payable assume the till tendering model.
- **Drive:**
  `order = env['pos.order'].search([('state','in',('paid','done','invoiced'))], limit=1); xml, errs =
  env['pos.edi.xml.ubl_21']._export_pos_order(order); print(errs); print(xml[:600])`; with the
  Jordan localisation installed, `env['pos.edi.xml.ubl_21.jo']._export_pos_order(order)[0][:400]`;
  `rg -n '_export_pos_order' addons --glob '!addons/pos_edi_ubl/**'` shows `l10n_jo_edi_pos` is the
  sole caller.

*Provenance: `extract_module.py` + `extract_frontend.py` + code-read of `addons/pos_edi_ubl`,
`addons/account_edi_ubl_cii/models/account_edi_xml_ubl_21.py`, `addons/point_of_sale/models/pos_order.py`,
and the consumer `addons/l10n_jo_edi_pos`. Odoo 19.0.*
