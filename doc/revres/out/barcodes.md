# barcodes — Reverse-Engineering Brief

`barcodes` (manifest name "Barcode", category Supply Chain/Inventory, v2.0) is the
suite-wide **barcode nomenclature / parsing framework plus scan-anywhere capture
layer**. It is `auto_install=false`, `application=false`, and depends only on `web`.
It owns no real business document: just two pieces of reference data
(`barcode.nomenclature` and its ordered `barcode.rule` set), an event mixin, and
~655 lines of Python — its true substance is the OWL/JS scan buffer, parser and
field widgets under `static/src`. Every scanning app (stock, stock_barcode,
point_of_sale, mrp) builds on it. It is firm **infrastructure**, not a value-
producing process of its own.

## Role & Dependencies

- **web** — supplies the OWL framework, the `registry`, the `services`/`fields`
  registries, the form-field widget contract and `ir.http.session_info`; barcodes
  hangs its scan service and field widgets off these.

What it adds on top: a configurable, ordered **regex + check-digit nomenclature**
that classifies any scanned string into a typed reference (product / lot / weight /
price / package), a **GS1 / EPC-URI + RFID** parser, EAN/UPC validation and
conversion, and a browser **keystroke-buffer + camera + manual** capture layer that
fires `barcode_scanned` anywhere in the UI — exposed to other apps via the
`on_barcode_scanned` mixin and the `barcode_handler` / `field_float_scannable`
widgets.

## Data Model (the ERM)

| _name | _description | #fields | key relations |
|-------|--------------|---------|---------------|
| `barcode.nomenclature` | Barcode Nomenclature | 3 | `rule_ids` → `barcode.rule` |
| `barcode.rule` | Barcode Rule | 7 | `barcode_nomenclature_id` → `barcode.nomenclature` |
| `barcodes.barcode_events_mixin` | Barcode Event Mixin (AbstractModel) | 1 | — |
| `ir.http` *(extension)* | adds `max_time_between_keys_in_ms` to `session_info` | 0 | — |
| `res.company` *(extension)* | adds `nomenclature_id` (active nomenclature) | 1 | → `barcode.nomenclature` |

The aggregate is **`barcode.nomenclature`** (a named, ordered collection of rules);
`barcode.rule` is the leaf carrying `sequence`, `encoding`, `type`, `pattern`,
`alias`. **`barcodes.barcode_events_mixin`** is a mixin (`_inherit`-style abstract,
non-stored `_barcode_scanned`) that other models mix in to react to scans; the
`ir.http` and `res.company` entries are pure extensions. The field mix is tiny and
attribute-heavy (Char-dominated patterns/aliases/names with two Many2one links) —
consistent with a reference-data/config model, not a transactional one.

## Behavior & Surfaces

- **Routes:** **none** — the module ships no controllers. It is consumed as a model/
  mixin API and an OWL service, not as an HTTP surface (gap #7: 0 call sites, no SDK/
  API keys). The metadata-invisible behavior is in methods: `parse_barcode` walks
  `rule_ids` in `sequence asc` order applying each rule's encoding + `match_pattern`
  regex + `check_barcode_encoding` check-digit, returning the first typed match;
  `match_pattern` decodes embedded quantity/weight/price from the `{N*D*}` brace
  grammar; `parse_uri` decomposes GS1/EPC URIs (GTIN→product+lot, SSCC→package).
  A `@api.constrains('pattern')` guard enforces the brace grammar.
- **Frontend (gap #3, the real surface):** 7 JS / 3 XML. `barcodeService`
  (services:`barcode`) buffers `keydown` bursts and flushes on a
  `maxTimeBetweenKeysInMs` timeout to tell a scanner from typing;
  `barcodeGenericHandlers` (services:`barcode_handlers`) dispatches `OBT*`/`OCD*`
  commands; `BarcodeParser` is a JS port of the Python parser; `BarcodeHandlerField`
  and `FloatScannableField` (fields:`barcode_handler`, `field_float_scannable`) plus
  `BarcodeScanner` / `ManualBarcodeScanner` wire scans into forms.
- **Views:** 2 form + 2 list — minimal admin screens for nomenclatures and rules.
- **Security:** 4 ACLs, 0 record rules, 0 new groups — read for `base.group_user`,
  full maintenance for `base.group_erp_manager`.

## Value-Configuration Classification

**support** (Stabell & Fjeldstad). barcodes is a cross-cutting scanning/
identification framework — Porter-style firm infrastructure with no business object
beyond nomenclature reference data, 0 routes, and its weight in reusable OWL/JS. It
is not a primary activity of any one chain/shop/network; instead it is the input/
identification platform that stock, POS and MRP all reuse. `activity_class` =
**support**.

## APQC PCF Hint

**8.0 Manage Information Technology** — barcodes is a shared technical capability /
IT-delivered service (the barcode identification runtime + library) that underpins
**4.0** logistics scanning (warehouse/POS) but is itself infrastructure, not the
logistics process. 4.0 was rejected because those flows live in stock/pos and merely
call into this layer; 13.0 (Manage Business Capabilities) was rejected because this
is a concrete running library/runtime, i.e. IT delivery — mirroring the `web`
framework precedent.

## How to Drive It

Use the **run-odoo** skill (`odoo shell`); there are no routes to curl.

```python
# classify a UPC-A product code:
env.ref('barcodes.default_barcode_nomenclature').parse_barcode('012345678905')
# GS1 EPC-URI -> [product, lot]:
env.ref('barcodes.default_barcode_nomenclature').parse_barcode(
    'urn:epc:id:sgtin:0614141.812345.6789')
# inspect the ordered rule set:
env['barcode.rule'].search_read([], ['name','sequence','encoding','type','pattern'])
# confirm the scan-buffer threshold injected into the client:
env['ir.http'].session_info()['max_time_between_keys_in_ms']
```

## Open Questions (verify in code)

- The full set of parsed **types** is extended downstream — stock/stock_barcode/
  point_of_sale add `barcode.rule.type` values and override `on_barcode_scanned`
  beyond this module's product/alias.
- Camera-scanner browser support matrix (`BarcodeDetector` vs ZXing fallback) and
  HTTPS/permission requirements at runtime.
- Divergences between the Python parser and its JS port (e.g. JS sanitizes only
  `ean13` base_code; Python also sanitizes `upca`).
- Runtime nomenclature/rule counts and which nomenclature each company actually uses
  (not captured; `models_with_data=0`).

*Provenance: facts from `extract_module.py` + `extract_frontend.py`; behavioral notes
code-read from `addons/barcodes/models/*` and `static/src/*` (Odoo 19.0).*
