from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from app import graphql_queries as q
from app.config import Settings
from app.normalizers import (
    aggregate_discard_reasons,
    aggregate_source_breakdown,
    compact_dict,
    flatten_hiring_request,
    flatten_history_events,
    flatten_manager,
    flatten_person,
    flatten_response,
    flatten_vacancy,
    flatten_workflow_stage,
    parse_csv,
    parse_csv_int,
)
from app.talantix_client import TalantixClient, TalantixError


class TalantixBIService:
    def __init__(self, client: TalantixClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    async def list_vacancies(
        self,
        *,
        vacancy_ids: list[int] | None = None,
        status: str | None = None,
        departments: list[str] | None = None,
        area_ids: list[str] | None = None,
        vacancy_title: str | None = None,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> dict[str, Any]:
        raw = await self.fetch_vacancies(
            vacancy_ids=vacancy_ids,
            status=status,
            departments=departments,
            area_ids=area_ids,
            vacancy_title=vacancy_title,
                page_size=page_size,
                max_pages=max_pages,
        )
        return _envelope([flatten_vacancy(item) for item in raw["items"]], raw["meta"])

    async def list_workflow_stages(
        self,
        *,
        vacancy_ids: list[int] | None = None,
        status: str | None = None,
        departments: list[str] | None = None,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> dict[str, Any]:
        raw = await self.fetch_vacancies(
            vacancy_ids=vacancy_ids,
            status=status,
            departments=departments,
            page_size=page_size,
            max_pages=max_pages,
        )
        rows = [
            flatten_workflow_stage(vacancy, stage)
            for vacancy in raw["items"]
            for stage in _workflow_stages(vacancy)
        ]
        return _envelope(rows, raw["meta"])

    async def list_persons(
        self,
        *,
        search: str | None = None,
        source_ids: list[int] | None = None,
        vacancy_ids: list[int] | None = None,
        wf_status_names: list[str] | None = None,
        current_wf_status_names: list[str] | None = None,
        discard_reason_ids: list[int] | None = None,
        discard_type: str | None = None,
        include_history: bool = False,
        history_first: int = 20,
        lean: bool = True,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> dict[str, Any]:
        filter_value = compact_dict(
            {
                "search": search,
                "sourceIds": source_ids,
                "vacancyIds": vacancy_ids,
                "wfStatusNames": wf_status_names,
                "currentWfStatusNames": current_wf_status_names,
                "discardReasonIds": discard_reason_ids,
                "discardType": _enum(discard_type),
            }
        )
        variables: dict[str, Any] = {
            "filter": filter_value or None,
            "first": _page_size(page_size, self._settings.talantix_page_size, 50),
        }
        if include_history:
            variables["historyFirst"] = history_first

        items, meta = await self._paginate(
            query=q.persons_query(include_history, lean=lean),
            variables=variables,
            connection_path=("persons",),
            max_pages=max_pages,
        )
        rows = [flatten_person(item) for item in items]
        events = [event for item in items for event in flatten_history_events(item)]
        meta.update({"include_history": include_history, "lean": lean})
        result = _envelope(rows, meta)
        if include_history:
            result["candidate_events"] = events
            result["discard_reasons"] = aggregate_discard_reasons(events)
        return result

    async def list_person_sources(
        self,
        *,
        filter_by_name: str | None = None,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> dict[str, Any]:
        items, meta = await self._paginate(
            query=q.PERSON_SOURCES_QUERY,
            variables={
                "filterByName": filter_by_name,
                "first": _page_size(page_size, self._settings.talantix_page_size, 50),
            },
            connection_path=("personSources",),
            cursor_variable="afterCursor",
            max_pages=max_pages,
        )
        return _envelope(items, meta)

    async def dictionaries(self) -> dict[str, Any]:
        body = await self._client.execute(q.DICTIONARIES_QUERY)
        dictionaries = body.get("data", {}).get("dictionaries") or {}
        return {
            "data": dictionaries,
            "meta": _meta({"source": "talantix.dictionaries"}),
        }

    async def list_managers(
        self,
        *,
        search_by_name: str | None = None,
        search_by_email: str | None = None,
        roles: list[str] | None = None,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> dict[str, Any]:
        filter_value = compact_dict(
            {
                "searchByName": search_by_name,
                "searchByEmail": search_by_email,
                "roles": [_enum(role) for role in roles] if roles else None,
            }
        )
        items, meta = await self._paginate(
            query=q.MANAGERS_QUERY,
            variables={
                "filter": filter_value or None,
                "first": _page_size(page_size, self._settings.talantix_page_size, 50),
            },
            connection_path=("managers",),
            max_pages=max_pages,
            union_error_typenames={"ManagersError"},
        )
        return _envelope([flatten_manager(item) for item in items], meta)

    async def list_hiring_requests(
        self,
        *,
        statuses: list[str] | None = None,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> dict[str, Any]:
        filter_value = compact_dict({"byStatus": [_enum(status) for status in statuses] if statuses else None})
        items, meta = await self._paginate(
            query=q.HIRING_REQUESTS_QUERY,
            variables={
                "filter": filter_value or None,
                "first": _page_size(page_size, self._settings.talantix_page_size, 50),
            },
            connection_path=("hiringRequests",),
            max_pages=max_pages,
        )
        return _envelope([flatten_hiring_request(item) for item in items], meta)

    async def list_responses(
        self,
        *,
        workflow_status_id: int | None = None,
        vacancy_ids: list[int] | None = None,
        vacancy_status: str | None = None,
        departments: list[str] | None = None,
        response_filter: dict[str, Any] | None = None,
        include_history: bool = False,
        history_first: int = 20,
        page_size: int | None = None,
        max_pages: int | None = None,
        max_stages: int | None = None,
    ) -> dict[str, Any]:
        response_page_size = _page_size(page_size, self._settings.talantix_page_size, 50)
        if workflow_status_id:
            rows, events = await self._fetch_responses_for_stage(
                stage={"id": workflow_status_id},
                vacancy=None,
                response_filter=response_filter,
                include_history=include_history,
                history_first=history_first,
                page_size=response_page_size,
                max_pages=max_pages,
            )
            result = _envelope(rows, {"include_history": include_history, "workflow_status_id": workflow_status_id})
            if include_history:
                result["candidate_events"] = events
                result["discard_reasons"] = aggregate_discard_reasons(events)
            return result

        vacancies = await self.fetch_vacancies(
            vacancy_ids=vacancy_ids,
            status=vacancy_status,
            departments=departments,
            page_size=page_size,
            max_pages=max_pages,
        )
        stage_pairs = [(vacancy, stage) for vacancy in vacancies["items"] for stage in _workflow_stages(vacancy)]
        if max_stages and len(stage_pairs) > max_stages:
            raise TalantixError(
                f"Requested {len(stage_pairs)} workflow stages, max_stages is {max_stages}",
                status_code=400,
            )

        rows, events = await self._fetch_responses_for_stage_pairs(
            stage_pairs,
            response_filter=response_filter,
            include_history=include_history,
            history_first=history_first,
            page_size=response_page_size,
            max_pages=max_pages,
        )
        result = _envelope(rows, {"include_history": include_history, "stages_requested": len(stage_pairs)})
        if include_history:
            result["candidate_events"] = events
            result["discard_reasons"] = aggregate_discard_reasons(events)
        return result

    async def funnel(
        self,
        *,
        vacancy_ids: list[int] | None = None,
        vacancy_status: str | None = None,
        departments: list[str] | None = None,
        include_responses: bool = True,
        include_history: bool = False,
        history_first: int = 20,
        page_size: int | None = None,
        max_pages: int | None = None,
        max_stages: int | None = None,
    ) -> dict[str, Any]:
        vacancies = await self.fetch_vacancies(
            vacancy_ids=vacancy_ids,
            status=vacancy_status,
            departments=departments,
            page_size=page_size,
            max_pages=max_pages,
        )
        vacancy_rows = [flatten_vacancy(vacancy) for vacancy in vacancies["items"]]
        stage_rows = [
            flatten_workflow_stage(vacancy, stage)
            for vacancy in vacancies["items"]
            for stage in _workflow_stages(vacancy)
        ]

        response_rows: list[dict[str, Any]] = []
        events: list[dict[str, Any]] = []
        if include_responses:
            stage_pairs = [(vacancy, stage) for vacancy in vacancies["items"] for stage in _workflow_stages(vacancy)]
            if max_stages and len(stage_pairs) > max_stages:
                raise TalantixError(
                    f"Requested {len(stage_pairs)} workflow stages, max_stages is {max_stages}",
                    status_code=400,
                )
            response_rows, events = await self._fetch_responses_for_stage_pairs(
                stage_pairs,
                response_filter=None,
                include_history=include_history,
                history_first=history_first,
                page_size=_page_size(page_size, self._settings.talantix_page_size, 50),
                max_pages=max_pages,
            )

        return {
            "vacancies": vacancy_rows,
            "workflow_stages": stage_rows,
            "responses": response_rows,
            "source_breakdown": aggregate_source_breakdown(response_rows),
            "candidate_events": events,
            "discard_reasons": aggregate_discard_reasons(events),
            "meta": _meta(
                {
                    "vacancies_count": len(vacancy_rows),
                    "workflow_stages_count": len(stage_rows),
                    "responses_count": len(response_rows),
                    "include_responses": include_responses,
                    "include_history": include_history,
                }
            ),
        }

    async def bi_export(
        self,
        *,
        vacancy_ids: list[int] | None = None,
        vacancy_status: str | None = None,
        departments: list[str] | None = None,
        include_responses: bool = True,
        include_history: bool = True,
        include_persons: bool = True,
        include_dictionaries: bool = True,
        include_reference_data: bool = True,
        history_first: int = 20,
        lean_persons: bool = True,
        page_size: int | None = None,
        person_page_size: int | None = None,
        max_pages: int | None = None,
        max_stages: int | None = None,
    ) -> dict[str, Any]:
        tasks: dict[str, Any] = {
            "funnel": self.funnel(
                vacancy_ids=vacancy_ids,
                vacancy_status=vacancy_status,
                departments=departments,
                include_responses=include_responses,
                include_history=False,
                history_first=history_first,
                page_size=page_size,
                max_pages=max_pages,
                max_stages=max_stages,
            ),
            "hiring_requests": self.list_hiring_requests(page_size=page_size, max_pages=max_pages),
        }

        if include_reference_data:
            tasks["person_sources"] = self.list_person_sources(page_size=page_size, max_pages=max_pages)
            tasks["managers"] = self.list_managers(page_size=page_size, max_pages=max_pages)

        if include_dictionaries:
            tasks["dictionaries"] = self.dictionaries()

        if include_persons:
            tasks["persons"] = self.list_persons(
                vacancy_ids=vacancy_ids,
                include_history=include_history,
                history_first=history_first,
                lean=lean_persons,
                page_size=person_page_size or page_size,
                max_pages=max_pages,
            )

        result_names = list(tasks)
        result_values = await asyncio.gather(*tasks.values())
        results = dict(zip(result_names, result_values, strict=True))

        funnel = results["funnel"]
        persons = results.get("persons") or {}
        candidate_events = _dedupe_events(
            [
                *(funnel.get("candidate_events") or []),
                *(persons.get("candidate_events") or []),
            ]
        )
        responses = funnel.get("responses") or []

        dataset = {
            "vacancies": funnel.get("vacancies") or [],
            "workflow_stages": funnel.get("workflow_stages") or [],
            "responses": responses,
            "source_breakdown": aggregate_source_breakdown(responses),
            "candidate_events": candidate_events,
            "discard_reasons": aggregate_discard_reasons(candidate_events),
            "persons": persons.get("items") or [],
            "person_sources": (results.get("person_sources") or {}).get("items") or [],
            "managers": (results.get("managers") or {}).get("items") or [],
            "hiring_requests": (results.get("hiring_requests") or {}).get("items") or [],
            "dictionaries": (results.get("dictionaries") or {}).get("data") or {},
        }
        dataset["meta"] = _meta(
            {
                "dataset": "talantix_bi_export",
                "tables": {name: len(value) for name, value in dataset.items() if isinstance(value, list)},
                "include_responses": include_responses,
                "include_history": include_history,
                "include_persons": include_persons,
                "lean_persons": lean_persons,
                "include_dictionaries": include_dictionaries,
                "include_reference_data": include_reference_data,
            }
        )
        return dataset

    async def fetch_vacancies(
        self,
        *,
        vacancy_ids: list[int] | None = None,
        status: str | None = None,
        departments: list[str] | None = None,
        area_ids: list[str] | None = None,
        vacancy_title: str | None = None,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> dict[str, Any]:
        filter_value = compact_dict(
            {
                "vacancyIds": vacancy_ids,
                "vacancyStatus": _enum(status),
                "departments": departments,
                "areaIds": area_ids,
                "vacancyTitle": vacancy_title,
            }
        )
        items, meta = await self._paginate(
            query=q.VACANCIES_QUERY,
            variables={
                "filter": filter_value or None,
                "first": _page_size(page_size, self._settings.talantix_vacancy_page_size, 200),
            },
            connection_path=("vacancies",),
            max_pages=max_pages,
        )
        await self._enrich_vacancies(items)
        return {"items": items, "meta": meta}

    async def _enrich_vacancies(self, vacancies: list[dict[str, Any]]) -> None:
        semaphore = asyncio.Semaphore(self._settings.talantix_concurrency)

        async def worker(vacancy: dict[str, Any]) -> None:
            vacancy_id = vacancy.get("id")
            if vacancy_id is None:
                return
            async with semaphore:
                body = await self._client.execute(q.VACANCY_DETAILS_QUERY, {"id": vacancy_id})
            details = (body.get("data") or {}).get("vacancy") or {}
            if details.get("__typename") == "VacancyError":
                raise TalantixError(
                    f"Talantix returned VacancyError for vacancy {vacancy_id}",
                    details={"errorType": details.get("errorType"), "message": details.get("message")},
                )
            if details.get("__typename") != "VacancyItem":
                return
            vacancy["workflowStatuses"] = details.get("workflowStatuses")
            vacancy["externalVacancies"] = details.get("externalVacancies")

        await asyncio.gather(*(worker(vacancy) for vacancy in vacancies))

    async def _fetch_responses_for_stage_pairs(
        self,
        stage_pairs: list[tuple[dict[str, Any], dict[str, Any]]],
        *,
        response_filter: dict[str, Any] | None,
        include_history: bool,
        history_first: int,
        page_size: int,
        max_pages: int | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        semaphore = asyncio.Semaphore(self._settings.talantix_concurrency)

        async def worker(vacancy: dict[str, Any], stage: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
            async with semaphore:
                return await self._fetch_responses_for_stage(
                    stage=stage,
                    vacancy=vacancy,
                    response_filter=response_filter,
                    include_history=include_history,
                    history_first=history_first,
                    page_size=page_size,
                    max_pages=max_pages,
                )

        results = await asyncio.gather(*(worker(vacancy, stage) for vacancy, stage in stage_pairs))
        rows = [row for result_rows, _ in results for row in result_rows]
        events = [event for _, result_events in results for event in result_events]
        return rows, events

    async def _fetch_responses_for_stage(
        self,
        *,
        stage: dict[str, Any],
        vacancy: dict[str, Any] | None,
        response_filter: dict[str, Any] | None,
        include_history: bool,
        history_first: int,
        page_size: int,
        max_pages: int | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        variables: dict[str, Any] = {
            "id": stage["id"],
            "filter": response_filter or None,
            "first": page_size,
        }
        if include_history:
            variables["historyFirst"] = history_first

        items, _ = await self._paginate(
            query=q.workflow_status_responses_query(include_history),
            variables=variables,
            connection_path=("workflowStatus", "responses"),
            max_pages=max_pages,
            union_error_typenames={"WorkflowStatusError"},
        )
        rows = [flatten_response(item, vacancy_context=vacancy, stage_context=stage) for item in items]
        events = [
            event
            for item in items
            for event in flatten_history_events(item.get("person"), vacancy_context=vacancy)
        ]
        return rows, events

    async def _paginate(
        self,
        *,
        query: str,
        variables: dict[str, Any],
        connection_path: tuple[str, ...],
        cursor_variable: str = "after",
        max_pages: int | None = None,
        union_error_typenames: set[str] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        page_limit = max_pages if max_pages is not None else self._settings.talantix_max_pages
        cursor = variables.get(cursor_variable)
        items: list[dict[str, Any]] = []
        pages_read = 0
        truncated = False

        while page_limit is None or pages_read < page_limit:
            if cursor:
                variables[cursor_variable] = cursor
            elif cursor_variable in variables:
                variables[cursor_variable] = None

            body = await self._client.execute(query, variables)
            connection = _path(body.get("data") or {}, connection_path)
            if not isinstance(connection, dict):
                raise TalantixError(f"Talantix response does not contain {'.'.join(connection_path)}")

            typename = connection.get("__typename")
            if typename and union_error_typenames and typename in union_error_typenames:
                raise TalantixError(
                    f"Talantix returned {typename}",
                    details={"errorType": connection.get("errorType"), "message": connection.get("message")},
                )

            page_items = connection.get("items") or []
            items.extend(page_items)
            pages_read += 1

            page_info = connection.get("pageInfo") or {}
            next_cursor = page_info.get("endCursor")
            if not page_info.get("hasNextPage") or not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
            if page_limit is not None and pages_read >= page_limit:
                truncated = True
                break

        return items, _meta({"pages_read": pages_read, "page_limit": page_limit, "truncated": truncated})


def _workflow_stages(vacancy: dict[str, Any]) -> list[dict[str, Any]]:
    workflow_statuses = vacancy.get("workflowStatuses") or {}
    items = workflow_statuses.get("items")
    return items if isinstance(items, list) else []


def _dedupe_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any, Any]] = set()
    for event in events:
        key = (event.get("event_id"), event.get("person_id"), event.get("vacancy_id"))
        if key in seen:
            continue
        seen.add(key)
        result.append(event)
    return result


def _path(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _enum(value: str | None) -> str | None:
    return value.upper() if isinstance(value, str) and value else None


def _page_size(value: int | None, default: int, maximum: int) -> int:
    if value is None:
        return min(default, maximum)
    return max(1, min(value, maximum))


def _envelope(items: list[dict[str, Any]], meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"items": items, "count": len(items), "meta": _meta(meta or {})}


def _meta(extra: dict[str, Any]) -> dict[str, Any]:
    return {"generated_at": datetime.now(UTC).isoformat(), **extra}


def vacancy_filter_params(
    *,
    vacancy_id: str | None = None,
    status: str | None = None,
    department: str | None = None,
    area_id: str | None = None,
    vacancy_title: str | None = None,
) -> dict[str, Any]:
    return {
        "vacancy_ids": parse_csv_int(vacancy_id),
        "status": status,
        "departments": parse_csv(department),
        "area_ids": parse_csv(area_id),
        "vacancy_title": vacancy_title,
    }


def person_filter_params(
    *,
    search: str | None = None,
    source_id: str | None = None,
    vacancy_id: str | None = None,
    wf_status_name: str | None = None,
    current_wf_status_name: str | None = None,
    discard_reason_id: str | None = None,
    discard_type: str | None = None,
) -> dict[str, Any]:
    return {
        "search": search,
        "source_ids": parse_csv_int(source_id),
        "vacancy_ids": parse_csv_int(vacancy_id),
        "wf_status_names": parse_csv(wf_status_name),
        "current_wf_status_names": parse_csv(current_wf_status_name),
        "discard_reason_ids": parse_csv_int(discard_reason_id),
        "discard_type": discard_type,
    }
