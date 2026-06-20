# privacy_lookup — Reverse-Engineering Brief

> GDPR data-subject lookup & erasure. Given a person's name + email, find every
> record tied to them across all Odoo models, then archive or delete those
> records and write a tamper-resistant, identity-masked audit log. A compliance /
> data-governance utility with no business object of its own.

- **Module:** `privacy_lookup` ("Privacy"), Odoo S.A., LGPL-3
- **depends:** `mail` · **auto_install:** true · **application:** false
- **Size:** 3 own models (1 persistent + 2 transient) + 1 `res.partner` extension,
  0 routes, 585 Python LOC, 210 XML LOC, frontend absent (no OWL/JS).

## Role & Dependencies

A thin, admin-only support layer. It is auto-installed and depends only on `mail`
(to reach `mail.message` authorship). It owns no products, no customer-facing
flow, and exposes no HTTP routes — it operates *on* other modules' data. All
access (`ir.model.access.csv`) is gated to `base.group_system`, so only the
System administrator / DPO can run a lookup or perform an erasure.

## Data Model (the ERM)

- **privacy.log** — append-only audit record: `date`, `anonymized_name`,
  `anonymized_email`, `user_id`→`res.users` (Handled By), `execution_details`,
  `records_description`, `additional_note`.
- **privacy.lookup.wizard** (transient) — the run: `name`, `email`,
  `line_ids`→`privacy.lookup.wizard.line`, `log_id`→`privacy.log`,
  computed `execution_details` / `records_description` / `line_count`.
- **privacy.lookup.wizard.line** (transient) — one matched record:
  `res_model_id`→`ir.model`, `res_id`, `resource_ref` (dynamic Reference to *any*
  model), `is_active`, `is_unlinked`, `execution_details`.
- **res.partner** (extension) — adds `action_privacy_lookup` launcher only.

## Behavior & Surfaces

The metadata-invisible substance is the discovery engine (all `code-read`):

- **`_get_query` / `action_lookup`** build a single raw SQL `UNION ALL` and run it
  via `cr.execute`, materialising each row as a wizard line. Layers: (1) an
  `indirect_references` CTE of `res_partner` matched by `email_normalized` or
  `name ilike`; (2) explicit UNIONs over `res_partner`, `res_users` (by login or
  partner_id), and `mail_message` (author_id, to catch direct messages); (3) a
  **dynamic sweep across every non-transient, non-abstract model in `self.env`**.
- **Model-discovery heuristic** (per model, minus a blacklist of
  partner/users/notification/followers/channel-member/message): DIRECT match on a
  stored `email_normalized`/`email`/`email_from`/`company_email` field (plus an
  ilike on the model's char `_rec_name`); INDIRECT match for every stored
  `many2one`→`res.partner` whose `ondelete != 'cascade'`. So "which models hold
  PII" is derived at runtime, not from a fixed list.
- **Erasure** is per-line: `_onchange_is_active` writes `active` (archive),
  `action_unlink` calls `.sudo().unlink()` (delete); `action_archive_all` /
  `action_unlink_all` iterate. All run `sudo()` to reach records the operator may
  not directly own.
- **Audit + masking:** `_post_log` auto-creates a `privacy.log`; its `create()`
  masks the subject — `_anonymize_name` → `J*** D**`, `_anonymize_email` →
  `j***.d**@e******.com` (keeps gmail/hotmail/yahoo domains and the TLD).
- **UI (static):** Settings ▸ Privacy ▸ read-only Privacy Logs, plus a partner
  form Action that opens the wizard pre-filled with the partner's email/name.

## Value-Configuration Classification

- **value_model:** `support` — a firm-level risk / IT governance function with no
  product, customer transaction, or document chain of its own; it acts on other
  modules' data.
- **activity_class:** `support`.
- Confidence: information_concepts/organization/products = `auto`;
  capabilities/value_streams/policies/metrics = `inferred`; strategy = `human`
  (null).

## APQC PCF Hint

- **13.0 Develop and Manage Business Capabilities** — the module operationalises a
  data-privacy *governance* capability: discovering, retaining and erasing PII
  across the enterprise's information assets (information-governance strand).
- **Alternative considered:** 11.0 "Manage Enterprise Risk, Compliance,
  Remediation, and Resiliency" — defensible, since GDPR is a regulatory obligation
  and erasure is a compliance-remediation act. 13.0 is preferred because the
  tool's substance is governing the data/information capability itself rather than
  the broader risk-register/control-testing scope 11.0 centres on.

## How to Drive It

```python
# odoo shell — run a lookup and see which models matched
w = env['privacy.lookup.wizard'].create({'name':'John Doe','email':'john@example.com'})
w.action_lookup(); w.line_ids.mapped('res_model')

# inspect the generated cross-model discovery SQL
print(env['privacy.lookup.wizard'].new({'name':'A','email':'a@b.com'})._get_query())

# observe identity masking on the audit log
env['privacy.log'].create({'anonymized_name':'John Doe',
    'anonymized_email':'john.doe@acme.com'}).read(['anonymized_name','anonymized_email'])
```
UI: partner form ▸ Action ▸ Privacy Lookup, archive/delete lines, then check
Settings ▸ Privacy ▸ Privacy Logs.

## Open Questions (verify in code)

- Real-world recall: how much PII sits in custom models lacking both an email-like
  field and a non-cascade partner FK (and is therefore missed)?
- Do downstream modules extend the sweep via their own privacy hooks? (none here)
- Failure handling when `unlink()` hits referential-integrity / access constraints.
- No in-place pseudonymisation — only archive or full unlink — and no
  request workflow / approval / SLA tracking around the erasure.
