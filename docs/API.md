# ClientFlow CRM - API reference

Interactive documentation is generated from the code: **`/api/docs/`** (Swagger UI), `/api/redoc/`, schema at `/api/schema/` (OpenAPI 3).
This page is a quick orientation; the schema is the source of truth.

Base URL (local): `http://127.0.0.1:8000/api`

## Authentication

| Method & path | Purpose |
|---|---|
| `POST /auth/login/` | `{username, password}` → `{access, refresh, user}`. Rate limited (default 10/min → `429`). |
| `POST /auth/refresh/` | `{refresh}` → new `access` and a rotated `refresh` (old one is blacklisted). |
| `POST /auth/logout/` | `{refresh}` → `204`; blacklists the refresh token. Idempotent. |
| `GET /auth/me/` | Current user and role. |

Send `Authorization: Bearer <access>` on every other request. Access tokens last 30 minutes, refresh tokens 7 days (configurable).

## Resources

All list endpoints are paginated: `?page=2&page_size=15` (default 20, max 100) → `{count, next, previous, results}`.
Common query parameters: `search=`, `ordering=field` or `-field`.

| Resource | Endpoints | Filters (besides `search`/`ordering`) |
|---|---|---|
| Users | `GET/POST /users/`, `GET/PUT/PATCH /users/{id}/` | `role`, `is_active`. Everyone can list active users; only admins write. No DELETE: deactivate instead. |
| Tags | `/tags/` (CRUD, unpaginated) | |
| Companies | `/companies/` (CRUD) + `GET /companies/export/` | `industry`, `city`, `country`, `owner` |
| Contacts | `/contacts/` (CRUD) + `/contacts/export/` | `company`, `owner`, `tag` (tag id). Write tags with `tag_ids: [1,2]`. |
| Leads | `/leads/` (CRUD) + `/leads/export/` | `status`, `source`, `owner`, `overdue=true/false`, `follow_up_after`, `follow_up_before` |
| | `POST /leads/{id}/convert/` | body `{deal_title, amount, expected_close_date?}` → `201` deal |
| Deals | `/deals/` (CRUD) + `/deals/export/` | `stage`, `owner`, `company`, `contact`, `open=true/false`, `min_amount`, `max_amount`, `close_after`, `close_before` |
| | `POST /deals/{id}/change-stage/` | body `{stage, lost_reason?}` |
| | `GET /deals/{id}/history/` | stage history |
| | `GET /deals/pipeline/` | deals grouped by stage with counts/totals (accepts the deal filters) |
| Tasks | `/tasks/` (CRUD) + `/tasks/export/` | `status`, `priority`, `assignee`, `lead`, `deal`, `contact`, `overdue`, `due_after`, `due_before` |
| | `POST /tasks/{id}/complete/`, `POST /tasks/{id}/reopen/` | `status` is read-only on create/update |
| Interactions | `/interactions/` (CRUD) | `type`, `contact`, `company`, `deal`, `lead`, `created_by`, `occurred_after`, `occurred_before` |
| Notifications | `GET /notifications/`, `POST /notifications/{id}/read/`, `POST /notifications/read-all/`, `GET /notifications/unread-count/` | `unread=true`, `kind` |
| Dashboard | `GET /dashboard/` | KPIs, pipeline by stage, leads by source, upcoming tasks, overdue leads, recent activity |
| Workflows | `POST /automation/run/` | Managers/admins: flag overdue leads now → `{flagged, cleared}` |
| Health | `GET /health/` | `{status, database}` (no auth) |

CSV exports accept the same filters/search/ordering as the list and respect the caller's permissions. Cells that could be read as spreadsheet formulas are prefixed with `'`.

## Deal stages

`stage` is **read-only** on `POST/PATCH /deals/`. Use `change-stage`:

| From | Allowed next stages |
|---|---|
| New | Qualified, Lost |
| Qualified | New, Proposal, Lost |
| Proposal | Qualified, Negotiation, Lost |
| Negotiation | Proposal, Won, Lost |
| Won | none (final) |
| Lost | New (reopen) |

Moving to `lost` requires a non-blank `lost_reason`. Invalid moves return `400` with a message, e.g.
`{"stage": ["Cannot move a deal from New to Won. Allowed: Qualified, Lost."]}`.

## Errors

Errors use standard HTTP status codes and DRF's shape:

```json
// 400 - field validation
{"email": ["Enter a valid email address."], "first_name": ["This field is required."]}
// 400 - non-field
{"non_field_errors": ["Link the interaction to a contact, company, lead or deal."]}
// 401 / 403 / 404 / 405 / 409 / 429
{"detail": "..."}
```

| Status | Meaning |
|---|---|
| `401` | Missing/expired token (or bad login) |
| `403` | Authenticated but not allowed (e.g. a rep deleting a company) |
| `404` | Not found **or not visible to you** (reps can't see others' leads/deals/tasks) |
| `409` | Conflict, e.g. deleting a company that still has deals |
| `429` | Login throttled |

## Example

```bash
# log in
curl -s -X POST localhost:8000/api/auth/login/ -H 'Content-Type: application/json' \
  -d '{"username":"rep","password":"ClientFlow-Demo-2026"}'

# create a lead: a follow-up task is created automatically
curl -s -X POST localhost:8000/api/leads/ -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"first_name":"Ada","last_name":"Byron","company_name":"Byron Bakery","source":"referral","follow_up_date":"2026-12-01"}'

# convert it into a deal
curl -s -X POST localhost:8000/api/leads/14/convert/ -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"deal_title":"Byron Bakery - website","amount":"4800.00"}'

# move the deal
curl -s -X POST localhost:8000/api/deals/17/change-stage/ -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"stage":"qualified"}'

# export overdue leads
curl -s "localhost:8000/api/leads/export/?overdue=true" -H "Authorization: Bearer $TOKEN" -o overdue-leads.csv
```
