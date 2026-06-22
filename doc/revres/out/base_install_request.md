# base_install_request — Reverse-Engineering Brief

`base_install_request` lets a **non-admin internal user request that an Odoo app be installed**, and lets a **System administrator review and approve/install it**. It is a tiny, `auto_install: true`, non-application "Hidden" support add-on (158 py / 119 xml LOC) depending only on `mail`. It owns no business object: it ships two `TransientModel` wizards (`base.module.install.request`, `base.module.install.review`) plus a one-method extension of `ir.module.module`, wiring a governed app-provisioning workflow onto Odoo's Apps registry. It sits at the IT-infrastructure edge of the dependency graph — every database that pulls in `mail` gets it.

## Role & Dependencies

- **mail** — the whole notification path: the request is delivered as a `mail.template` (`mail_template_base_install_request`) rendered and sent via `send_mail(force_send=True, email_layout_xmlid='mail.mail_notification_light')`.

Capability added on top: a **self-service "Request Access" flow** for apps a regular employee cannot install themselves. It does not add a new business domain — it adds governance around `ir.module.module.button_immediate_install` (which is provided by `base`).

## Data Model (the ERM)

| Model | _description | #fields | Key relations |
|-------|--------------|---------|---------------|
| `base.module.install.request` | Module Activation Request | 4 | `module_id`→`ir.module.module`, `user_id`/`user_ids`→`res.users` |
| `base.module.install.review` | Module Activation Review | 3 | `module_id` + computed `module_ids`→`ir.module.module` |
| `ir.module.module` (extension) | adds `action_open_install_request()` | 0 | — |

Both concrete models are **TransientModels** — no rows persist; they exist only to drive a wizard turn. The `ir.module.module` row is a pure **mixin/extension** (`_inherit` without `_name`). Field types are relational-heavy (3 Many2one, 2 Many2many) plus 2 `Html` (the requester's justification `body_html`, the review's `modules_description`). There is no aggregate/document model and no audit record — the workflow is fire-and-forget.

## Behavior & Surfaces

- **Routes:** none (0). All interaction is wizard act_windows + one mail deep-link.
- **Views:** 2 form views (request, review), 1 inherited **kanban** button on `base.module_view_kanban` ("Request Access"), and 1 QWeb description/email template. No list/search/graph — pure modal-wizard UX.
- **Security:** 6 access rules, 0 record rules, 0 new groups. The split is the heart of the design: `base.group_user` may create a **request**; the **review** wizard's create is restricted to `base.group_system`. Read-only access on `ir.module.module`/category/dependency/exclusion is granted to `base.group_user` so employees can browse Apps.

Key behaviors (code-read, not in metadata):
- **action_open_install_request()** opens the request wizard from the kanban; the button is shown only for `groups='!base.group_system'`, `state=='uninstalled'`, and `!record.to_buy.raw_value` (enterprise/buy apps excluded).
- **action_send_request()** resolves recipients from `base.group_system.all_user_ids` and emails each admin a "Review Request" deep link `/odoo/{module_id}/action-base_install_request.action_base_module_install_review`.
- **action_install_module()** (admin) previews dependency apps via `_get_depending_apps` → `module.upstream_dependencies()`, then calls `button_immediate_install()` (end-of-transaction, registry/DB-safe) and reloads the client.
- **post_init_hook `_auto_install_apps`** optionally `button_install()`s a fixed productivity pack (hr, mass_mailing, project, survey; appointment, knowledge, planning, sign) when `config['default_productivity_apps']` is set.

## Value-Configuration Classification

**support** / **support** (Stabell & Fjeldstad; Porter support activity). This is cross-cutting firm IT infrastructure, not a value-creating primary activity of any chain/shop/network. It transforms nothing, solves no customer problem, and mediates no exchange — it provisions an internal application capability. Evidence: `auto_install: true`, `application: false`, "Hidden" category, depends only on `mail`, zero persisted business data, and substance that is purely behavioral (request-email-to-admins → admin-approve → immediate install).

## APQC PCF Hint

**8.0 Manage Information Technology** — the work is an IT service request / application-provisioning flow: receive and triage a request, review and approve it, then deliver the application capability (install the app). 13.0 "Develop and Manage Business Capabilities" was considered (a request decides which capability is enabled) but rejected — this is a concrete running install mechanism, not a governance/portfolio capability.

## How to Drive It

Use the **run-odoo** skill (`odoo shell`); there are no routes to curl.

```python
m = env['ir.module.module'].search([('name','=','crm')])
m.action_open_install_request()                       # -> request wizard act_window
w = env['base.module.install.request'].create({
        'module_id': m.id, 'body_html': '<p>need it</p>'})
w.action_send_request()                               # emails all base.group_system admins
r = env['base.module.install.review'].create({'module_id': m.id})
r.module_ids                                           # dependency apps preview
r.action_install_module()                             # button_immediate_install + reload
```
In the browser: log in as a non-admin, open Apps, confirm "Request Access" appears on uninstalled non-enterprise apps and is absent on `to_buy` apps.

## Open Questions

- Do downstream/enterprise modules replace the email notification with a `mail.activity` or a persisted request record with approval/rejection states? (Base has none.)
- What happens to the "Review Request" deep link if the module was installed between request and review (`_get_depending_apps` raises `UserError` on already-installed)?
- Which deployment contexts set `config['default_productivity_apps']`, triggering `_auto_install_apps`?
- Concurrent duplicate requests for the same app are not de-duplicated — each send is an independent transient email; is that intended?

*Provenance: facts from `extract_module.py` / `extract_frontend.py`; behavioral notes code-read from `models/ir_module_module.py`, `wizard/base_module_install_request.py`, `__init__.py`, views and mail templates. Odoo 19.0.*
