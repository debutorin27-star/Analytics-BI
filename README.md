# HR Link: Talantix -> Power BI

Python/FastAPI service that reads Talantix GraphQL API, stores a prepared BI JSON cache, and exposes REST/JSON endpoints for Power BI.

The service is read-only by default. It collects vacancies, workflow stages, responses, candidates, sources, managers, hiring requests, dictionaries, and candidate history events used for discard reason analytics. Power BI reads the already prepared cache, so regular dashboard refreshes do not wait for the full Talantix GraphQL export.

## What It Returns

- `vacancies`: vacancy metadata, department, status, dates, salary, cities, managers, external publications.
- `workflow_stages`: funnel stages per vacancy with current candidate counters and SLA.
- `responses`: candidate-vacancy rows with current stage, candidate source, city, cover letter, rating, unread flag, update date, and URL.
- `bi/export`: one-call cached BI payload with vacancies, stages, responses, candidates, sources, managers, hiring requests, dictionaries, events and discard reasons.
- `funnel`: smaller combined payload with vacancies, stages, responses, source breakdown, candidate events, discard reasons.
- `persons`: lightweight candidate base with optional history. Mass export keeps fields that fit Talantix GraphQL complexity limits: ID, name, age/birthday, gender, city, source, updated date. Heavy nested fields such as contacts/files/photos/resumes should be fetched separately for a specific candidate if needed.
- `hiring-requests`: hiring requests with status, dates, regions, salary, managers, linked vacancy.
- `person-sources`, `managers`, `dictionaries`: reference data for BI dimensions.

Talantix returns timestamps as Unix milliseconds. This service keeps the original value and adds `*_iso` fields where useful.

Vacancy description text is intentionally excluded from BI export to keep cache and Power BI refresh payloads smaller.

## Setup

Talantix API requires a bearer access token. A Talantix administrator generates the token JSON in the Talantix account.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill `.env`:

```bash
TALANTIX_ACCESS_TOKEN=...
TALANTIX_REFRESH_TOKEN=...
TALANTIX_TOKEN_FILE=.talantix_tokens.json
TALANTIX_USER_AGENT='Your Company (it@example.com)'
SERVICE_API_KEY='long-random-key-for-power-bi'
POWERBI_BEARER_TOKEN='future-jwt-or-static-bearer-token'
SYNC_ENABLED=true
SYNC_ON_STARTUP=true
SYNC_INTERVAL_SECONDS=3600
BI_CACHE_FILE=data/talantix_bi_export.json
BI_SYNC_PERSON_PAGE_SIZE=5
TALANTIX_MAX_PAGES=
```

Run locally:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open:

```text
http://localhost:8000/docs
```

## Token Refresh

If `TALANTIX_REFRESH_TOKEN` is set, the service refreshes `access_token` after HTTP 401 or near expiry.

If `TALANTIX_TOKEN_FILE` is set, the refreshed pair is saved there. This is important because Talantix refresh tokens are one-time use.

## BI Cache Refresh

By default the service refreshes the BI cache every hour:

```text
SYNC_INTERVAL_SECONDS=3600
```

If `SYNC_ON_STARTUP=true`, the first sync starts when the service starts. Until the first successful sync is finished, `/api/v1/bi/export` returns HTTP 503 with the sync status.

Production sync is a full historical snapshot: do not pass `max_pages` or `max_stages`, and keep `TALANTIX_MAX_PAGES=` empty. With empty limits the service paginates until Talantix returns `hasNextPage=false`, including archived vacancies because no `vacancy_status` filter is applied.

Initial full sync:

```text
POST http://localhost:8000/api/v1/bi/sync?force=true
```

Limited smoke sync without changing `.env`:

```text
POST http://localhost:8000/api/v1/bi/sync?max_pages=1
```

Sync status:

```text
GET http://localhost:8000/api/v1/bi/sync/status
```

For initial testing, you can limit the background export:

```text
BI_SYNC_MAX_PAGES=2
BI_SYNC_MAX_STAGES=20
```

Leave those values empty in production to collect all available pages/stages. Keep `BI_SYNC_PERSON_PAGE_SIZE` lower than the main page size because Talantix counts `persons + history` as a heavier GraphQL query.

Talantix does not expose universal `updatedFrom` filters for all required entities. In particular, `VacancyFilterInput` and `ResponseFilterInput` have no date/update fields, so reliable hourly refresh is a full cache refresh. Power BI receives incremental data by filtering this prepared full cache with `updated_from`.

## Power BI Examples

The main endpoint for Power BI is:

```text
http://localhost:8000/api/v1/bi/export
```

It returns one JSON object with these top-level tables:

```text
vacancies
workflow_stages
responses
source_breakdown
candidate_events
discard_reasons
persons
person_sources
managers
hiring_requests
dictionaries
meta
```

For direct flat table reads, use one endpoint per BI table:

```text
GET /api/v1/bi/tables
GET /api/v1/bi/tables/vacancies
GET /api/v1/bi/tables/workflow-stages
GET /api/v1/bi/tables/responses
GET /api/v1/bi/tables/source-breakdown
GET /api/v1/bi/tables/candidate-events
GET /api/v1/bi/tables/discard-reasons
GET /api/v1/bi/tables/persons
GET /api/v1/bi/tables/person-sources
GET /api/v1/bi/tables/managers
GET /api/v1/bi/tables/hiring-requests
```

These endpoints return a JSON array by default, so Power BI can use `Table.FromRecords(Source)` directly. Add `envelope=true` if you need `{ items, count, meta }` instead of a raw array. Add `flat=false` only if you want nested JSON fields preserved.

Dictionaries are exposed separately:

```text
GET /api/v1/bi/dictionaries
GET /api/v1/bi/dictionaries/areas
GET /api/v1/bi/dictionaries/educationLevels
```

Authentication options:

```text
Authorization: Bearer <POWERBI_BEARER_TOKEN>
X-API-Key: <SERVICE_API_KEY>
?api_key=<SERVICE_API_KEY>
```

Power Query example:

```powerquery
let
    Source = Json.Document(
        Web.Contents(
            "http://localhost:8000/api/v1/bi/export",
            [
                Headers = [
                    Authorization = "Bearer future-jwt-or-static-bearer-token"
                ]
            ]
        )
    ),
    Stages = Source[workflow_stages],
    Table = Table.FromRecords(Stages)
in
    Table
```

Incremental read from the prepared cache:

```text
/api/v1/bi/export?updated_from=2026-06-10
/api/v1/bi/export?updated_from=2026-06-10T10:30:00Z
/api/v1/bi/tables/responses?updated_from=2026-06-10
/api/v1/bi/tables/vacancies?updated_from=2026-06-10
```

If `updated_from` is omitted, the endpoint returns the full cached dataset. The incremental filter is applied to tables that have update/event dates: vacancies, responses, candidate events, persons, and hiring requests.

For BI consistency, incremental export also includes related dimensions:

- if a response changed, the related vacancy, candidate, and vacancy stages are included;
- if a new/changed vacancy appears, its stages and responses are included;
- reference tables such as sources, managers, and dictionaries remain available in full.

For debugging or selective live pulls from Talantix, use the non-cached endpoints:

```text
/api/v1/bi/export/live?vacancy_id=123,456&include_history=true
/api/v1/bi/export/live?include_persons=true&lean_persons=true&page_size=20&person_page_size=5
/api/v1/funnel?vacancy_id=123,456&include_history=true
/api/v1/responses?vacancy_id=123&include_history=true
/api/v1/workflow-stages?vacancy_id=123
```

## Endpoints

```text
GET  /health
GET  /api/v1/auth/check
POST /api/v1/graphql
GET  /api/v1/vacancies
GET  /api/v1/workflow-stages
GET  /api/v1/responses
GET  /api/v1/funnel
GET  /api/v1/bi/export
GET  /api/v1/bi/export/live
GET  /api/v1/bi/tables
GET  /api/v1/bi/tables/{table_name}
GET  /api/v1/bi/dictionaries
GET  /api/v1/bi/dictionaries/{dictionary_name}
GET  /api/v1/bi/sync/status
POST /api/v1/bi/sync
GET  /api/v1/persons
GET  /api/v1/person-sources
GET  /api/v1/dictionaries
GET  /api/v1/managers
GET  /api/v1/hiring-requests
```

Common query parameters:

- cached export: `updated_from=2024-05-01`, `refresh=true`
- live endpoints: `vacancy_id=123,456`, `vacancy_status=ACTIVE`, `status=ACTIVE`, `department=Sales,HR`, `page_size=50`, `person_page_size=5`, `max_pages=10`, `include_history=true`, `lean_persons=true`, `max_stages=100`

`include_history=true` is required for `discard_reasons`, because rejection/refusal reasons are taken from candidate history events with `discardInfo`.

## Docker

```bash
docker build -t hr-link .
docker run --env-file .env -p 8000:8000 hr-link
```

Recommended compose run:

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f hr-link
docker compose down
```

The compose setup mounts `./data` into the container, so the prepared BI cache and refreshed Talantix token file survive container restarts.

## Talantix API Notes

The service uses the official Talantix GraphQL endpoint:

```text
POST https://api.talantix.ru/graphql
Authorization: Bearer <access token>
Content-Type: application/json
User-Agent: <company/contact>
```

Main GraphQL roots used here: `persons`, `vacancies`, `response`, `workflowStatus`, `hiringRequests`, `managers`, `personSources`, `dictionaries`.
