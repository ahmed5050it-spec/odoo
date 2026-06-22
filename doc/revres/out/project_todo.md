# project_todo — Architecture Brief

> Module: `project_todo` · Category: Productivity/To-Do · Depends: `project` · `auto_install: true`
> Value model: **shop** (inherited from project) · Activity class: **support** · APQC: **5.0 Deliver Services** (personal to-do = a private project.task; consistent with the project_* family)
> Odoo 19.0 · Facts: `doc/revres/facts/project_todo.facts.json` · Frontend: `doc/revres/frontend/project_todo.frontend.json`

## 1. Summary

`project_todo` is a **personal To-Do / memo app built by reusing `project.task`**.
A "to-do" is simply a `project.task` with **no `project_id` and no `parent_id`**,
assigned to the user — private by default via one record rule. The module adds a
dedicated To-Do UI (kanban/list/form/calendar/activity grouped by *personal*
stages), an "Add a To-Do" wizard that also schedules a `mail.activity`, a systray
split that separates To-Do from Task activity stacks, and a one-click **convert a
to-do into a real project task**. It owns no new persistent model: **1 TransientModel
(`mail.activity.todo.create`), 2 inherits (`project.task`, `res.users`), 0 routes,
4 access rules + 1 record rule, ~589 py LOC**. Its substance is the **auto-naming,
the activity systray SQL split, the convert/onboarding side-effects, and the
personal-stage UI** — none of which metadata reveals.

## 2. Structure (evidence)

- **Models (1 own + 2 inherit):** `mail.activity.todo.create`
  (`TransientModel`, `wizard/…` — `summary`, `date_deadline` (req, default today),
  `user_id` (default self, readonly), `note` Html; method `create_todo_activity`);
  `project.task` (`models/project_task.py` — **no fields**; `create`,
  `action_convert_to_task`, `get_todo_views_id`); `res.users`
  (`models/res_users.py` — `_get_activity_groups`, `_onboard_users_into_project`,
  `_generate_onboarding_todo`).
- **Routes:** **0** — no web/RPC surface; backend ORM + views only.
- **Security:** 4 `ir.model.access` rows (`base.group_user` on `project.task.type`,
  `project.task`, `project.tags`, and the wizard); **1 `ir.rule`**
  `task_edition_rule_internal` — the privacy gate: full access to
  `[('project_id','=',False),('user_ids','in',user.id),('parent_id','=',False)]`.
  No new groups (reuses project's).
- **Views:** all on `project.task` — kanban/list/form/calendar/activity + quick-create
  + conversion form, each with a dedicated `js_class`. The main `act_window`
  `project_task_action_todo` hard-codes the to-do domain and `path='to-do'`.

## 3. Frontend (gap #3)

**14 JS / 3 XML**, bundled in `web.assets_backend` (+ test/unit bundles). **1 OWL
widget** — `TodoChatterPanel` (a toggleable side chatter driven by a
`TODO:TOGGLE_CHATTER` bus event) — and **1 patch**, `ActivityMenu.prototype`.
The ActivityMenu patch adds an *Add a To-Do* command (`alt+shift+t`) that ORM-creates
the `mail.activity.todo.create` wizard and opens it in a `FormViewDialog`, and routes
`is_todo` systray groups to To-Do-specific views fetched via
`project.task.get_todo_views_id`. Registry adds: the `todo_done_checkmark` field
widget, the `todo_chatter_panel` view widget, and `todo_form/todo_list/
todo_conversion_form/todo_activity_wizard` `js_class` views. The kanban/list/calendar
group by **`personal_stage_type_id`** (project's per-user `project.task.stage.personal`
relation) — the mechanism that lets project-less to-dos still have draggable columns.

## 4. Behavior (beyond metadata)

- **Auto-naming (code-read):** `project.task.create` (`model_create_multi`) — for
  vals with **no name AND no project_id AND no parent_id** (a bare private to-do),
  it derives the title from the description: `html2plaintext` → strip → drop `*` →
  first line (`partition('\n')[0]`) → truncate to 97 + `'...'` if >100; with no
  description it falls back to `_('Untitled to-do')`. Scoped precisely to the
  project-less/parentless case so real project tasks are untouched.
- **Convert to task (code-read):** `action_convert_to_task` (`ensure_one`) sets
  `company_id = project_id.company_id` and re-opens the same record in a form. The
  conversion form (`todo_conversion_form`, surfaced by `TodoFormController` only when
  the user has `project.group_project_user` **and** the record has no `project_id`)
  makes `project_id` **required** — once written, the task **leaves the to-do domain**
  and gains its project stage/company. It is an **in-place re-scoping** of one
  `project.task`, no copy.
- **Systray To-Do/Task split (code-read):** `res.users._get_activity_groups` removes
  the aggregated `project.task` group and runs **raw SQL** over `mail_activity JOIN
  project_task` for the user, bucketing by `BOOL(t.project_id) AS is_task` (False =
  to-do) and today/overdue/planned (from `MIN(date_deadline)`), then rebuilds **two**
  systray stacks — *To-Do* (icon from this manifest) and *Task* (from project) —
  with per-state counts. The split is SQL-driven and invisible to metadata.
- **Onboarding seeding (code-read):** the `post_init_hook` `_todo_post_init` calls
  `res.users.search([('share','=',False)])._generate_onboarding_todo()`, and
  `_onboard_users_into_project` is overridden so new users also get one.
  `_generate_onboarding_todo` renders QWeb `project_todo.todo_user_onboarding` per
  user (in their lang), titles it *"Welcome %s!"*, and creates a `project.task`
  `with_user(SUPERUSER_ID)` + `mail_auto_subscribe_no_notify=True` — every non-portal
  user is **silently seeded a private welcome to-do** on install/onboarding.
- **Wizard dual side-effect (code-read):** `mail.activity.todo.create.create_todo_activity`
  creates **both** a `project.task` (name=summary, description=note, deadline,
  `user_ids`) **and** a `mail.activity` on it (default activity type), then returns a
  `display_notification`. One submit → a to-do record **plus** a scheduled activity.
- **Static frontend note (static):** the personal-stage kanban + the `ActivityMenu`
  patch above are the load-bearing client behaviour; the conversion-form controller
  merely autofocuses the project field.

## 5. IT architecture

- **Application:** personal To-Do app; auto-installed productivity layer over
  `project`, reusing `project.task`.
- **Data objects:** `project.task` (as a To-Do), `mail.activity.todo.create`,
  `res.users`, `mail.activity` (created), `project.task.stage.personal`.
- **Key relations:** `project.task (project_id=False) == To-Do`;
  `project.task → res.users` (`user_ids`); `→ project.task.type` via
  `project.task.stage.personal` (`personal_stage_type_id`);
  `mail.activity.todo.create →` creates `project.task` + `mail.activity`;
  `ir.rule → project.task` (own private project-less top-level tasks).
- **Flows:** create with no name/project/parent → auto-name; `action_convert_to_task`
  → set company + write `project_id` → becomes a project task;
  `_get_activity_groups` → SQL split To-Do vs Task systray; wizard → task + activity;
  install/onboarding → seeded welcome to-do.

## 6. Business architecture

- **Capabilities (inferred):** capture private to-dos/memos; auto-title from content;
  track via personal kanban stages; split to-do vs task activities; create a to-do +
  scheduled activity; promote a to-do into a project task; onboard new users with a
  starter to-do.
- **Value streams (inferred):** *Personal-task lifecycle* — capture a private to-do →
  auto-name + self-assign → organise by personal stage/deadline/tags → mark done, or,
  when it turns collaborative, convert to a project task and hand off to Project.
- **Information concepts (auto):** `project.task` (as a To-Do), `personal_stage_type_id`
  / `project.task.stage.personal`, `mail.activity`, `mail.activity.todo.create`,
  `res.users`.
- **Organization (auto):** `base.group_user` (every internal user — no dedicated group).
- **Products (auto):** none.
- **Policies (inferred):** privacy (`task_edition_rule_internal`: own project-less
  top-level tasks only); to-do identity (`project_id`=False ∧ `parent_id`=False;
  writing a project converts it); auto-naming; silent onboarding seeding.
- **Metrics (inferred):** systray total/today/overdue/planned counts; personal-stage
  distribution; open vs closed to-dos.
- **Strategy:** `null` (human).

## 7. Classification

- **Value model: shop** — by inheritance. A to-do *is* a `project.task` (it reuses
  project's personal kanban stages, the activity mixin and chatter — the same
  intensive-technology value-shop model) and can be promoted into a real project task
  (`action_convert_to_task`).
- **Activity class: support** (not primary) — this is a **personal-productivity /
  self-organisation utility for the workforce**, not a customer-facing delivery
  engine: no revenue document, no portal/customer surface, `auto_install` and
  universal (`base.group_user`). It enables employees to organise their own work and
  hand it off to Project — firm-infrastructure / workforce enablement.
- **APQC: 5.0 Deliver Services** — a personal to-do is a `project.task` reused for private work, consistent with the entire `project_*` family; workforce-productivity (7.0) and generic-tooling (13.0) readings were weighed and rejected
  maps best here; Project's own **5.0 Deliver Services** is noted because the concrete
  object *is* `project.task`. **13.0 Develop & Manage Business Capabilities** (the
  generic "productivity tooling" bucket) was weighed but rejected: the feature is for
  end-users doing their own work, closer to workforce/personal productivity than to
  building enterprise capabilities.

## 8. Fit-to-Standard

- **Standard:** private personal to-dos backed by `project.task` (private-by-default
  record rule); quick-create with `#tags`/`@user`/`!` shortcuts + auto-naming;
  personal kanban/list/calendar/activity by per-user stage; mark-as-done widget +
  description version history; *Add a To-Do* wizard that also schedules an activity;
  systray To-Do/Task split; convert-to-task; starter to-do for new users.
- **Typical fits:** employees keeping a personal task/memo list inside Odoo; turning
  a self-note into team work by converting it once it needs collaboration;
  reminder-style activities alongside the to-do; any internal user (zero config).
- **Common gaps:** no own analytics on to-dos (borrows project's task analytics only
  after conversion); single-level (no subtasks on personal to-dos); sharing is
  all-or-nothing via assignees (no granular portal-style permissions); conversion is
  one-way/in-place; fixed onboarding template; cannot run standalone (`auto_install`
  on project).
- **Drive:** `env['project.task'].create({'description':'<p>Buy milk</p>'})` →
  auto-named private to-do; `env['mail.activity.todo.create'].create({'summary':'Call
  back','date_deadline':fields.Date.today()}).create_todo_activity()`;
  `env.user._get_activity_groups()` (the systray split); `t.action_convert_to_task()`
  then write a `project_id`; UI: To-Do app (`/odoo/to-do`).
