# pos_event_sale — Architecture Brief

> Module: `pos_event_sale` · Category: Technical · Depends: `pos_event`, `pos_sale` · `auto_install: true`
> Value model: **chain** · Activity class: **primary** · APQC: **3.0 Market and Sell Products and Services**
> Odoo 19.0 · Facts: `doc/revres/facts/pos_event_sale.facts.json` · Frontend: `doc/revres/frontend/pos_event_sale.frontend.json` · DEEP record.

## 1. Summary

`pos_event_sale` is the tiny **double-bridge** that sits where `pos_event` and `pos_sale`
overlap. It owns a single `event.registration` extension whose *entire* contribution is **one
re-override of `_compute_registration_status`** (`@api.depends('pos_order_id.state')`, **0 new
fields, 1 method, 148 py LOC**). Its job: make a POS-sold event ticket count as **"Sold" only
once its POS order is actually paid**. `pos_event` alone marked any ticket on a non-zero,
non-cancelled POS order immediately `sold`/`open`; that was safe when a ticket is rung and
tendered in one checkout. But `pos_sale` lets a cashier **settle a draft sale-order/quotation**
at the till, so an order can carry a non-zero total while still in state `draft` until payment is
validated. When **both** modules are present a ticket can therefore sit on an unpaid order —
and this module corrects it: `state in {paid,done,invoiced}` ⇒ `sale_status='sold'`/`state='open'`,
**else** `sale_status='to_pay'`/`state='draft'`. It is the point-of-sale analogue of
`event_sale`'s rule that slaves registration status to `sale_order_id.state`. Footprint: **1
inherit, 0 routes, 0 ACLs, 0 views, 0 JS**, `auto_install=true` (it switches on exactly when both
seams exist). The bundled `tests/test_frontend.py` is its executable spec.

## 2. Structure (evidence)

- **Models (1 inherit):** `event.registration` (`_inherit ['event.registration']`) — **no new
  fields**, one overridden compute. The relations it reads (`pos_order_id → pos.order`,
  `sale_order_id → sale.order`) are inherited from `pos_event` and `event_sale`.
- **Routes:** **0** — backend/ORM only.
- **Security:** 0 ACLs, 0 record rules, 0 groups — relies on `pos_event`'s
  `group_pos_user` CRU on `event.registration`.
- **Views:** none; **0 XML/data files**. It changes one method's behaviour; the registration
  form/list it influences belong to `pos_event` / `event_sale`.

## 3. Frontend (gap #3)

**0 JS / 0 XML templates, no OWL components, no registry adds, no patches, no asset bundles**
(`present:false`). Backend/ORM only — the POS ticket-selling UX
(`EventConfiguratorPopup`/`EventRegistrationPopup`/`EventSlotSelectionPopup`, the `ProductScreen`
patch) is contributed by `pos_event`, not here. `integrations_gap7` empty.

## 4. Behavior (beyond metadata)

- **`_compute_registration_status` (code-read) — the whole module:** calls `super()` first, then
  for every POS-linked registration (`self.filtered('pos_order_id.id')`) **overwrites** the status
  with a paid-state test: `pos_order_id.state in ['paid','done','invoiced']` ⇒ `sale_status='sold'`,
  `state='open'`; else ⇒ `sale_status='to_pay'`, `state='draft'`. This deliberately replaces the
  `pos_event` rule where `amount_total != 0` made the ticket immediately `sold` regardless of payment.
- **Why the bridge exists (code-read):** `pos_sale`'s settle-from-quotation flow creates **non-zero
  but unpaid draft `pos.order`s** (an order moves to `paid`/`done`/`invoiced` only on
  `action_pos_order_paid`). So an event ticket can sit on a non-zero unpaid order. This module aligns
  `event.registration.sale_status` with the order's real paid state, mirroring `event_sale`'s
  `sale_order_id.state` rule (`'sold'` only when the SO is in state `'sale'`, else `'to_pay'`).
- **MRO / `super()` ordering (code-read):** `_compute_registration_status` is overridden along a chain
  (`event_product` default → `event_sale` for `sale_order_id` → `pos_event` for `pos_order_id` →
  here), all feeding the same stored `sale_status` (defined in `event_product`) and `state`. Because
  this override calls `super()` **first** then re-writes POS-linked records, its paid-state verdict
  **wins** for POS-sourced registrations. `sale_status` is stored/precompute/compute_sudo, so the
  recompute fires on create and whenever `pos_order_id.state` changes — auto-flipping a ticket from
  `to_pay`/`draft` to `sold`/`open` when the order is finally tendered.
- **Proven by `tests/test_frontend.py::test_sale_status_event_in_pos` (code-read):** `sync_from_ui`s
  two POS orders each with a ticket line + attendee — order 1 with a 100.0 payment, order 2 `draft`
  with no payment — and asserts the resulting registrations' `sale_status` set == `{'sold','to_pay'}`.
  That is exactly the paid-vs-unpaid distinction `pos_event` alone could not make.
- **Frontend (static, gap #3):** none — backend only.

## 5. IT architecture

- **Application:** auto-install double-bridge reconciling event-ticket registration status with the
  POS order's paid state when both `pos_event` and `pos_sale` are installed.
- **Data objects:** `event.registration` (ext — override only).
- **Key relations:** `event.registration → pos.order` (`pos_order_id`, related via
  `pos_order_line_id.order_id`); `event.registration → sale.order` (`sale_order_id`, reachable because
  `pos_sale` pulls in `sale_management`); `pos.order.state → event.registration.sale_status/state`.
- **Flows:** `depends` `pos_event` + `pos_sale`; side-effect: on create and on `pos_order_id.state`
  change, `sale_status='sold'`/`state='open'` iff the order is paid/done/invoiced, else
  `'to_pay'`/`'draft'`; consequence: a ticket settled from a quotation is "Not Sold" until tendered,
  then auto-confirms. No new persistence, route, view, security or external call.

## 6. Business architecture

- **Capabilities (inferred):** reconcile registration status with POS order payment state; defer
  "Sold" confirmation until the till payment is validated; harmonise POS-sold and SO-sold ticket
  status; auto-flip to Sold/Open when the (possibly settled-from-quotation) order is finally paid.
- **Value streams (inferred):** *Settle-Ticket-then-Confirm* — ticket settled onto a still-draft,
  non-zero `pos.order` → registration `to_pay`/draft → cashier tenders → order paid/done/invoiced →
  `_compute_registration_status` flips the attendee to `sold`/`open`.
- **Information concepts (auto):** `event.registration`, `pos.order`, `sale.order`.
- **Organization (auto):** none (inherits `pos_event`'s `group_pos_user` CRU + event groups).
- **Products (auto):** none.
- **Policies (inferred):** `auto_install=true` (activates only when both parents present); POS-linked
  registration is `sold`/`open` **only** when `pos_order_id.state in {paid,done,invoiced}`; `super()`
  first then correct; no revocation of its own (refund-to-cancel stays `pos_event`'s job).
- **Metrics (inferred):** `sale_status` distribution (sold vs to_pay) now reflecting real payment;
  count of POS-linked registrations awaiting payment.
- **Strategy:** `null` (human).

## 7. Classification

- **Value model: chain — primary activity.** Its substance is a **single side-effect on the in-store
  sell transaction**: it ties confirmation of an event-ticket sale to the POS order being paid — the
  Market-and-Sell "accept/fulfil the order" moment realised at a till. The dominant operation is the
  retail sale (ring/settle a ticket and tender payment), the 3.5 manage-sales-orders family that
  `point_of_sale`, `pos_sale` and `event_sale` all sit in; it merely corrects *when* the seat is
  counted as sold. It inherits the `chain`/`primary` class of **both** parents.
- **APQC: 3.0 Market and Sell Products and Services.** The artefact it governs (`event.registration`)
  belongs to the event subsystem — a value *network* on its own — but this module touches none of that
  mediation: it only reads `pos.order.state` and writes a sold/unsold flag, so its value logic is on
  the chain/selling side. **9.0 (finance) was rejected:** the trigger is a payment *state*, but the
  module manages no receivables/payments/entries — it consumes the already-computed paid state to
  decide a **sales** status.

## 8. Fit-to-Standard

- **Standard:** make a POS-sold ticket `Sold`/open only once its order is paid/done/invoiced; keep it
  `to_pay`/draft while unpaid; auto-flip on tendering (stored/precompute/compute_sudo on
  `pos_order_id.state`); harmonise the `pos_event` amount-based rule with `event_sale`'s
  sale-order-state rule; auto-install when both parents present.
- **Typical fits:** a venue/box-office that both rings walk-up tickets **and** settles pre-booked
  quotations at the same till; deposit-then-collect ticketing confirmed only on payment; deployments
  needing accurate sold-seat counts that exclude unpaid in-progress orders.
- **Common gaps:** **no UI of its own** (the change is silent); **no new refund/cancel behaviour**
  (`pos_event` still owns refund-to-cancel and `state='cancel'`); `'invoiced'` is treated as sold like
  paid/done (to-invoice-but-unpaid policies need an override); seat-availability broadcasting is
  unchanged (remains `pos_event`'s `_update_available_seat`).
- **Drive:**
  `env['event.registration'].search([('pos_order_id','!=',False)]).mapped(lambda r:(r.pos_order_id.state, r.sale_status, r.state))`;
  `o = env['pos.order'].search([('lines.event_registration_ids','!=',False),('state','=','draft')], limit=1); o.action_pos_order_paid(); print(o.lines.event_registration_ids.mapped('sale_status'))`
  (flips to `sold`); run `TestPoSEventSale.test_sale_status_event_in_pos` (two orders →
  `{'sold','to_pay'}`).

*Provenance: `extract_module.py` + `extract_frontend.py` + code-read of
`addons/pos_event_sale/models/event_registration.py` & `tests/test_frontend.py`, and the parent
computes in `addons/pos_event`, `addons/event_sale`, `addons/event_product`. Odoo 19.0.*
