# portal_rating — Reverse-Engineering Brief

**Module:** portal_rating  
**Category:** Services  
**Odoo version:** 19.0  
**Auto-install:** yes (activates whenever both `portal` and `rating` are installed)  
**Tier:** deep (≥3 code-read behavioral notes)

---

## What it does in one sentence

`portal_rating` bridges the `rating` and `portal` modules: it adds publisher-response comments to `rating.rating`, injects star-rating data and aggregate statistics into the portal chatter payload, and provides a `RatingPopupComposer` widget that lets customers submit and edit reviews from the portal.

---

## Architecture

### Python side (227 LOC, 3 model extensions, 1 route)

**`rating.rating` extension** adds three fields: `publisher_comment` (Text), `publisher_id` (Many2one → res.partner), `publisher_datetime` (Datetime). These are readonly by design — they are auto-populated on every write that sets `publisher_comment`:

- `_synchronize_publisher_values` — auto-fills `publisher_id` (current user's partner) and `publisher_datetime` (now) if missing.
- `_check_synchronize_publisher_values` — dual-path authorization: either the user holds `website.group_website_restricted_editor` (resolved via `ir.model.data._xmlid_to_res_id`, so the module does not hard-depend on `website`) OR they have `write` access on the rated document (checked via `records.check_access('write')`).

**`mail.message` extension** enriches the portal chatter payload at runtime:

- `_portal_get_default_format_properties_names` adds `rating` and `rating_value` to the requested properties set when `rating_include=True` is in options.
- `_portal_message_format` performs a `sudo` `search_read` on `rating.rating` filtered by `message_id`, builds a per-message `rating_id` dict (publisher_comment, avatar URL `/web/image/res.partner/<id>/avatar_128/50x50`, formatted datetime), and calls `rating_get_stats()` on the related document model if that method exists, attaching aggregate stats as `rating_stats`. None of this is visible in ORM metadata.

**`PortalChatter` extension** (controllers):

- `_get_non_empty_message_domain` — adds `Domain('rating_value', '!=', False)` via OR so that messages with only a star rating (no text) are shown.
- `_setup_portal_message_fetch_extra_domain` — optionally adds `Domain('rating_value', '=', float(data['rating_value']))` for client-requested star filtering.

**`/website/rating/comment`** (auth=user, jsonrpc) — accepts `rating_id` + `publisher_comment`, calls `rating.rating.write` (triggering the access gate), returns a formatted publisher block.

### JS/Frontend side (9 files, 7 patches, 1 interaction)

All behavior is delivered through patches on existing portal/mail components — no new OWL components are introduced:

- **`Thread.prototype` patch** — unconditionally injects `rating_include=true` into every non-discuss.channel chatter fetch, and forwards `rating_value` when a star filter is active.
- **`RatingPopupComposer`** (registered in `public.interactions`) — renders a static star average widget and opens a modal wrapping the portal `Composer`. On reload (triggered by `reload_rating_popup_composer` bus event), it merges updated `rating_avg`/`rating_count` and adjusts the send button label (`'Update review'` vs `'Post review'`).
- Additional patches on `Chatter`, `Composer`, `Message`, `PortalComposer`, and `Store` integrate rating data display into the existing chatter UI.

---

## Value model & APQC

**Value model:** network — value lies in connecting customer reviewers with business publishers; both parties gain from the exchange.  
**APQC:** 3.0 Market and Sell Products and Services — public ratings are a sales signal that supports product/service evaluation by prospects.

---

## Key behavioral facts not visible in metadata

1. **Access gate on publisher comment**: writing `publisher_comment` triggers a dual-path check (website editor group OR document write access) — this is a runtime enforcement invisible from field definitions alone.
2. **Runtime payload enrichment**: `mail.message._portal_message_format` injects rating data and document-level aggregate stats into the chatter payload dynamically — no stored field holds this data.
3. **Domain extension for rating-only messages**: messages with only a star value (no body text) would be hidden by the default non-empty message filter; `portal_rating` extends that domain to include them.
4. **Frontend rating filter**: `Thread.prototype.getFetchParams` passes `rating_value` to the server, enabling star-rating-filtered chatter without any client-side data model change.
5. **Optional website bridge**: the `group_website_restricted_editor` check is conditional (`if editor_group`) — the module works cleanly without `website` installed.

---

## Fit-to-standard

| Capability | Coverage |
|---|---|
| Star rating display with avg + count | Standard |
| Rating-filtered chatter view | Standard |
| Publisher response comments (auto-stamped) | Standard |
| Portal review submit/edit popup | Standard |
| Moderation workflow | Gap — no approve/reject |
| Publisher notification on new rating | Gap — upstream module only |

---

## Open questions

1. Does `portal_rating` interact with `helpdesk` or `website_livechat` rating flows, or only with modules that explicitly implement `rating_get_stats`?
2. Is the `token` field in `RatingPopupComposer` options validated server-side by the upstream `rating` module, or is auth solely by user session?
3. How does the star-value filter interact with chatter pagination on large threads — does the displayed count reflect the filtered subset?
