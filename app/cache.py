from __future__ import annotations

import asyncio
import copy
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import Settings
from app.normalizers import aggregate_discard_reasons, aggregate_source_breakdown
from app.services import TalantixBIService


DATE_FIELDS: dict[str, tuple[str, ...]] = {
    "vacancies": ("status_updated_at_iso", "created_at_iso"),
    "responses": ("updated_at_iso",),
    "candidate_events": ("event_time_iso",),
    "persons": ("updated_at_iso",),
    "hiring_requests": ("updated_at_iso", "created_at_iso", "approved_at_iso", "withdrawn_at_iso"),
}

TABLE_ALIASES: dict[str, str] = {
    "vacancies": "vacancies",
    "workflow_stages": "workflow_stages",
    "workflow-stages": "workflow_stages",
    "responses": "responses",
    "source_breakdown": "source_breakdown",
    "source-breakdown": "source_breakdown",
    "candidate_events": "candidate_events",
    "candidate-events": "candidate_events",
    "discard_reasons": "discard_reasons",
    "discard-reasons": "discard_reasons",
    "persons": "persons",
    "person_sources": "person_sources",
    "person-sources": "person_sources",
    "managers": "managers",
    "hiring_requests": "hiring_requests",
    "hiring-requests": "hiring_requests",
}
PUBLIC_TABLE_NAMES: tuple[str, ...] = (
    "vacancies",
    "workflow-stages",
    "responses",
    "source-breakdown",
    "candidate-events",
    "discard-reasons",
    "persons",
    "person-sources",
    "managers",
    "hiring-requests",
)
TABLE_EXCLUDED_COLUMNS: dict[str, set[str]] = {
    "vacancies": {"description"},
}


class BIDataCache:
    def __init__(self, service: TalantixBIService, settings: Settings) -> None:
        self._service = service
        self._settings = settings
        self._path = Path(settings.bi_cache_file)
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._dataset: dict[str, Any] | None = self._load_from_disk()
        self._status: dict[str, Any] = {
            "running": False,
            "last_started_at": None,
            "last_success_at": (self._dataset or {}).get("meta", {}).get("cache_updated_at"),
            "last_error_at": None,
            "last_error": None,
            "cache_file": str(self._path),
            "has_cache": self._dataset is not None,
            "is_full_history": bool((self._dataset or {}).get("meta", {}).get("is_full_history")),
            "sync_scope": (self._dataset or {}).get("meta", {}).get("sync_scope"),
            "tables": (self._dataset or {}).get("meta", {}).get("tables"),
        }

    def start(self) -> None:
        if not self._settings.sync_enabled or self._task:
            return
        self._task = asyncio.create_task(self._run_periodic(), name="talantix-bi-sync")

    async def stop(self) -> None:
        if not self._task:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    def status(self) -> dict[str, Any]:
        meta = (self._dataset or {}).get("meta", {})
        return {
            **self._status,
            "has_cache": self._dataset is not None,
            "is_full_history": bool(meta.get("is_full_history")),
            "sync_scope": meta.get("sync_scope"),
            "tables": meta.get("tables"),
        }

    async def get(self, *, updated_from: str | None = None) -> dict[str, Any]:
        if self._dataset is None:
            raise CacheNotReadyError("BI cache is empty. Wait for sync or call /api/v1/bi/sync.")

        dataset = copy.deepcopy(self._dataset)
        strip_excluded_columns(dataset)
        if updated_from:
            dataset = filter_dataset_since(dataset, updated_from)
        return dataset

    async def sync_once(
        self,
        *,
        force: bool = False,
        page_size: int | None = None,
        person_page_size: int | None = None,
        max_pages: int | None = None,
        max_stages: int | None = None,
        history_first: int | None = None,
    ) -> dict[str, Any]:
        if self._lock.locked() and not force:
            return self.status()

        async with self._lock:
            started = time.monotonic()
            started_at = _now_iso()
            self._status.update(
                {
                    "running": True,
                    "last_started_at": started_at,
                    "last_error": None,
                    "last_error_at": None,
                }
            )
            try:
                effective_page_size = page_size or self._settings.bi_sync_page_size
                effective_person_page_size = person_page_size or self._settings.bi_sync_person_page_size
                effective_max_pages = max_pages if max_pages is not None else self._settings.bi_sync_max_pages
                effective_max_stages = max_stages if max_stages is not None else self._settings.bi_sync_max_stages
                effective_history_first = history_first or self._settings.bi_sync_history_first
                is_full_history = effective_max_pages is None and effective_max_stages is None

                dataset = await self._service.bi_export(
                    include_responses=True,
                    include_history=True,
                    include_persons=True,
                    include_dictionaries=True,
                    include_reference_data=True,
                    lean_persons=True,
                    page_size=effective_page_size,
                    person_page_size=effective_person_page_size,
                    max_pages=effective_max_pages,
                    max_stages=effective_max_stages,
                    history_first=effective_history_first,
                )
                strip_excluded_columns(dataset)
                cache_updated_at = _now_iso()
                dataset.setdefault("meta", {})
                dataset["meta"].update(
                    {
                        "cache_updated_at": cache_updated_at,
                        "sync_duration_seconds": round(time.monotonic() - started, 3),
                        "sync_scope": "full_history" if is_full_history else "limited",
                        "is_full_history": is_full_history,
                        "sync_parameters": {
                            "page_size": effective_page_size,
                            "person_page_size": effective_person_page_size,
                            "max_pages": effective_max_pages,
                            "max_stages": effective_max_stages,
                            "history_first": effective_history_first,
                        },
                    }
                )
                self._write_to_disk(dataset)
                self._dataset = dataset
                self._status.update(
                    {
                        "running": False,
                        "last_success_at": cache_updated_at,
                        "last_error": None,
                        "last_error_at": None,
                        "has_cache": True,
                        "is_full_history": is_full_history,
                        "sync_scope": dataset["meta"].get("sync_scope"),
                        "tables": dataset["meta"].get("tables"),
                    }
                )
            except Exception as exc:
                self._status.update(
                    {
                        "running": False,
                        "last_error_at": _now_iso(),
                        "last_error": f"{type(exc).__name__}: {exc}",
                        "has_cache": self._dataset is not None,
                    }
                )
                raise
        return self.status()

    async def _run_periodic(self) -> None:
        if self._settings.sync_on_startup:
            await self._run_sync_safely()

        while True:
            await asyncio.sleep(self._settings.sync_interval_seconds)
            await self._run_sync_safely()

    async def _run_sync_safely(self) -> None:
        try:
            await self.sync_once()
        except Exception:
            # Status already contains the error. Keep the last good cache serving BI.
            return

    def _load_from_disk(self) -> dict[str, Any] | None:
        if not self._path.exists():
            return None
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def _write_to_disk(self, dataset: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(self._path)


class CacheNotReadyError(Exception):
    pass


def filter_dataset_since(dataset: dict[str, Any], updated_from: str) -> dict[str, Any]:
    cutoff = parse_datetime(updated_from)
    result = copy.deepcopy(dataset)
    source = copy.deepcopy(dataset)

    changed_rows: dict[str, list[dict[str, Any]]] = {}
    for table_name, date_fields in DATE_FIELDS.items():
        rows = source.get(table_name)
        if isinstance(rows, list):
            changed_rows[table_name] = [row for row in rows if _row_is_newer(row, date_fields, cutoff)]

    changed_vacancy_ids = _value_set(changed_rows.get("vacancies") or [], "vacancy_id", "id")
    changed_person_ids = _value_set(changed_rows.get("persons") or [], "person_id", "id")
    changed_response_rows = changed_rows.get("responses") or []
    changed_event_rows = changed_rows.get("candidate_events") or []
    changed_hiring_rows = changed_rows.get("hiring_requests") or []

    related_vacancy_ids = set(changed_vacancy_ids)
    related_vacancy_ids.update(_value_set(changed_response_rows, "vacancy_id"))
    related_vacancy_ids.update(_value_set(changed_event_rows, "vacancy_id"))
    related_vacancy_ids.update(_value_set(changed_hiring_rows, "vacancy_id"))

    related_person_ids = set(changed_person_ids)
    related_person_ids.update(_value_set(changed_response_rows, "person_id"))
    related_person_ids.update(_value_set(changed_event_rows, "person_id"))

    all_vacancies = _list_table(source, "vacancies")
    all_responses = _list_table(source, "responses")
    all_events = _list_table(source, "candidate_events")
    all_persons = _list_table(source, "persons")
    all_workflow_stages = _list_table(source, "workflow_stages")

    result["vacancies"] = [
        row
        for row in all_vacancies
        if _row_id(row, "vacancy_id", "id") in related_vacancy_ids
        or _row_is_newer(row, DATE_FIELDS["vacancies"], cutoff)
    ]
    result["responses"] = [
        row
        for row in all_responses
        if _row_is_newer(row, DATE_FIELDS["responses"], cutoff)
        or _row_id(row, "vacancy_id") in changed_vacancy_ids
    ]
    result["candidate_events"] = [
        row
        for row in all_events
        if _row_is_newer(row, DATE_FIELDS["candidate_events"], cutoff)
        or _row_id(row, "vacancy_id") in changed_vacancy_ids
    ]

    related_vacancy_ids.update(_value_set(result["responses"], "vacancy_id"))
    related_vacancy_ids.update(_value_set(result["candidate_events"], "vacancy_id"))
    related_person_ids.update(_value_set(result["responses"], "person_id"))
    related_person_ids.update(_value_set(result["candidate_events"], "person_id"))

    result["vacancies"] = [
        row
        for row in all_vacancies
        if _row_id(row, "vacancy_id", "id") in related_vacancy_ids
        or _row_is_newer(row, DATE_FIELDS["vacancies"], cutoff)
    ]
    result["persons"] = [
        row
        for row in all_persons
        if _row_id(row, "person_id", "id") in related_person_ids
        or _row_is_newer(row, DATE_FIELDS["persons"], cutoff)
    ]
    result["workflow_stages"] = [
        row for row in all_workflow_stages if _row_id(row, "vacancy_id") in related_vacancy_ids
    ]

    for table_name in ("hiring_requests",):
        result[table_name] = changed_rows.get(table_name, [])

    responses = result.get("responses") if isinstance(result.get("responses"), list) else []
    events = result.get("candidate_events") if isinstance(result.get("candidate_events"), list) else []
    result["source_breakdown"] = aggregate_source_breakdown(responses)
    result["discard_reasons"] = aggregate_discard_reasons(events)
    result.setdefault("meta", {})
    result["meta"].update({"updated_from": updated_from, "filtered_at": _now_iso()})
    result["meta"]["tables"] = {name: len(value) for name, value in result.items() if isinstance(value, list)}
    return result


def table_registry(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "name": public_name,
            "canonical_name": canonical_name,
            "rows": len(dataset.get(canonical_name) or []),
            "endpoint": f"/api/v1/bi/tables/{public_name}",
        }
        for public_name in PUBLIC_TABLE_NAMES
        for canonical_name in (TABLE_ALIASES[public_name],)
        if isinstance(dataset.get(canonical_name), list)
    ]


def dictionary_registry(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    dictionaries = dataset.get("dictionaries") or {}
    if not isinstance(dictionaries, dict):
        return []

    result: list[dict[str, Any]] = []
    for name, payload in sorted(dictionaries.items()):
        rows = _dictionary_items(payload)
        result.append(
            {
                "name": name,
                "rows": len(rows),
                "endpoint": f"/api/v1/bi/dictionaries/{name}",
            }
        )
    return result


def dataset_table(dataset: dict[str, Any], table_name: str, *, flat: bool = True) -> list[dict[str, Any]]:
    canonical_name = TABLE_ALIASES.get(table_name) or TABLE_ALIASES.get(table_name.replace("_", "-"))
    if not canonical_name:
        raise KeyError(table_name)
    rows = dataset.get(canonical_name)
    if not isinstance(rows, list):
        raise KeyError(table_name)
    strip_excluded_columns({canonical_name: rows})
    return flatten_rows(rows) if flat else rows


def dictionary_table(dataset: dict[str, Any], dictionary_name: str, *, flat: bool = True) -> list[dict[str, Any]]:
    dictionaries = dataset.get("dictionaries") or {}
    if not isinstance(dictionaries, dict) or dictionary_name not in dictionaries:
        raise KeyError(dictionary_name)
    rows = [{"dictionary_name": dictionary_name, **row} for row in _dictionary_items(dictionaries[dictionary_name])]
    return flatten_rows(rows) if flat else rows


def flatten_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [flatten_row(row) for row in rows]


def flatten_row(row: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, dict):
            if _is_scalar_dict(value):
                for nested_key, nested_value in value.items():
                    result[f"{key}_{nested_key}"] = _format_flat_value(nested_value)
            else:
                result[key] = json.dumps(value, ensure_ascii=False, default=str)
            continue
        result[key] = _format_flat_value(value)
    return result


def strip_excluded_columns(dataset: dict[str, Any]) -> dict[str, Any]:
    for table_name, excluded_columns in TABLE_EXCLUDED_COLUMNS.items():
        rows = dataset.get(table_name)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict):
                for column in excluded_columns:
                    row.pop(column, None)
    return dataset


def parse_datetime(value: str) -> datetime:
    normalized = value.strip()
    if normalized.isdigit():
        number = int(normalized)
        seconds = number / 1000 if number > 10_000_000_000 else number
        return datetime.fromtimestamp(seconds, UTC)
    if len(normalized) == 10:
        normalized = normalized + "T00:00:00+00:00"
    normalized = normalized.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _row_is_newer(row: dict[str, Any], date_fields: tuple[str, ...], cutoff: datetime) -> bool:
    for field in date_fields:
        value = row.get(field)
        if not value:
            continue
        try:
            if parse_datetime(str(value)) >= cutoff:
                return True
        except ValueError:
            continue
    return False


def _list_table(dataset: dict[str, Any], table_name: str) -> list[dict[str, Any]]:
    rows = dataset.get(table_name)
    return rows if isinstance(rows, list) else []


def _value_set(rows: list[dict[str, Any]], *fields: str) -> set[Any]:
    result: set[Any] = set()
    for row in rows:
        value = _row_id(row, *fields)
        if value is not None:
            result.add(value)
    return result


def _row_id(row: dict[str, Any], *fields: str) -> Any:
    for field in fields:
        value = row.get(field)
        if value is not None:
            return value
    return None


def _dictionary_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        items = payload.get("items")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
        return [payload] if payload else []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _format_flat_value(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list):
        if not value:
            return None
        if all(_is_scalar(item) for item in value):
            return ", ".join(str(item) for item in value if item is not None)
        return json.dumps(value, ensure_ascii=False, default=str)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def _is_scalar_dict(value: dict[str, Any]) -> bool:
    return all(_is_scalar(item) for item in value.values())


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, str | int | float | bool)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
