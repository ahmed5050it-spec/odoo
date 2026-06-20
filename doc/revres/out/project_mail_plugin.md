# project_mail_plugin — Reverse-Engineering Brief

The **project_mail_plugin** module is the Project backend for Odoo's Outlook/Gmail mail add-in ("Turn emails received in your mailbox into tasks and log their content as internal notes", category *Services/Project*). It is a small (`198` Python LOC), `application: false`, **`auto_install: true`** bridge that activates whenever both **project** and **mail_plugin** are present. It owns no new models; instead it grafts a work-request-intake layer onto the inbox sidebar: from an open email a project member can create a `project.task` in one click, pick or create the target project, and see the sender's existing tasks inside the add-in contact card. All the heavy mail-plugin plumbing — outlook bearer-token auth and the email-to-partner lookup — lives in the parent **mail_plugin**; this module only adds the Project-specific routes and the contact-card task list.

## Role & Dependencies

- **project** — supplies `project.project` and `project.task` (the records this module creates/reads/searches), default kanban stages, and the standard task form (`project.view_task_form2`, reused by the redirect action).
- **mail_plugin** — supplies the JSON-RPC controller base, the `outlook` auth method (`ir_http._auth_method_outlook`), the auth-code → access-token exchange, and the partner resolution route (`res_partner_get`). This module subclasses `mail_plugin.MailPluginController` and extends its hooks (`_get_contact_data`, `_mail_content_logging_models_whitelist`, `_translation_modules_whitelist`).

Capability added on top: inbox-to-task capture, project lookup/creation, and a contact-context task list, gated by Project access rights.

## Data Model (the ERM)

| _name / _inherit | _description | #fields | Key relations |
|------------------|--------------|--------:|---------------|
| `project.task` (created) | Task | — | project_id→project.project, partner_id→res.partner, user_ids→res.users |
| `project.project` (created/searched) | Project | — | partner_id→res.partner |

The module defines **0 new models** and **0 inherit-only model extensions** — it is pure controller code that creates/reads `project.task` and `project.project` through the ORM. There is no security data (0 access rules, 0 record rules, 0 groups); it relies entirely on Project's own ACLs, checked at runtime via `project.task.has_access('create')`, `project.project.has_access('create')`, and `project_id._filtered_access('read')`. The only stored datum is one `ir.actions.act_window` record (`project_task_action_form_edit`) used to redirect to the new task's form in edit mode. Value flows across three information concepts it does not own — `project.task`, `project.project`, `res.partner` — plus `res.users.apikeys` as the outlook token identity.

## Behavior & Surfaces

Three HTTP routes, all JSON-RPC `auth="outlook"`, `cors="*"`, split across two controllers (`project_client.py`, `mail_plugin.py`).

- **`/mail_plugin/task/create`** (`task_create`): `exists()`-validates `partner_id` (else `{'error': 'partner_not_found'}`) and `project_id` (else `{'error': 'project_not_found'}`); defaults a blank subject to `Task for <partner>`; then `project.task.with_company(partner.company_id).create({name: subject, partner_id, description: email_body, project_id, user_ids: [Command.link(uid)]})`, returning `{'task_id', 'name'}`. No stage set → project defaults apply. Note the subject is stored **raw** (no `html2plaintext`, unlike the crm lead path).
- **`/mail_plugin/project/search`** (`projects_search`): `project.project` search by `name ilike search_term` (limit 5), returns `{project_id, name, partner_name, company_id}` per hit, read via `sudo()` for the picker.
- **`/mail_plugin/project/create`** (`project_create`): `project.project.create({'name': name})` on demand — name only, no partner/company/template.
- **`_get_contact_data` override**: appends a `tasks` key (and `can_create_project` flag) to the sidebar contact card — search `project.task` by `partner_id` (limit 5), filtered to projects passing `_filtered_access('read')`, returning `{task_id, name, project_name}`. The whole branch is skipped unless `project.task.has_access('create')`, so the section silently disappears for users who cannot create tasks. Same gate also adds `project.task` to the content-logging whitelist and `project_mail_plugin` to the translation whitelist.
- **Auth**: `_auth_method_outlook` (parent) reads the `Authorization` header, strips `Bearer `, validates against `res.users.apikeys._check_credentials(scope='odoo.plugin.outlook')`, then takes the API-key user's identity; missing/invalid tokens raise `BadRequest`.
- **Frontend**: no OWL/JS (0 js files); the 2 XML templates are the `to_translate` add-in translation bundles. The real UI is the external Outlook/Gmail add-in.

## Value-Configuration Classification

**Value model: `shop` · Activity class: `primary`.** project_mail_plugin is a thin service-intake extension of Project, itself a value-shop. Its work is capturing inbound work requests from the mailbox and turning an email into a `project.task` — feeding the Project diagnose-plan-execute-control loop rather than transforming inputs into outputs along a chain. It is a feeder/bridge (auto_install) onto `project.task`/`project.project` rather than a standalone value stream, but the activity it performs is engagement/work-request intake at the very front of the shop, so `shop`/`primary` rather than `support`.

## APQC PCF Hint

**5.0 Deliver Services** — service-request intake at the front edge of the deliver-services category. The created `project.task` then enters Project's standard task lifecycle (stages + timesheet). This maps to the `project.task` "Deliver services (engagement)" row in `apqc_odoo_map.tsv` (level *process*, `5.x`, value_model `shop`); project_mail_plugin is specifically the inbox-to-task intake that opens that engagement.

## How to Drive It

- `odoo shell`: `p = env['res.partner'].search([('email','!=',False)], limit=1); pr = env['project.project'].search([], limit=1); t = env['project.task'].with_company(p.company_id).create({'name':'Inbox subject','partner_id':p.id,'description':'email body','project_id':pr.id,'user_ids':[(4, env.uid)]}); (t.id, t.stage_id.name, t.project_id.name)`
- `odoo shell`: `env['project.project'].search([('name','ilike','a')], limit=5).mapped(lambda r:(r.id,r.name,r.partner_id.name,r.company_id.id))`
- `curl -X POST .../mail_plugin/task/create -H 'Authorization: Bearer <apikey>' -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","method":"call","params":{"email_subject":"Hi","email_body":"body","project_id":1,"partner_id":1}}'`
- `odoo shell`: `env['res.users.apikeys']._check_credentials(scope='odoo.plugin.outlook', key='<token>')`

## Open Questions

- Exact `project.task` defaults (stage_id/company_id/privacy) for a plugin-created task with no stage context beyond `with_company`.
- Whether `email_body`/`description` (and the raw, un-`html2plaintext`'d subject) is HTML-sanitized anywhere downstream.
- Whether any add-in client uses `project/create` to spin up bare projects in production, or only targets existing ones via `project/search`.
