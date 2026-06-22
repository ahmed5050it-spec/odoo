# google_address_autocomplete — Architecture Brief

> Module: `google_address_autocomplete` · Category: Hidden/Tools · Depends: `web` · `auto_install: false`
> Value model: **support** · Activity class: **support** · APQC: **13.0 Develop and Manage Business Capabilities**
> Odoo 19.0 · Facts: `doc/revres/facts/google_address_autocomplete.facts.json` · Frontend: `doc/revres/frontend/google_address_autocomplete.frontend.json`

## 1. Summary

`google_address_autocomplete` is a **server-side proxy + form widget for address
type-ahead**. As a user types an address on a partner form, it queries the
**Google Places API** (Autocomplete then Details) and maps the structured result
onto `res.partner` address fields — street, number, city, zip, state, country.
It owns no business object: **2 `_inherit`-only models** (`res.config.settings`
adds the Google API key as a config parameter; `res.partner` only overrides
`_get_view`), **0 own security records**, **~715 py LOC** almost entirely in one
controller. Category *Hidden/Tools* + `auth='public'` routes that self-gate to
internal users mark it as invisible plumbing on top of `web`. Its substance is
the **outbound Google call** (gap #7) and the **inbound component→field mapping**.

## 2. Structure (evidence)

- **Models (0 own + 2 inherit):** `res.config.settings` (+`google_places_api_key`
  `Char`, `config_parameter='google_address_autocomplete.google_places_api_key'`
  — stored in `ir.config_parameter`, not a column); `res.partner` (no new fields;
  overrides `_get_view` to inject the widget).
- **Routes:** **2** — `/autocomplete/address` and `/autocomplete/address_full`,
  both `type='jsonrpc'`, `auth='public'`, `website=True`. These are the module's
  only surface; the actual Google HTTP is *outbound* from the controller.
- **Security:** 0 access rules, 0 record rules, 0 groups — both routes self-gate
  via `_get_api_key` (`assert request.env.user._is_internal()`), and the API key
  field is restricted to `base.group_system` in Settings.
- **Views:** **0** model views declared (xml_loc=90 is `res.config.settings` /
  `res.partner` / `res.company` form inheritance); the address widget is injected
  programmatically by `res.partner._get_view`, not via XML.

## 3. Frontend (gap #3)

**2 JS / 1 XML**, bundled in `web.assets_backend` (+`web.assets_web_dark`,
`web._assets_core`). **No OWL components** — one registry add,
`fields:google_address_autocomplete` (a field widget).
`static/src/google_places_session.js` exports a `googlePlacesSession` singleton
that mints a v4-style UUID **`sessiontoken`** (per Google's session-billing rule:
one token spans many autocomplete queries + one details fetch, then resets), and
wraps the routes as `getAddressPropositions()` → `rpc('/autocomplete/address')`
and `getAddressDetails()` → `rpc('/autocomplete/address_full')`. The
`google_address_autocomplete` widget renders the suggestion dropdown (with the
*Powered by Google* image, light/dark variants) and on select writes the resolved
address back onto the record.

## 4. Behavior (beyond metadata)

- **Predictions call (code-read):** `_autocomplete_address` (`/autocomplete/address`)
  → `_perform_place_search` reads `ir.config_parameter
  'google_address_autocomplete.minimal_partial_address_size'` (default 5) and
  returns nothing until the input is longer — a **cost guard** — then
  `requests.get('https://maps.googleapis.com/maps/api/place/autocomplete/json',
  params={key, fields, inputtype='textquery', types='address', input,
  components='country:<cc>'?, language?, sessiontoken?}, timeout=2.5)` and reshapes
  Google `predictions[]` into `[{formatted_address, google_place_id}]`.
- **Details + mapping (code-read):** `_autocomplete_address_full`
  (`/autocomplete/address_full`) → `_perform_complete_place_search` GETs
  `/details/json` (`fields='address_component,adr_address'`), then
  `_translate_google_to_standard` maps Google component types→Odoo fields via
  `FIELDS_MAPPING`/`FIELDS_PRIORITY`: `country`→`res.country.search([('code','=',…)])`,
  `administrative_area_level_1/2`→`res.country.state` (assigned only on an exact
  single match), `locality`/`postal_town`→city, `route`→street, etc.; resolves
  `res.city` via `res.partner._get_res_city_by_name` and back-fills state from the
  city. `_guess_number_from_input` recovers the house number from the raw input
  when Google omits it.
- **Access gating (code-read):** `_get_api_key` asserts `_is_internal()` and reads
  the key (`ir.config_parameter`, sudo). `/autocomplete/address` **degrades to
  empty** for non-internal callers (public visitor gets no suggestions, never
  spends the key); `/autocomplete/address_full` **raises `AccessError`**. The key
  is sent to Google as the `key` query param and never reaches the browser.
- **Widget injection (code-read):** `res.partner._get_view` sets
  `widget='google_address_autocomplete'` on the `street`/`street_name` nodes **only
  when `enforce_cities` exists in `res.country._fields`** (i.e. `base_address_extended`
  is installed) — a dependency no manifest field expresses.
- **External integration (static, gap #7):** `http_call_sites=1`, `requests`,
  `uses_api_keys=true`; single endpoint base `https://maps.googleapis.com/maps/api/place`
  (`/autocomplete/json`, `/details/json`), auth = Google Maps Platform API key.

## 5. IT architecture

- **Application:** server-side proxy + form widget turning partial address typing
  into a Google Places lookup written onto `res.partner`.
- **Software services:** `/autocomplete/address` (predictions), `/autocomplete/address_full`
  (details→structured address, internal-only).
- **Data objects:** `res.config.settings` (+key), `res.partner` (inherit).
- **Key relations:** controller→`res.country`/`res.country.state`/`res.city`;
  `google_places_api_key` in `ir.config_parameter`; Google `place_id` as the
  cross-system key between the two routes.
- **Flows:** OWL typing (sessiontoken) → `rpc /autocomplete/address` → Google
  Autocomplete → pick → `rpc /autocomplete/address_full` → Google Details →
  `_translate_google_to_standard` → partner fields.

## 6. Business architecture

- **Capabilities (inferred):** address type-ahead; structured address capture;
  house-number recovery; configurable API key + minimal-input threshold.
- **Value streams (inferred):** *Type-to-Address* (type → Autocomplete → select →
  Details → fields populated).
- **Information concepts (auto):** `res.partner` address; Google prediction/`place_id`;
  `google_places_api_key`.
- **Policies (inferred):** internal-user gate; minimal-size cost guard; 2.5s
  fail-soft timeout; key held server-side only; state set only on an unambiguous
  match.
- **Strategy:** `null` (human). **Organization/Products:** none.

## 7. Classification

- **Value model: support** — shared firm IT infrastructure (Stabell & Fjeldstad
  *support*; Porter support activity). It owns no chain/shop/network business
  object; it improves partner address master data via an external provider. A
  *network* reading (it mediates Odoo↔Google) was weighed but rejected, as in the
  sibling `partner_autocomplete`: the mediation is incidental egress, not the
  enterprise substance.
- **Activity class: support.**
- **APQC: 13.0 Develop and Manage Business Capabilities** — **master-/reference-data
  management**: populating/maintaining the partner address master that
  sale/purchase/account/crm reuse. `8.0 Manage IT` rejected (no IT plumbing of its
  own); `3.0 Market & Sell` rejected (sells nothing).

## 8. Fit-to-Standard

- **Standard:** Google-Places address type-ahead on `res.partner`; Autocomplete +
  Details split with one billing session token; component→field mapping with
  house-number recovery; system-only API-key config; conditional widget injection
  under `base_address_extended`.
- **Typical fits:** faster, standardised address entry; fewer malformed delivery/
  invoice addresses; deployments that already hold a Google Maps Platform key.
- **Common gaps:** needs a paid Google key + outbound HTTPS (no air-gapped
  autocomplete); coverage is Google's; only the partner street path is wired; no
  local lookup/spend audit (metered in Google Cloud); state left blank on
  ambiguous matches; partial addresses sent to Google (privacy/DPA review).
- **Drive:** `env['ir.config_parameter'].sudo().get_param('google_address_autocomplete.google_places_api_key')`;
  `curl -X POST /autocomplete/address` (empty without a key / non-internal user).
