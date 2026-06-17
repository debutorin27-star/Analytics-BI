# Power BI Table Requests

Base URL:

```text
http://127.0.0.1:8000
```

Authentication:

```http
Authorization: Bearer <POWERBI_BEARER_TOKEN>
```

Shell examples use `POWERBI_TOKEN`:

```bash
export POWERBI_TOKEN='<POWERBI_BEARER_TOKEN>'
```

## Full Tables

```bash
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" http://127.0.0.1:8000/api/v1/bi/tables/vacancies
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" http://127.0.0.1:8000/api/v1/bi/tables/workflow-stages
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" http://127.0.0.1:8000/api/v1/bi/tables/responses
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" http://127.0.0.1:8000/api/v1/bi/tables/source-breakdown
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" http://127.0.0.1:8000/api/v1/bi/tables/candidate-events
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" http://127.0.0.1:8000/api/v1/bi/tables/discard-reasons
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" http://127.0.0.1:8000/api/v1/bi/tables/persons
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" http://127.0.0.1:8000/api/v1/bi/tables/person-sources
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" http://127.0.0.1:8000/api/v1/bi/tables/managers
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" http://127.0.0.1:8000/api/v1/bi/tables/hiring-requests
```

## Tables From 2026-06-10

```bash
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" "http://127.0.0.1:8000/api/v1/bi/tables/vacancies?updated_from=2026-06-10"
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" "http://127.0.0.1:8000/api/v1/bi/tables/workflow-stages?updated_from=2026-06-10"
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" "http://127.0.0.1:8000/api/v1/bi/tables/responses?updated_from=2026-06-10"
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" "http://127.0.0.1:8000/api/v1/bi/tables/source-breakdown?updated_from=2026-06-10"
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" "http://127.0.0.1:8000/api/v1/bi/tables/candidate-events?updated_from=2026-06-10"
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" "http://127.0.0.1:8000/api/v1/bi/tables/discard-reasons?updated_from=2026-06-10"
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" "http://127.0.0.1:8000/api/v1/bi/tables/persons?updated_from=2026-06-10"
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" "http://127.0.0.1:8000/api/v1/bi/tables/person-sources?updated_from=2026-06-10"
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" "http://127.0.0.1:8000/api/v1/bi/tables/managers?updated_from=2026-06-10"
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" "http://127.0.0.1:8000/api/v1/bi/tables/hiring-requests?updated_from=2026-06-10"
```

## Dictionaries

```bash
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" http://127.0.0.1:8000/api/v1/bi/dictionaries/areas
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" http://127.0.0.1:8000/api/v1/bi/dictionaries/businessTripReadinesses
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" http://127.0.0.1:8000/api/v1/bi/dictionaries/educationLevels
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" http://127.0.0.1:8000/api/v1/bi/dictionaries/employments
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" http://127.0.0.1:8000/api/v1/bi/dictionaries/industries
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" http://127.0.0.1:8000/api/v1/bi/dictionaries/languageLevels
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" http://127.0.0.1:8000/api/v1/bi/dictionaries/languages
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" http://127.0.0.1:8000/api/v1/bi/dictionaries/relocationTypes
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" http://127.0.0.1:8000/api/v1/bi/dictionaries/schedules
curl -H "Authorization: Bearer ${POWERBI_TOKEN}" http://127.0.0.1:8000/api/v1/bi/dictionaries/travelTimes
```
