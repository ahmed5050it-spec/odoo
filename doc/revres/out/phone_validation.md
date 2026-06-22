# phone_validation — Reverse-Engineering Brief

The **Phone Numbers Validation** module (`phone_validation`, category *Hidden*,
`application=False`) is a cross-cutting **data-quality utility**: it parses,
validates and normalizes phone numbers (to E164/INTERNATIONAL/NATIONAL/RFC3966)
against a destination country using the external pure-Python **`phonenumbers`**
library, and adds a **phone blacklist** (do-not-contact) plus a reusable
`mail.thread.phone` mixin. It is **auto-installed** and sits low in the graph —
depends only on `base` and `mail` — and is in turn consumed by many primary
modules (crm, sms, event, mass_mailing) that need clean, dialable numbers. It
owns no line-of-business entity of its own; its product is firm infrastructure.

## Role & Dependencies

| Depends on | Why (inferred) |
|------------|----------------|
| `base` | Extends the abstract `base` model so `_phone_format`/`_phone_get_number_fields` are available on **every** model; owns `res.partner`/`res.users` extensions. |
| `mail` | `mail.thread.phone` and `phone.blacklist` inherit `mail.thread` for chatter-tracked blacklist audit logging. |

**Adds on top:** a phonenumbers-backed format/validate helper injected
system-wide, country/region inference, sanitized-number search, and blacklist
management — without itself running any business process.

## Data Model (the ERM)

| Model (`_name`) | Description | #fields | Key relations |
|-----------------|-------------|--------:|---------------|
| **`phone.blacklist`** | Phone Blacklist | 2 | `number` (Char, **unique**, E164-sanitized on create/write) |
| **`mail.thread.phone`** *(mixin)* | Phone Blacklist Mixin | 4 | `phone_sanitized` (computed E164), `phone_sanitized_blacklisted` ← `phone.blacklist.number` |
| `phone.blacklist.remove` *(wizard)* | Remove phone from blacklist | 2 | transient unblacklist wizard |
| `res.partner` *(extension)* | consumes mixin + onchange formatting | 0 | `_inherit = [mail.thread.phone, res.partner]` |
| `base` *(extension)* | phone-format helpers on all models | 0 | `_phone_format` / `_phone_get_country` |
| `res.users` *(extension)* | blacklist phone on portal-user deletion | 0 | `phone.blacklist._add` |

**Central concept:** `phone.blacklist`; the real reach is the `mail.thread.phone`
**mixin** and the `base` extension (`_inherit` without `_name`). The field set is
tiny and **attribute-heavy** (Char/Boolean only) — the value is in Python method
semantics, not in stored fields.

## Behavior & Surfaces

- **Routes:** none (0). Purely an ORM/service module — no web or RPC surface.
- **Views:** form (1), list (1), search (1) for `phone.blacklist`; no kanban/
  pivot/graph. Minimal admin UI; live formatting happens via a `res.partner`
  `@api.onchange('phone','country_id','company_id')` hook, not client JS.
- **Frontend:** none — 0 JS, 0 OWL components, 0 registry adds, no asset bundles
  (static). All behaviour is server-side.
- **Integrations:** none — 0 HTTP call sites, no SDKs, no API keys (static). The
  only external dependency is the **in-process** `phonenumbers` library (offline
  region patches in `lib/phonenumbers_patch`: BR/CI/CO/IL/KE).
- **Security:** 3 access rules, 0 record rules, 0 groups — `phone.blacklist` is
  owned by `base.group_system`.

## Value-Configuration Classification

**Support (firm infrastructure), support activity.** Per Stabell & Fjeldstad,
`phone_validation` is not chain/shop/network — it transforms no document and
mediates no parties. It is a **master-data-quality utility**: `_phone_format`
injected onto the abstract `base` model plus the `phonenumbers` wrapper, consumed
by primary modules. Category *Hidden*, `auto_install=true`, and depending only on
`base`+`mail` confirm cross-cutting infrastructure rather than a value-creating
activity.

## APQC PCF Hint

**8.0 Manage Information Technology** — the module is a data-quality / master-data
correctness service that standardizes and validates a shared data attribute (the
phone number) across the system. (3.0 Market & Sell rejected: it performs no
selling, only guarantees the integrity of contact data that selling/marketing
modules later use.)

## How to Drive It

Use the `run-odoo` skill (`.claude/skills/run-odoo/`). With the server up:

```python
# odoo shell — format/validate via the base extension
env['res.partner']._phone_format(number='0470123456',
    country=env.ref('base.be'), force_format='E164')          # -> '+32470123456'

# the tool helper directly (phonenumbers wrapper)
from odoo.addons.phone_validation.tools import phone_validation as pv
pv.phone_format('0470123456', 'BE', 32, force_format='INTERNATIONAL')
pv.phone_get_region_data_for_number('+32470123456')
#   {'code':'BE','national_number':'470123456','phone_code':'32'}

# blacklist + mixin compute
env['phone.blacklist'].add('+32470123456')
p = env['res.partner'].create({'name':'X','phone':'0470123456',
    'country_id': env.ref('base.be').id}); p.phone_sanitized      # E164
```

No routes to curl — the module exposes no HTTP surface.

## Open Questions (verify in code)

- Country quirks fixed by `lib/phonenumbers_patch` (BR/CI/CO/IL/KE) vs what
  upstream `phonenumbers` already handles.
- How downstream modules (crm, sms, event, mass_mailing) call `_phone_format`
  and whether they pass a country or rely on the `env.company` fallback.
- `_phone_get_number_fields` behaviour on models lacking `phone`/`mobile`
  (custom overrides required).
- The single-`phone_sanitized` limitation in `_compute_blacklisted` when a model
  has both a phone and a mobile blacklisted differently.

---

*Provenance: facts via `doc/revres/extract_module.py addons/phone_validation` +
code-read of `models/models.py`, `models/mail_thread_phone.py`,
`models/phone_blacklist.py`, `tools/phone_validation.py`; frontend via
`extract_frontend.py`. Odoo 19.0.*
