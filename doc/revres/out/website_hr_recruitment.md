# website_hr_recruitment — Reverse-Engineering Brief

**Online Jobs** is the public-facing careers site for Odoo recruitment. It publishes
`hr.job` positions on the website, exposes a searchable/filterable `/jobs` listing and
per-job detail pages, and lets anonymous visitors apply online — each submission creating
an `hr.applicant` (with an `ir.attachment` resume) straight into the recruiter pipeline.
It is an `application: true` module that `auto_install`s with `hr_recruitment` +
`website_mail`, so it is the storefront layered on top of the back-office recruitment engine.

## Role & Dependencies

- **hr_recruitment** — supplies `hr.job` / `hr.applicant` / `hr.recruitment.stage`; this
  module extends them with website publishing and the public apply channel.
- **website_mail** — brings `website` (builder, pages, fuzzy search, SEO mixins) plus the
  mail layer for templated candidate notifications.

Capability added: an SEO-optimized public careers website + anonymous online application
intake, turning the internal recruitment pipeline into a candidate-facing acquisition channel.

## Data Model (the ERM)

| Model (`_inherit`) | Role | Key additions |
|---|---|---|
| `hr.job` (+`website.seo.metadata`, `website.published.multi.mixin`, `website.searchable.mixin`) | **central** published position | `website_published`, `website_description`, `job_details`, `published_date`, `full_url` (6 fields) |
| `hr.applicant` | online application | `website_form_input_filter`, `extract_data` (form intake) |
| `hr.department` | public facet | `display_name` sudo-computed for portal/public |
| `hr.recruitment.source` | channel | `url` computed UTM tracker link |
| `website` | search provider | `_search_get_details('jobs')`, suggested controller |
| `website.page` | cache control | disable cache on `/job-thank-you` |

Only `hr.job` adds stored fields; the rest are thin mixin/extension models (`_inherit`
without `_name`). The field mix is attribute-light (3 Html, 1 Bool, 1 Date, 1 Char) — the
weight is in **controllers and templates** (708 py / 2881 xml LOC), not schema.

## Behavior & Surfaces

- **Routes (6):** `/jobs` + `/jobs/page/<int:page>` (public listing), `/jobs/<job>`
  (public detail), `/jobs/detail/<job>` (301 → canonical slug), `/jobs/apply/<job>`
  (public apply page), `/jobs/add` (jsonrpc, auth=user — create draft job),
  `/website_hr_recruitment/check_recent_application` (jsonrpc public — dedup warning).
  Surface is overwhelmingly **anonymous public web**.
- **Listing logic:** fuzzy site-search + in-Python filtering by country / department /
  office / contract-type / industry with live per-facet counters and geo-IP country
  pre-selection; 12 jobs/page.
- **Apply submission:** posts to `/website/form/` (`data-model_name="hr.applicant"`);
  `website_form_input_filter` checks the job is active and stamps the first non-folded
  stage; resume becomes an `ir.attachment`; postable fields are whitelisted via
  `formbuilder_whitelist`.
- **Views:** 1 form + 1 kanban (backend publish controls) — the real UX is QWeb website
  templates, not backend views.
- **Security:** 4 ACLs, **4 record rules**, 1 group. Public/portal can read `hr.job`
  only where `website_published = True`; recruiters see all.

## Value-Configuration Classification

- **value_model: `network`** — a website storefront/portal that **mediates** between job
  seekers and the hiring organization over shared infrastructure (careers site + SEO +
  apply channel). Public web/portal routes, not a chain document-flow or a shop engagement.
- **activity_class: `primary`** — it is the front-facing acquisition channel that directly
  captures candidates (`hr.applicant` creation), the inbound edge of talent acquisition.
- Contrast: the parent `hr_recruitment` is `support`; this module is the candidate-facing
  network/primary front end on top of it.

## APQC PCF Hint

**7.0 Develop and Manage Human Capital** — specifically **7.1 Recruit, source and select
employees**: the online sourcing/application channel feeding the recruiter pipeline.

## How to Drive It

Use the **run-odoo** skill. Publish-gated reads and the public form are the things to poke:

```
curl -sS http://localhost:8069/jobs | head -40            # public listing
curl -sS 'http://localhost:8069/jobs?department_id=1'     # facet filtering
# odoo shell:
env['hr.job'].sudo().search([('website_published','=',True)]).mapped(('name','full_url','published_date'))
env['hr.job'].with_user(env.ref('base.public_user')).search([])   # ir.rule → only published
env['hr.applicant'].search([('job_id','!=',False)], limit=5).mapped(('partner_name','job_id.name','stage_id.name'))
env['hr.recruitment.source'].search([], limit=5).mapped('url')    # UTM tracker URLs
```

## Open Questions

- Exact apply-form fields vs the `formbuilder_whitelist` — the form is website-editor
  customizable at runtime.
- Whether multi-website (`website_id`) scoping publishes different job subsets per site.
- Real published-job / applicant volumes (runtime extract returned 0 rows; only demo data).
- How `hr_recruitment_survey` / `hr_recruitment_extract` extend the public flow when co-installed.

---
*Provenance: `extract_module.py` + `extract_frontend.py` facts, code-read of
`controllers/main.py`, `models/hr_job.py`, `models/hr_applicant.py`, templates &
security. Odoo 19.0.*
