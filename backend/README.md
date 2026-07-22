# FE-RealEstate-Tracker — Backend

A Django REST Framework API scaffolded field-for-field from the
`FE-RealEstate-Tracker` React + Vite + TypeScript frontend. It reproduces
every entity in `src/data/demo-data.ts` plus the extra local-storage-only
data used on the Compliance, Handover, Society and Admin pages — so the
seeded database looks exactly like the app does today with its hardcoded
demo data.

**No frontend code or UI logic was touched.** This is backend-only, designed
to be a drop-in data source once you swap the frontend's local arrays /
`localStorage` calls for `fetch`/`axios` calls to these endpoints.

## Why the JSON looks the way it does

Every response uses **camelCase** keys (`startDate`, `assignedHod`,
`criticalPath`, ...) instead of Django's usual `snake_case`, via
`djangorestframework-camel-case`. That means the JSON shape matches the
TypeScript interfaces in `src/data/demo-data.ts` almost exactly — minimal
adapter code needed on the frontend. (Note: `assignedHod`, not
`assignedHOD` — the mechanical camelCase conversion of `assigned_hod`
doesn't preserve the all-caps acronym, and every serializer field is
deliberately named in plain snake_case so djangorestframework-camel-case's
parser can match it back up correctly on writes — see the docstring at the
top of `tasks/serializers.py` for why that matters.)

## Quick start

Uses PostgreSQL. Get a server running first — Docker is usually fastest:
```bash
docker run --name vibe-pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres
```
(or a native install, or a hosted free tier like Neon/Supabase/Railway — any
of those work, just point `.env` at it.)

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # edit DB_* vars if your Postgres isn't the default

createdb vibe_tracker            # or: psql -U postgres -c "CREATE DATABASE vibe_tracker;"
python manage.py migrate
python manage.py seed_demo_data # loads the full demo dataset
python manage.py createsuperuser  # optional, for /admin/

python manage.py runserver      # http://localhost:8000
```

Migrating existing data from an older SQLite setup? See
`POSTGRES_MIGRATION.md`.

The frontend's Vite dev server runs on port 8080 (see `vite.config.ts`) /
5173 by default — both are pre-allowed in `CORS_ALLOWED_ORIGINS`.

### Demo login

`seed_demo_data` recreates all 12 users from `demo-data.ts`. Every seeded
user shares the password **`demo1234`**; the username is the part of their
email before the `@` (e.g. `rajesh@vibe.com` → username `rajesh`).

| Username  | Name          | Role              | Department  |
|-----------|---------------|-------------------|-------------|
| rajesh    | Rajesh Sharma | CEO               | Admin       |
| priya     | Priya Mehta   | Project Director  | Admin       |
| amit      | Amit Patel    | HOD               | Civil       |
| deepak    | Deepak Kumar  | Site Engineer     | Civil       |
| ...       | ...           | ...               | (12 total, see `core/management/commands/seed_demo_data.py`) |

`POST /api/auth/login/` with `{"username": "rajesh", "password": "demo1234"}`
returns `{access, refresh, user}` — this replaces the hardcoded check
currently in `src/contexts/AuthContext.tsx`.

## Project layout

Each Django app mirrors one slice of the frontend. See the top-of-file
docstring/comments in each `models.py` and `views.py` for the exact
frontend file it backs.

```
backend/
├── manage.py
├── requirements.txt
├── .env.example
├── config/                  # settings, root urls
│   ├── settings.py
│   └── urls.py
├── accounts/                 # custom User model + JWT auth
│   ├── models.py             #   User (role, department, name)
│   └── views.py               #   /api/auth/login|logout|refresh|me, /api/users/
├── projects/                  # Project → Tower → Floor → Unit
├── tasks/                     # Task, checklist items, comments, dependencies
├── hurdles/                   # Hurdle
├── resources/                 # Resource, machines, materials (per task)
├── checklists/                # ChecklistTemplate (+ items)
├── compliance/                # ComplianceItem
├── handover/                  # HandoverUnit
├── society/                   # Society, SocietyStep
├── documents/                 # Document (real file uploads)
├── adminpanel/                # EscalationRule
├── analytics/                 # computed endpoints, no models:
│   └── services.py            #   department stats, delay prediction,
│                               #   AI assistant — ported from the frontend's
│                               #   client-side logic in DelayPrediction.tsx
│                               #   / AIAssistant.tsx
└── core/
    └── management/commands/seed_demo_data.py   # loads demo-data.ts equivalent
```

## Endpoints ↔ frontend pages

| Frontend page | Endpoint(s) |
|---|---|
| `LoginPage.tsx` / `AuthContext.tsx` | `POST /api/auth/login/`, `POST /api/auth/refresh/`, `GET /api/auth/me/`, `POST /api/auth/logout/` |
| `Projects.tsx` | `/api/projects/`, `/api/towers/`, `/api/floors/`, `/api/units/` |
| `Tasks.tsx` | `/api/tasks/`, `POST /api/tasks/{id}/comments/`, `POST /api/tasks/{id}/checklist/`, `POST /api/tasks/{id}/checklist/{item_id}/toggle/` |
| `Timeline.tsx`, `DigitalTwin.tsx` | `/api/tasks/` (filter by `project`, `tower`, `floor`) |
| `HurdleTracker.tsx` + `ReportHurdleDialog.tsx` | `/api/hurdles/` |
| `Resources.tsx` | `/api/resources/` |
| `Checklists.tsx` | `/api/checklist-templates/` |
| `Compliance.tsx` | `/api/compliance-items/` |
| `Handover.tsx` | `/api/handover-units/` |
| `Society.tsx` | `/api/societies/`, `POST /api/societies/{id}/steps/{step_id}/toggle/` |
| `Documents.tsx` | `/api/documents/` (multipart upload via `file` field) |
| `Admin.tsx` (Users tab) | `/api/users/` |
| `Admin.tsx` (Escalation Matrix tab) | `/api/escalation-rules/` |
| `Reports.tsx`, `Dashboard.tsx` charts | `GET /api/analytics/department-stats/`, `GET /api/analytics/dashboard-summary/` |
| `DelayPrediction.tsx` | `GET /api/analytics/delay-predictions/` |
| `AIAssistant.tsx` | `POST /api/analytics/ai-assistant/ {message}` |

All list endpoints support:
- **Filtering** — e.g. `/api/tasks/?status=delayed&department=Civil&project=1`
- **Search** — e.g. `/api/tasks/?search=slab`
- **Pagination** — responses are `{count, next, previous, results}` (50/page)

## Auth model

JWT via `djangorestframework-simplejwt`. Send `Authorization: Bearer <access>`
on every request. Access tokens last 8 hours, refresh tokens 7 days (see
`SIMPLE_JWT` in `config/settings.py`) — tune these to match how long you want
the frontend's session to last.

## Permissions — adjust to your needs

Right now:
- Any authenticated user can **read** everything.
- **Write** access to Projects/Towers/Floors/Units and Users/Escalation Rules
  is restricted to `Admin` / `CEO` / `Project Director` roles
  (`accounts/permissions.py: IsAdminOrCEO`).
- Tasks/Hurdles/Resources/Checklists/Compliance/Handover/Society/Documents
  are read+write for any authenticated user (matches today's frontend, where
  any logged-in user can edit anything).

If you want e.g. only a task's assigned HOD to edit it, or Site Engineers to
be read-only, extend `accounts/permissions.py` and swap the `permission_classes`
on the relevant viewset.

## Wiring the frontend

The frontend currently reads from `src/data/demo-data.ts` (a static array)
and various `useLocalStorageState` hooks — no UI logic needs to change, just
the data source. The general pattern per page is:

```ts
// before
import { tasks } from "@/data/demo-data";

// after
const { data: tasks } = useQuery({
  queryKey: ["tasks"],
  queryFn: () => api.get("/tasks/").then(r => r.data.results),
});
```

Because the JSON is already camelCase and matches the existing `Task`,
`Project`, `Hurdle`, etc. interfaces, most components that consume this data
shouldn't need changes beyond the fetch itself. A couple of exceptions to
budget time for:
- IDs are now integers, not strings like `'task1'`.
- `Compliance`/`Handover`/`Society` now reference `project` as an ID
  (`GET /api/compliance-items/` includes both `project` and a convenience
  `projectName` string) instead of a raw project-name string.

## Production notes

This is configured for PostgreSQL with `DEBUG=True` for local development.
Before deploying:
- Set a real `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, proper `DJANGO_ALLOWED_HOSTS`.
- Use a managed Postgres instance (RDS, Cloud SQL, Neon, Supabase, etc.) rather than a local container, and put its credentials in `DB_*` env vars.
- Serve `MEDIA_ROOT` (document uploads) from S3/GCS or similar rather than local disk.
- Run `python manage.py check --deploy` and address the warnings it raises.
