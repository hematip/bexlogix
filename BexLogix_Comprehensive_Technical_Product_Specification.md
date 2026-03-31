# BexLogix — Comprehensive Technical Product Specification

## Document Status

**Type:** Comprehensive technical product specification  
**Language:** English  
**Audience:** Product owner, technical lead, Codex/code generation workflows, implementation partner, supervisor/advisor, internal stakeholders  
**Version intent:** MVP architecture and operational specification  
**Scope:** End-to-end explanation of what BexLogix is intended to be, how it should work, how it should look, what technical architecture it should follow, what data it should manage, what user flows it should support, and how the MVP should evolve

---

# 1. Executive Summary

BexLogix is intended to be a **UI-first internal operational web application** for visit planning, field execution, telesales follow-up, and day-to-day managerial monitoring.

The business motivation behind the product is straightforward: a company such as **Zar Group** has many stores, a limited number of visitors, and an operational need to decide every day:

- which stores should be visited
- which visitor should go to which stores
- in what order those stores should be visited
- what happened in each visit
- which failed visits should move into telesales
- how leadership can monitor the full process from one place

The MVP is not intended to be a fully mature enterprise platform. It is intended to be a **clean, operationally meaningful, role-based web tool** that turns a semi-manual process into a structured workflow.

At its heart, BexLogix is designed to manage the following operational chain:

**Import -> Schedule -> Assign -> Route -> Visit -> Telesales -> Monitor -> Export**

The system is meant to support a realistic internal workflow while remaining simple enough to build, test, demonstrate, and iterate quickly.

---

# 2. Product Vision

The product vision is to provide a company with a practical internal system where managers and operational staff can coordinate store visits and follow-ups without relying on fragmented spreadsheets, disconnected communication, or weak manual tracking.

The intended experience is:

- managers configure the operational day
- visitors receive their route and execute their work
- telesales handles failed physical visits
- supervisors monitor without interfering
- reporting is available at the end of the day
- all of this happens inside one coherent application

This is not simply a “dashboard.”  
It is a **workflow engine with a human-operable interface**.

---

# 3. Business Problem Being Solved

The system is designed to solve a set of recurring operational inefficiencies:

## 3.1 Store Coverage Inefficiency
Without a structured planning engine, stores may be:
- visited too late
- visited too often
- skipped unintentionally
- assigned inconsistently across visitors

## 3.2 Visitor Capacity Waste
Visitors have limited daily capacity. If the system does not plan intelligently:
- routes are weak
- store distribution is unbalanced
- high-priority stores may be missed
- low-value movement consumes time

## 3.3 Weak Visit Outcome Tracking
If a visit happens but there is no structured outcome tracking:
- management cannot distinguish success from failure
- stores do not re-enter the schedule correctly
- follow-up actions get lost

## 3.4 Telesales Disconnect
If red visits are not passed into a structured telesales workflow:
- customer opportunity is lost
- no one knows what was followed up
- there is no auditable operational trail

## 3.5 Lack of Unified Monitoring
Without one operational system:
- managers do not have real-time visibility
- supervisors rely on partial reports
- role-specific workflows become unclear

BexLogix addresses all of these by combining planning, execution, follow-up, and monitoring in one application.

---

# 4. Product Scope

## 4.1 What the MVP Is
The MVP is a **role-based web application** that supports:

- data import from Excel
- store scheduling
- daily assignment generation
- route ordering
- visit result submission
- telesales follow-up
- role-based visibility
- route and summary exports
- basic route visualization on a map

## 4.2 What the MVP Is Not
The MVP is intentionally **not**:
- a full ERP
- a complete CRM
- a final enterprise field-force platform
- a public consumer-facing app
- an OSM road-optimized routing system from day one
- a production API-first service layer with external integrations
- a mobile-native field application
- a workflow engine with advanced approvals and distributed background jobs

The MVP is supposed to be **operational, understandable, and demonstrable**.

---

# 5. Target Users and Roles

The product is designed around four explicit roles.

## 5.1 Manager
The manager is the operational controller of the day.

The manager should be able to:
- import setup and daily files
- generate draft assignments
- generate route order
- publish routes
- finalize unsubmitted assignments if needed
- monitor KPIs and workflow status
- export reports and route sheets

The manager is the only role that can perform core route and planning actions.

---

## 5.2 Supervisor
The supervisor is a monitoring-only role.

The supervisor should be able to:
- view assignments
- view visit outcomes
- view telesales queue
- view KPIs
- monitor the health of the day

The supervisor should **not**:
- import data
- generate assignments
- publish routes
- submit visit outcomes
- submit telesales outcomes

---

## 5.3 Visitor
The visitor is the field operator.

The visitor should be able to:
- log in
- see only their own assignments
- see route order
- see route map
- open a specific store
- submit one visit result
- add a note

The visitor should not see:
- other visitors’ assignments
- manager controls
- telesales functions
- global workflow controls

---

## 5.4 Telesales
The telesales user handles follow-up after red visits.

The telesales user should be able to:
- see pending telesales queue
- open follow-up items
- submit contact status
- submit outcome
- add notes

The telesales user should not:
- generate routes
- edit visitor assignments
- act as visitor
- mutate manager-only workflow

---

# 6. Core Business Logic

## 6.1 Visit Unit of Work
The fundamental operational unit is the **store visit**.

The visit is **basket-based**. This means that the company does not treat each product family as a separate independent visit. Instead, when a visitor reaches a store, the store is handled as one operational visit unit.

This is a very important design decision because it simplifies scheduling, route generation, and execution.

---

## 6.2 Store Grade
Each store has a Store Grade representing service priority:

- VIP
- A+
- A
- B
- C

In the MVP, Store Grade is used directly by scheduling logic to determine how often the store should be revisited.

---

## 6.3 Product Categories
The basket may include one or more of these categories:

- confectionery
- oil
- pasta

Each store may contain one or more of these categories.

---

## 6.4 Visit Frequency Matrix

### Confectionery and Oil
- VIP = every 6 days
- A+ = every 6 days
- A = every 9 days
- B = every 12 days
- C = every 20 days

### Pasta
- VIP = every 6 days
- A+ = every 6 days
- A = every 10 days
- B = every 8 days
- C = every 8 days

### Multi-category Rule
If a store includes multiple categories, the system should use the **shortest interval** to protect the sales opportunity.

This means scheduling logic does not average or merge intervals. It always chooses the most aggressive required cadence.

---

## 6.5 Visit Outcomes

### Green
A successful visit outcome:
- sale or relevant operational success completed
- store returns to normal scheduling cycle
- next visit date is calculated from base interval

### Yellow
A partial-but-not-failed visit:
- the store currently does not need product
- the store has enough stock for now
- next visit date becomes `visit_date + 3 days`

### Red
An operationally failed visit:
- store owner unavailable
- visitor did not reach the store
- visit failed or could not be completed

Red does not simply become “try again later” in the field workflow.  
Instead, red creates an internal handoff into the telesales workflow.

---

## 6.6 Telesales Outcomes
Telesales follow-up can produce one of several business outcomes:

- `sale_done`
- `no_need`
- `postpone`
- `invalid`

These outcomes affect the store’s scheduling state.

Typical MVP behavior:
- `sale_done` -> queue cleared, normal cycle resumes
- `no_need` -> queue cleared, next visit delayed by heuristic
- `postpone` -> queue continues, another follow-up is required
- `invalid` -> queue cleared or de-prioritized depending on defined policy

---

## 6.7 Daily Capacity
Every visitor has a default daily capacity, initially set to **30**.

For the MVP scenario:
- stores = 300
- visitors = 10

This gives the product enough scale to be meaningful for demonstration and operational simulation.

---

# 7. Intended Daily Workflow

## 7.1 Pre-Day or Start-of-Day Preparation
The manager prepares the operational day by ensuring:
- users exist
- visitors exist
- stores exist
- daily visitor status is imported or confirmed
- due stores can be calculated

---

## 7.2 Draft Assignment Generation
The system identifies due stores and distributes them among active visitors.

Assignments are initially created as **draft**.

This allows:
- route planning
- managerial preview
- potential last-minute correction before publish

---

## 7.3 Route Generation
After draft assignments exist, the route ordering layer computes:
- stop order
- route distance estimates

This route order is stored on daily assignments.

---

## 7.4 Publish
The manager publishes the assignments.

At this point:
- visitor-facing work becomes live
- assignment status changes from draft to published
- visitor panels can consume the work

---

## 7.5 Visit Submission
Visitors log in and see their own route.

For each store, the visitor can submit:
- green
- yellow
- red
- optional note

The submission updates:
- Visit table
- StoreScheduleState
- possibly TelesalesFollowup

---

## 7.6 Telesales Follow-Up
If a red visit exists:
- telesales sees a queue
- telesales submits follow-up result
- store scheduling state is updated

---

## 7.7 Monitoring and Reporting
Manager and supervisor can observe:
- due stores
- assignments
- visit outcomes
- telesales queue
- exports
- KPIs

---

# 8. Technical Architecture

The intended architecture for the MVP is:

**Streamlit UI -> Service Layer -> SQLAlchemy ORM -> SQLite**

This is a deliberate MVP decision.

---

## 8.1 Presentation Layer
The presentation layer is implemented using Streamlit.

Responsibilities:
- file upload
- date filters
- action buttons
- route tables
- KPI cards
- map rendering
- forms for visits and follow-ups
- role-based page access

The UI should not own the business logic.

---

## 8.2 Service Layer
The service layer owns the actual product behavior.

Responsibilities include:
- import logic
- scheduling logic
- assignment logic
- routing logic
- visit submission logic
- telesales follow-up logic
- reporting/export logic
- integrity checks
- reconciliation/repair helpers

This layer should remain UI-independent.

---

## 8.3 Persistence Layer
Persistence is handled by:
- SQLAlchemy models
- SQLite for the MVP
- DB session management

This layer stores:
- reference/master data
- daily operational data
- event records
- derived schedule state

---

# 9. Technical Stack

## 9.1 Python
Python is used for:
- backend logic
- UI layer (via Streamlit)
- import/export processing
- tests and utility scripts

## 9.2 SQLite
SQLite is used because:
- setup is simple
- local/internal execution is easy
- it is sufficient for the MVP scale

## 9.3 SQLAlchemy
SQLAlchemy is used because:
- it formalizes data models
- it keeps DB interaction structured
- it supports future migration to PostgreSQL

## 9.4 Streamlit
Streamlit is used because:
- it enables rapid internal app development
- it is enough for dashboard + workflow MVPs
- it keeps the stack Python-only for the first version

## 9.5 pandas and openpyxl
Used for:
- Excel reading
- Excel writing
- import cleaning
- data transformation

## 9.6 passlib + bcrypt
Used for:
- password hashing
- credential verification

---

# 10. Folder and Module Structure

A representative project structure:

```text
client/
  streamlit_app.py
  auth_state.py
  components/
    __init__.py
    route_map.py
  pages/
    __init__.py
    login.py
    manager_dashboard.py
    supervisor_dashboard.py
    visitor_panel.py
    telesales_panel.py

server/
  app/
    auth/
      password.py
      session.py
    enums/
      roles.py
      store_grade.py
      visit_result.py
      telesales_outcome.py
      assignment_status.py
    models/
      model_registry.py
      user.py
      store.py
      visitor_profile.py
      daily_visitor_status.py
      daily_assignment.py
      visit.py
      telesales_followup.py
      store_schedule_state.py
    services/
      constants.py
      import_service.py
      import_users_service.py
      import_visitors_service.py
      import_daily_visitor_status_service.py
      scheduling_service.py
      assignment_service.py
      routing_service.py
      visit_service.py
      telesales_service.py
      reporting_export_service.py
      integrity_service.py
      reconciliation_service.py
  db/
    base.py
    database.py
    create_tables.py
  tests/
    ...

data/
  users_seed_sample.xlsx
  visitors_sample.xlsx
  stores_sample.xlsx
  daily_visitor_status_sample.xlsx
```

---

# 11. Database Model Specification

## 11.1 User
Purpose:
- application authentication
- role separation
- account status

Typical fields:
- `id`
- `username`
- `password_hash`
- `role`
- `is_active`
- `created_at`
- `updated_at`

---

## 11.2 VisitorProfile
Purpose:
- operational profile for field visitor

Typical fields:
- `id`
- `user_id`
- `visitor_code`
- `full_name`
- `default_start_lat`
- `default_start_lon`
- `default_capacity`
- `is_active`
- `created_at`
- `updated_at`

This is one-to-one or effectively one-to-one with a visitor-type user.

---

## 11.3 Store
Purpose:
- reference/master store entity

Typical fields:
- `id`
- `store_code`
- `store_name`
- `region`
- `address`
- `lat`
- `lon`
- `grade`
- `has_confectionery`
- `has_oil`
- `has_pasta`
- `is_active`
- `notes`
- `created_at`
- `updated_at`

---

## 11.4 DailyVisitorStatus
Purpose:
- date-specific visitor operational status

Typical fields:
- `id`
- `visitor_id`
- `work_date`
- `start_lat`
- `start_lon`
- `capacity`
- `is_active_today`
- `created_at`

Important uniqueness intent:
- one row per `(visitor_id, work_date)`

---

## 11.5 DailyAssignment
Purpose:
- assignment of a store to a visitor on a given date

Typical fields:
- `id`
- `work_date`
- `visitor_id`
- `store_id`
- `route_order`
- `route_distance_km`
- `assignment_status`
- `generated_by`
- `published_at`
- `created_at`
- `updated_at`

Important conceptual uniqueness intent:
- one logical assignment per `(work_date, store_id)`

---

## 11.6 Visit
Purpose:
- actual result of execution

Typical fields:
- `id`
- `assignment_id`
- `store_id`
- `visitor_id`
- `visit_date`
- `result`
- `note`
- `created_at`
- `updated_at`

Important conceptual uniqueness intent:
- one visit per assignment

---

## 11.7 TelesalesFollowup
Purpose:
- post-red follow-up record

Typical fields:
- `id`
- `store_id`
- `visit_id`
- `followup_date`
- `contact_status`
- `result`
- `note`
- `created_by`
- `created_at`
- `updated_at`

Important conceptual rule:
- one open follow-up at a time per visit in the MVP

---

## 11.8 StoreScheduleState
Purpose:
- fast, derived, current schedule state of each store

Typical fields:
- `id`
- `store_id`
- `last_visit_date`
- `last_visit_result`
- `next_visit_date`
- `overdue_days`
- `in_telesales_queue`
- `update_at` / `updated_at`

This table allows scheduling logic to avoid recomputing everything from raw history every time.

---

# 12. Import Strategy and Data Flow

## 12.1 Database as Source of Truth
A key architectural rule:

**The database is the source of truth.**

Excel files are:
- setup inputs
- operational bulk inputs
- export targets

They are not the final workflow truth.

---

## 12.2 Import Service Pattern
Each importer should follow:

1. Read
2. Normalize
3. Validate
4. Transform
5. Upsert

This pattern improves:
- maintainability
- debuggability
- consistency
- idempotency

---

## 12.3 Stores Import
Stores import should populate:
- master store records
- category flags
- grade
- coordinates
- active status

The stores file should not contain workflow-level data such as visits or telesales outcomes.

---

## 12.4 Users Import
Users import should handle:
- username
- password
- role
- active state

Passwords must be hashed before storage.

---

## 12.5 Visitors Import
Visitors import should handle:
- username linkage
- visitor_code
- full_name
- default start location
- default capacity
- active state

---

## 12.6 Daily Visitor Status Import
This is a daily operational import.

It should handle:
- work_date
- visitor_code
- start_lat
- start_lon
- capacity
- is_active_today

This file is the daily declaration of visitor availability and operational start conditions.

---

## 12.7 What Should Not Be Imported as Daily Operational Truth
These should remain app-native:
- DailyAssignment
- Visit
- StoreScheduleState

TelesalesFollowup may support migration/backfill mode, but should not be the normal operating import source.

---

# 13. Scheduling Logic Specification

Scheduling determines:
- when a store is due
- how overdue it is
- what the next visit date should be
- whether it belongs in telesales queue

The service should:
- calculate interval from product basket + grade
- calculate due stores for a target date
- refresh overdue values
- apply visit results to schedule state
- apply telesales outcomes to schedule state

---

## 13.1 Green Rule
Green means:
- normal cycle resumes
- next visit date = visit date + interval
- in_telesales_queue = False

---

## 13.2 Yellow Rule
Yellow means:
- temporary retry
- next visit date = visit date + 3 days
- in_telesales_queue = False

---

## 13.3 Red Rule
Red means:
- immediate handoff to telesales
- next visit date = None or no direct field revisit date
- in_telesales_queue = True

---

## 13.4 Telesales Outcome Rules
Typical MVP rule examples:
- `sale_done` -> normal cycle resumes
- `no_need` -> delayed revisit by constant
- `postpone` -> follow-up remains active
- `invalid` -> queue resolved with fallback policy

These constants should remain centralized.

---

# 14. Assignment Logic Specification

Assignment logic is responsible for:
- selecting active visitors for a day
- selecting due stores
- sorting stores by priority
- distributing according to capacity
- creating draft assignments
- publishing assignments

---

## 14.1 Visitor Eligibility
A visitor is eligible if:
- linked user is active
- visitor profile is active
- daily visitor status exists for the date
- `is_active_today = True`
- capacity > 0

---

## 14.2 Draft vs Published
Assignments should support at least:
- `draft`
- `published`
- `completed`
- `skipped`

The intended workflow:
- draft is generated
- route ordering is applied
- manager publishes
- visitor executes
- completion/skipping happens later

---

## 14.3 Priority Ordering
A useful MVP priority order is:
- overdue days descending
- tighter interval first
- older next visit date first
- stable code ordering

This gives predictability and fairness while remaining easy to understand.

---

## 14.4 Overflow
If due stores exceed available capacity:
- assign up to total capacity
- leave the remaining stores due
- do not silently discard them

---

# 15. Routing Logic Specification

Routing should be separated from assignment.

## 15.1 Routing Input
The routing layer should receive:
- start point
- assigned store coordinates
- visitor identifier
- work date

## 15.2 Routing Output
The routing layer should update:
- `route_order`
- `route_distance_km`

## 15.3 MVP Routing
The MVP routing method may be:
- nearest-neighbor
- haversine-based

This is acceptable as long as:
- it is deterministic
- it produces visible route order
- it does not block the rest of the product

## 15.4 Future Routing
Later, the routing layer can be replaced with:
- OSM / OSRM / other route engine

This should not require redesigning assignment logic if the planner abstraction is clean.

---

# 16. Visit Service Specification

The visit service should:
- accept assignment-based result submission
- enforce ownership
- enforce published-only behavior
- prevent duplicate visit submission
- update store state
- create telesales follow-up when result is red

---

## 16.1 Visitor Ownership Rule
A visitor should only be able to submit for:
- their own assignments
- valid published assignments

---

## 16.2 Duplicate Rule
A given assignment should only generate one visit in the MVP.

If another submission is attempted:
- reject it at service level
- show a clear UI message

---

## 16.3 Notes
A note should be optional and stored as part of the visit event.

---

# 17. Telesales Service Specification

The telesales service should:
- create a follow-up when a red visit appears
- expose pending follow-ups
- accept telesales submission
- update schedule state accordingly

---

## 17.1 Open Follow-Up Rule
In the MVP, one follow-up should be considered open when:
- result is not final
- or a row exists with result unset, depending on chosen representation

This rule must remain consistent in integrity checks and reconciliation logic.

---

## 17.2 Postpone Chain
If a telesales result is `postpone`, the system should ensure there is a valid later follow-up.

This was identified as an important data-consistency area during hardening.

---

# 18. Authentication and Session Design

## 18.1 Password Security
Passwords must not be stored as plain text in the DB.

The flow should be:
- plain text import or input
- hash before save
- verify against hash at login

---

## 18.2 Session State
The Streamlit UI should keep only minimal authenticated state in session.

Everything else should be fetched from the DB or services as needed.

---

## 18.3 Role-Based Routing
A central app router should determine which page to render based on:
- authentication state
- role
- session validity

This is preferable to letting random pages expose themselves in an uncontrolled way.

---

# 19. Streamlit Application Design

The Streamlit app is intended to be the operational face of the MVP.

---

## 19.1 Login Page
Responsibilities:
- username/password input
- login action
- invalid credential feedback
- redirect into role-specific route

---

## 19.2 Manager Dashboard
Responsibilities:
- import files
- generate draft assignments
- generate route order
- publish routes
- finalize unsubmitted work if needed
- monitor KPI cards
- monitor assignments table
- monitor visit outcomes
- monitor telesales queue
- export route sheets and summaries
- view route maps

This dashboard is the operational command center.

---

## 19.3 Supervisor Dashboard
Responsibilities:
- view-only monitoring
- KPI visibility
- assignments visibility
- visits visibility
- telesales visibility

No mutation actions should be available.

---

## 19.4 Visitor Panel
Responsibilities:
- view own assignments
- view route map
- submit one result
- submit note
- see execution state

This panel should feel lightweight and practical.

---

## 19.5 Telesales Panel
Responsibilities:
- view pending queue
- open follow-up record
- submit contact status, result, note
- resolve queue items

---

# 20. Map Requirements

A route table alone is not enough.  
The MVP should include at least a visual route.

The route map should show:
- visitor start point
- assigned stores
- route order
- simple route path

The map does not need to be road-accurate in the MVP.

The map should fail gracefully when coordinates are incomplete.

---

# 21. White Neumorphism Visual Identity

The intended visual identity is **White Neumorphism**.

This means the app should not look like a default Streamlit prototype.  
It should feel like a calm, modern, soft internal product.

---

## 21.1 Visual Goals
The UI should feel:
- clean
- bright
- low-noise
- tactile
- calm
- premium but understated

---

## 21.2 Base Palette
Suggested background tones:
- `#F5F6F8`
- `#F2F4F7`
- `#EEF1F5`

These create a soft neutral surface.

---

## 21.3 Surface Styling
Use:
- soft rounded rectangles
- subtle outer shadows for raised blocks
- subtle inset shadows for inputs
- low-contrast, high-legibility composition

Cards should appear gently elevated from the background.

---

## 21.4 Cards
Cards should be used for:
- KPI tiles
- import sections
- route generation sections
- summary panels
- visitor action blocks
- telesales queue items
- map containers

---

## 21.5 Buttons
Buttons should have:
- rounded shape
- soft neumorphic depth
- subtle press state
- clear active/disabled state
- restrained accent color usage

---

## 21.6 Inputs
Inputs should look inset, soft, and minimal:
- rounded edges
- low border contrast
- soft internal shadow
- enough contrast for accessibility

---

## 21.7 Typography
Use:
- clean sans-serif font stack
- clear hierarchy
- bold headlines
- calm secondary text
- restrained color usage

---

## 21.8 Accent Use
Accent colors should be used for:
- action emphasis
- success/warning/error status
- route highlights
- selected state

Not for full-surface coloring.

---

## 21.9 Streamlit Implementation Strategy
White neumorphism in Streamlit typically requires:
- injected CSS
- custom section/card wrappers
- styled metric cards
- styled sidebar
- consistent spacing system
- component-level visual conventions

This should be implemented deliberately rather than scattered inline.

---

# 22. Reporting and Export Design

The reporting system should produce:
- daily KPI summaries
- route export files
- manager summary exports

---

## 22.1 KPIs
Expected KPIs include:
- due stores
- assigned stores
- completed visits
- green count
- yellow count
- red count
- telesales queue size

---

## 22.2 Export Targets
Examples:
- `route_{work_date}_{visitor_code}.xlsx`
- `summary_{work_date}.xlsx`

---

## 22.3 Export Data Sources
Reports should combine:
- DailyAssignment
- Visit
- TelesalesFollowup
- StoreScheduleState
- Store / VisitorProfile metadata

---

# 23. Test Strategy

The project needs both:
- developer-facing scripts
- user-facing operational validation

---

## 23.1 Developer-Facing Tests
Examples:
- import tests
- assignment smoke tests
- visit/telesales flow tests
- DB sanity tests
- integrity snapshot tests
- reconciliation tests

These should remain available during development.

---

## 23.2 User-Facing Validation
The real MVP should also be testable by:
- manager login and setup
- route generation in UI
- visitor execution in UI
- telesales completion in UI
- supervisor monitoring in UI

---

## 23.3 Important Distinction
A central technical lesson in this project is:

**CLI test scripts are development tools, not the intended user workflow.**

This distinction matters because the system can drift into being too backend-centric if not corrected.

---

# 24. Known Technical Risks and Constraints

## 24.1 Schema Migration
`create_all()` does not migrate existing schema.  
Therefore:
- model changes may require DB reset in the MVP
- later, migrations should be introduced properly

## 24.2 Some Constraints Are Service-Enforced
Examples may include:
- one visit per assignment
- no duplicate assignment per work_date/store
- one open telesales follow-up per visit

These may not yet be DB-enforced in the MVP.

## 24.3 Naming Consistency Risk
This project has a high risk of drift if naming differs across:
- Excel files
- pandas DataFrame columns
- SQLAlchemy fields
- service arguments
- UI field names

Strict consistency is required.

## 24.4 Streamlit Routing Risk
If router-based rendering and Streamlit auto-pages are mixed carelessly, empty or duplicate pages may appear.

---

# 25. Future Evolution

The MVP may later evolve into:
- PostgreSQL-backed persistence
- Alembic migrations
- stronger DB-level constraints
- cleaner config layering
- API support
- OSM route engine integration
- a possible Django or FastAPI layer if required

These are future concerns and should not dominate the MVP.

---

# 26. Final Technical Interpretation

Technically, BexLogix is intended to be a Python-based internal operations platform with:

- Streamlit as the presentation layer
- a business-logic-focused service layer
- SQLAlchemy ORM models
- SQLite as the MVP persistence layer
- Excel import/export support
- role-based operational UI
- route generation and route visualization
- visitor execution workflow
- telesales follow-up workflow
- manager/supervisor monitoring
- White Neumorphism as the visual identity

The final system should feel less like a collection of scripts and more like a coherent operational product.

The most important technical intention is this:

**The MVP must be UI-driven for real usage, service-driven for business logic, and database-centered for truth and consistency.**
