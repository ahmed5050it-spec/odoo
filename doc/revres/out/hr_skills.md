# hr_skills — Reverse-Engineering Brief

The **hr_skills** module is Odoo's employee competency and resume manager ("Manage skills, knowledge and resume of your employees", category *Human Resources/Employees*). It is an `application: true`, **`auto_install: true`** module that activates automatically once `hr` is present, grafting skills, skill levels, certifications, job-position skill requirements, and a resume/CV onto the employee record. Its single dependency is **hr**: every model hangs off `hr.employee`, `hr.job`, `hr.department`, or `resource.resource`. The conceptual core is the abstract `hr.individual.skill.mixin`, shared by `hr.employee.skill` and `hr.job.skill`, which implements an append-only, validity-windowed history of who held which skill at what level and when. It is a **support** subsystem feeding talent data to the rest of HR.

## Role & Dependencies

- **hr** — the only declared dependency; supplies `hr.employee`, `hr.employee.public`, `hr.job`, `hr.department`, `resource.resource` and the `hr.group_hr_user` group that this module extends (no own groups defined).

Capability added on top: a competency catalog (skill types → skills → levels with 0-100 progress), certification tracking with validity periods, per-job required skills, an employee resume timeline + printable CV, and skill/certification analytics — none of which `hr` provides alone.

## Data Model (the ERM)

| _name | _description | #fields | Key relations |
|-------|--------------|--------:|---------------|
| `hr.individual.skill.mixin` | Skill level (abstract base) | 12 | skill_id→hr.skill, skill_level_id→hr.skill.level, skill_type_id→hr.skill.type |
| `hr.employee.skill` | Skill level for employee | 13 | employee_id→hr.employee (+mixin rels) |
| `hr.job.skill` | Skills for job positions | 13 | job_id→hr.job (+mixin rels) |
| `hr.skill.type` | Skill Type | 8 | skill_ids→hr.skill, skill_level_ids→hr.skill.level |
| `hr.skill` | Skill | 4 | skill_type_id→hr.skill.type |
| `hr.skill.level` | Skill Level | 5 | skill_type_id→hr.skill.type |
| `hr.resume.line` | Resume line of an employee | 17 | employee_id→hr.employee, line_type_id→hr.resume.line.type |
| `hr.employee.skill.history.report` | Employee Skills Report (SQL view) | 5 | employee_id→hr.employee, skill_id→hr.skill |

The **mixin** `hr.individual.skill.mixin` (`_inherit` without its own concrete table) is the polymorphic heart: both `hr.employee.skill` and `hr.job.skill` add only a single linking Many2one (`employee_id`/`job_id`) and override `_linked_field_name()`. The module also carries **inherit-only extensions** of `hr.employee`, `hr.employee.public`, `hr.job` and `resource.resource`. Three `_auto = False` SQL-view report models (`hr.employee.skill.history.report`, `hr.employee.skill.report`, `hr.employee.certification.report`) provide analytics, the latter two inheriting `hr.manager.department.report`. The field-type mix is **relational-heavy** (23 Many2one, 13 One2many, 3 Many2many) over the catalog graph, with Boolean/Integer texture for flags and progress — a master-data subsystem, not a transactional one.

## Behavior & Surfaces

- **Routes:** a single `auth=user`, `type=http` route `/print/cv` (controllers/main.py) rendering the qweb CV report `report.hr_skills.report_employee_cv`. No JSON-RPC/public API.
- **Views:** form 6, **list 14**, kanban 1, search 4, calendar 1. The list-dominant mix plus a custom `skills_graph` view and the skills/resume OWL widgets signals an embedded-editor UX inside the employee form rather than standalone screens.
- **Security posture:** 20 access rules, 11 record rules, **0 own groups** — it reuses `hr.group_hr_user` (full CRUD on catalog) vs `base.group_user` (read-all, self-service create on own skills), a dual-tier own-vs-HR visibility model.

## Value-Configuration Classification

**Value model: `support`** (Stabell & Fjeldstad cross-cutting infrastructure), **activity_class: support**. hr_skills neither transforms inputs into a product (chain) nor solves a recurring customer problem (shop) nor mediates exchange between parties (network); it maintains the firm's **human-capital master data** — skills, levels, certifications, resumes — that other activities consume. The signals are unambiguous: a lone `hr` dependency, `auto_install: true`, catalog/mixin-centric models, HR/manager stakeholders, and a CV-print route as the only outward surface. It is a support activity in the value system, supplying competency information rather than participating in a primary document flow.

## APQC PCF Hint

**7.0 Develop and Manage Human Capital** — specifically **7.3 Manage employee development** (competency/skill definition, assessment, certification tracking). The catalog + employee-skill + job-skill + certification structure maps directly to competency management within HR; no row exists in `apqc_odoo_map.tsv`, which only covers chain/shop primary flows — consistent with a support subsystem.

## How to Drive It

Use the **run-odoo** skill (`odoo shell`):

- `env['hr.skill.type'].search([]).mapped(('name','levels_count','is_certification'))` — inspect the competency catalog and which types are certifications.
- `env['hr.employee.skill'].search([], limit=5).mapped(('employee_id','skill_id','skill_level_id','valid_from','valid_to'))` — observe the validity-windowed skill records (the history mechanism).
- `env['hr.employee.skill.history.report'].search([], limit=5)` — query the SQL-view timeline behind the skills graph.

Route (auth=user, http): `curl http://localhost:8069/print/cv` from an authenticated session to render an employee CV PDF.

## Open Questions

- **No dedicated log model (code-confirmed):** there is no `hr.employee.skill.log`; history is reconstructed from `valid_from`/`valid_to` windows and the `hr.employee.skill.history.report` SQL view — confirm no separate audit-log model is expected.
- **Versioned-write semantics:** `_get_transformed_commands`/`_write_individual_skills` archive-then-create rather than write in place; edge cases (sub-24h delete vs archive, certification overlap) warrant a runtime check.
- **Certification cron:** `_add_certification_activity_to_employees` schedules `mail.activity` reminders on a 3-month horizon — its trigger cadence and responsible-user resolution are not in metadata.
- **Resume timeline source:** `get_internal_resume_lines` derives job-title history from `hr.employee.version_ids`; its interaction with employee-versioning/contract modules should be verified in code.

---
*Provenance: facts from `doc/revres/extract_module.py` (facts/hr_skills.facts.json) + `extract_frontend.py`; behavioral notes from reading `addons/hr_skills/models/{hr_individual_skill_mixin,hr_employee_skill,hr_skill,hr_skill_type,hr_skill_level,hr_employee,hr_job_skill}.py` and `report/hr_employee_skill_history_report.py`. Odoo 19.0.*
