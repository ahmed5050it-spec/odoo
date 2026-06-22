# hr_recruitment_skills — Architecture Brief

> Module: `hr_recruitment_skills` · Category: Human Resources/Recruitment · Depends: `hr_skills`, `hr_recruitment` · `auto_install: true`
> Value model: **support** · Activity class: **support** · APQC: **7.0 Develop and Manage Human Capital**
> Odoo 19.0 · Facts: `doc/revres/facts/hr_recruitment_skills.facts.json` · Frontend: `doc/revres/frontend/hr_recruitment_skills.frontend.json`

## 1. Summary

`hr_recruitment_skills` **bridges the skills catalogue (`hr_skills`) onto
recruitment (`hr_recruitment`)**. It adds per-applicant **skill lines**
(`hr.applicant.skill`, inheriting `hr.individual.skill.mixin`), a **skill+degree
matching engine** that scores how well an applicant fits a job (`matching_score`,
`matching_skill_ids`, `missing_skill_ids`), a **"search matching applicants"**
workflow on the job, and — the key cross-model effect — **propagation of applicant
skills to the hired employee** (and to the linked talent-pool applicant). It owns
**one persistent model** (`hr.applicant.skill`, 1 own field + the mixin) and
extends `hr.applicant`/`hr.job` (**0 routes, 2 ACL + 2 ir.rule**, ~268 py LOC of
model code inside a 1447-LOC tree that is mostly tests, `auto_install: true`).

## 2. Structure (evidence)

- **Models (1 own + 2 inherit):** `hr.applicant.skill` (inherits
  `hr.individual.skill.mixin`; `applicant_id` cascade; `_rec_name='skill_id'`,
  `_order='skill_type_id, skill_level_id desc'`); `hr.applicant` (+`applicant_skill_ids`,
  computed `current_applicant_skill_ids`, `skill_ids` (stored), `matching_skill_ids`/
  `missing_skill_ids`/`matching_score`); `hr.job` (+`applicant_matching_score`
  Float, `action_search_matching_applicants`).
- **Routes:** **0** — no web/RPC surface; no external calls (gap #7 empty).
- **Security:** 2 ACL — `hr.applicant.skill` full CRUD for
  `group_hr_recruitment_interviewer`, plus `hr.job.skill` for
  `group_hr_recruitment_user` — and 2 `ir.rule`: interviewers see only skills of
  applicants on jobs they interview; `group_hr_recruitment_user` gets `(1=1)`.
  No own `res.groups`.
- **Views:** **1 form / 1 list** (+ inheritance, xml_loc=341): skills o2m + match
  widgets on the applicant form; `applicant_matching_score` progressbar on the job
  list; the matching-applicants list view; the `action_applicant_search_applicant`
  server action bound to the job form.

## 3. Frontend (gap #3)

**2 JS / 2 XML**, bundle `web.assets_backend`. **1 OWL component**, `SearchJobApplicant`
(`static/src/components/search_job_applicant_menu/*` — a cog/search-menu entry
driving the matching-applicant search), and **1 registry add**,
`fields:skill_match_gauge_field` (`static/src/fields/skill_match_gauge_field/*` —
a field widget rendering `matching_score` as a gauge on the applicant/job views).
`skills_one2many_recruitment.scss` styles the skills o2m. No patches; no unit-test
bundle.

## 4. Behavior (beyond metadata)

- **Applicant → employee skill propagation (code-read):** at hire,
  `hr.applicant._get_employee_create_vals()` (override of the `hr_recruitment` base)
  appends `employee_skill_ids = [(0,0,{skill_id, skill_level_id, skill_type_id})
  for applicant_skill in self.applicant_skill_ids]`, so every applicant skill is
  copied onto the new `hr.employee` inside the standard *Create Employee* flow. This
  hire-time copy is invisible to metadata.
- **Match scoring (code-read):** `hr.applicant._compute_matching_skill_ids`
  (`@depends_context('matching_job_id')`) computes, against the job's `job_skill_ids`
  + `expected_degree`: `job_total = Σ level_progress + degree.score*100`; per matched
  current skill it credits `min(level_progress, required*2)` (**over-qualification
  capped at 2×**), adds the diploma score when the job weights a degree, and sets
  `matching_score = round(applicant_total/job_total*100)`, with
  `matching_skill_ids` = overlap and `missing_skill_ids` = required − matched.
  `hr.job._compute_applicant_matching_score` (`@depends_context('active_applicant_id')`)
  is the mirror, shown as a progressbar on the job list.
- **Talent-search workflow (code-read):** `hr.job.action_search_matching_applicants`
  injects `matching_job_id` into context, swaps in a custom list view, and applies
  domain `[('job_id','!=',self.id), ('skill_ids','in', self.job_skill_ids.skill_id.ids)]`
  — applicants on *other* jobs whose skills overlap this job — every row re-scored
  under `matching_job_id`. `hr.applicant.action_add_to_job` then writes the chosen
  applicant onto `job_id` + `stage_job0` and opens that job's applications.
- **Versioning + talent-pool mirroring (code-read):** `hr.applicant.write` pops the
  skill commands and runs them through `hr.applicant.skill._get_transformed_commands`
  (the mixin's rule engine: one active skill per `skill_id`, **updates archive the
  old line and create a new one** via `valid_from`/`valid_to`, certifications coexist
  if date ranges differ) before `super`. `current_applicant_skill_ids` (via
  `_get_current_skills_by_applicant`) drops expired lines but keeps the most-recent
  certification when all are expired. If the applicant is pool-linked
  (`pool_applicant_id` and not `is_pool_applicant`), the same edits are mirrored to
  the pool applicant by re-keying each ORM command from the applicant's skill-line
  ids to the pool's ids (`_map_applicant_skill_ids_to_talent_skill_ids`).
- **External integration (static, gap #7):** none.

## 5. IT architecture

- **Application:** bridges `hr_skills` onto `hr_recruitment` — applicant skill
  lines, applicant↔job matching/scoring, and skill propagation to the hired
  employee / talent pool.
- **Data objects:** `hr.applicant.skill` + inherits on `hr.applicant`, `hr.job`.
- **Key relations:** `hr.applicant.skill → hr.applicant` (cascade) + mixin →
  `hr.skill`/level/type/`valid_*`; `hr.applicant → hr.applicant.skill` →
  `hr.skill` (skill/matching/missing m2m); `hr.job → hr.job.skill`; hire-time
  `applicant_skill_ids → employee_skill_ids`; pool `pool_applicant_id` mirror.
- **Flows:** match (applicant view / job list) → score; search → skill-overlap
  domain; promote → `action_add_to_job`; hire → `_get_employee_create_vals`; edit →
  `_get_transformed_commands` (versioned) → pool mirror.

## 6. Business architecture

- **Capabilities (inferred):** capture skills/certifications (levels + validity) on
  applicants; score applicant↔job fit; rank jobs-for-applicant and
  applicants-for-job; search candidates by skill match; carry skills to the
  employee on hire and the talent-pool applicant on edit; version skill changes.
- **Value streams (inferred):** *Skill-Match-to-Shortlist* (job skills →
  `action_search_matching_applicants` → scored candidates → `action_add_to_job`) and
  *Applicant-Skills-to-Employee* (applicant skills → hire → `employee_skill_ids`).
- **Information concepts (auto):** `hr.applicant.skill`; the skill match
  (`matching`/`missing`/`matching_score`); `hr.skill`/`hr.job.skill`; the talent-pool
  applicant.
- **Policies (inferred):** interviewers see only their applicants' skills (recruiters
  all); `applicant_matching_score` interviewer-only; one active skill per `skill_id`
  with archive-on-update + validity; over-qualification capped at 2×; pool-linked
  edits mirrored.
- **Strategy:** `null` (human). **Organization/Products:** none own.

## 7. Classification

- **Value model: support** — acquiring and developing the workforce; shared HR/firm
  infrastructure (Stabell & Fjeldstad *support*; Porter support activity). It owns
  no chain/shop/network business object; its substance is matching people's
  competencies to jobs.
- **Activity class: support.**
- **APQC: 7.0 Develop and Manage Human Capital** — within 7.0 it straddles **7.1
  Recruit, source and select employees** (skill-based candidate matching/search,
  hiring) and competency management (capturing and carrying forward employee
  skills), so 7.0 is the umbrella with a recruitment-skills emphasis. `8.0 Manage IT`
  rejected (no IT plumbing/routes/external calls); `3.0 Market & Sell` rejected
  (nothing is sold).

## 8. Fit-to-Standard

- **Standard:** applicant skills/certifications with levels + validity; weighted,
  over-qualification-capped match score (incl. expected degree); matching/missing
  breakdown + a match gauge; *Search Matching Applicants* (skill-overlap domain) +
  *Add to Job*; skill propagation to the hired employee and the talent pool;
  versioned skill history.
- **Typical fits:** skill-based shortlisting/ranking; sourcing existing applicants
  for a new role; pre-populating a hired candidate's employee skills; keeping a
  talent pool in sync as candidates are re-assessed.
- **Common gaps:** deterministic level/degree formula (no ML/semantic matching —
  synonyms/adjacent skills uncredited); jobs without declared skills/degree score
  nothing; scoring is context-driven and non-stored (recomputed per view, not
  historically aggregable); pool mirroring depends on `hr_recruitment`'s
  `pool_applicant_id` linkage; no external assessment/test integration.
- **Drive:** `a.with_context(matching_job_id=a.job_id.id)` then read
  `matching_score`/`matching_skill_ids`/`missing_skill_ids`;
  `j.action_search_matching_applicants()['domain']`;
  `a._get_employee_create_vals()['employee_skill_ids']`;
  `env['hr.applicant.skill']._get_current_skills_by_applicant()`.
