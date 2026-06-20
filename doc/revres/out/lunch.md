# lunch — Reverse-Engineering Brief

The **lunch** module ("Handle lunch orders of your employees") is a standalone HR
employee-services application that lets staff order meals from configured caterers
and manage a prepaid personal wallet. It is `application: true`, **not** auto-installed,
and depends only on **mail** — it has no link to `sale`, `purchase`, `stock` or
`account`, so it stays a self-contained perk rather than a transactional document
flow. 9 models, 6 JSON-RPC routes, 2021 Python LOC and a custom OWL backend dashboard.

## Role & Dependencies
- **mail** — the only dependency: `lunch.supplier` mixes in `mail.thread` +
  `mail.activity.mixin` (chatter/activities) and `lunch.order.action_notify` /
  `_send_auto_email` use `message_notify` and mail templates to reach employees and vendors.
- Capability added on top: an employee meal-ordering catalog, a per-employee cash
  wallet (`lunch.cashmove`), per-supplier order aggregation with an automatic vendor
  email, and a dedicated OWL ordering dashboard.

## Data Model (the ERM)
| _name | _description | #fields | key relations |
|-------|--------------|---------|---------------|
| lunch.order | Lunch Order | 36 | product_id->lunch.product, user_id->res.users, lunch_location_id->lunch.location |
| lunch.product | Lunch Product | 15 | supplier_id->lunch.supplier, category_id->lunch.product.category |
| lunch.supplier | Lunch Supplier | 42 | partner_id->res.partner, cron_id->ir.cron, topping_ids_*->lunch.topping |
| lunch.cashmove | Lunch Cashmove | 5 | user_id->res.users, currency_id->res.currency |
| lunch.topping | Lunch Extras | 6 | supplier_id->lunch.supplier |
| lunch.product.category | Lunch Product Category | 6 | company_id->res.company |
| lunch.location | Lunch Locations | 3 | company_id->res.company |
| lunch.alert | Lunch Alert | 19 | cron_id->ir.cron, location_ids->lunch.location |
| lunch.cashmove.report | Cashmoves report | 6 | user_id->res.users (`_auto=False` SQL view) |

- Central transactional model: **lunch.order** (24 methods, heavy on computed/related
  fields). **lunch.supplier** is the configuration hub (vendor + availability + cron).
- Mixins/extensions (`_inherit` without `_name`): `image.mixin` on lunch.product and
  lunch.product.category; `res.company`, `res.config.settings`, `res.users` are extended
  to add the wallet threshold, notify message, and per-user favorites/last location.
- Field distribution is relational + flag heavy (31 Many2one, 35 Boolean, 15 Selection),
  reflecting catalog wiring, weekday availability toggles and the order state machine.

## Behavior & Surfaces
- **Routes:** 6 JSON-RPC endpoints, all `auth=user` — `/lunch/infos` (dashboard payload),
  `/lunch/trash`, `/lunch/pay`, `/lunch/payment_message`, `/lunch/user_location_get|set`.
  No public/portal surface; everything is an internal-backend RPC.
- **Views:** list (10), kanban (8), form (7), search (7) dominate, plus 1 pivot + 1 graph
  for cash reporting — a catalog/dashboard UX rather than a document editor.
- **Security:** 17 access rules, 10 record rules, 2 groups (`group_lunch_user`,
  `group_lunch_manager`) — users see own orders/cashmoves; managers see all.
- **Frontend (gap #3):** custom OWL backend client — 7 components (LunchDashboard,
  LunchOrderLine, LunchUser, LunchLocation, LunchCurrency, LunchAlert(s)), a patched
  kanban/list and a `lunch_is_favorite` field; 7 JS / 4 XML, `web.assets_backend`.
- **Integrations (gap #7):** none — 0 HTTP call sites, no SDK imports, no API keys.
- **Behavioral facts (code-read):**
  - **Order lifecycle:** `state` = new(To Order) -> ordered -> sent -> confirmed(Received)
    / cancelled; `action_order` checks availability + product active + wallet, `action_send`
    -> sent, `action_confirm` -> confirmed. `create`/`write` merge duplicate lines by
    incrementing quantity.
  - **Wallet:** `lunch.cashmove.get_wallet_balance` sums `lunch.cashmove.report` + the
    company `lunch_minimum_threshold` (overdraft allowance); `_check_wallet` raises
    `ValidationError` when negative, blocking the order.
  - **Vendor auto-send:** each supplier owns an `ir.cron` synced by `_sync_cron`;
    `_send_auto_email` aggregates today's `ordered` lines, emails the caterer, then
    `action_send()`. `action_send_orders`/`action_confirm_orders` are manual buttons.

## Value-Configuration Classification
Stabell & Fjeldstad: **support** (value model) / **support** (activity class). lunch
neither transforms inputs into a sold output (no chain document flow — there are no
`stock.picking`/`account.move` side-effects), solves bespoke client problems (shop),
nor mediates between parties (network). It administers an internal employee benefit:
a meal catalog, a prepaid wallet, and order brokering to caterers. That makes it a
cross-cutting **support** activity, not part of the primary value chain.

## APQC PCF Hint
**7.0 Develop and Manage Human Capital** — lunch is an employee well-being / services
perk (meal ordering + employee wallet administration), squarely an HR support process
rather than a market/sell (3.0) or procurement (4.x) flow.

## How to Drive It
Use the **run-odoo** skill (`odoo shell`):
- `env['lunch.order'].search([], limit=5).mapped(('name','state'))` — inspect orders + states.
- `env['lunch.cashmove'].get_wallet_balance(env.user)` — current wallet balance for a user.
- `env['lunch.supplier'].search([('send_by','=','mail')]).mapped('automatic_email_time')`
  — which vendors auto-email and when.
- curl the JSON-RPC `/lunch/infos` (auth=user) to load the dashboard payload.

## Open Questions
- The exact path that turns an order's price into a `lunch.cashmove` debit row vs. a
  live derivation from `lunch.cashmove.report`.
- How `/lunch/pay` + `/lunch/payment_message` map to wallet top-ups and the notify message.
- Whether `_sync_cron` timezone math handles DST and multi-location order deadlines correctly.

*Provenance: structural facts from `extract_module.py` (`facts/lunch.facts.json`) +
`extract_frontend.py`; behavioral notes code-read from `addons/lunch/models/`. Odoo 19.0.*
