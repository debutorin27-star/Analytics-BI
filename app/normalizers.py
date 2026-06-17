from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any


def compact_dict(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


def parse_csv(value: str | None) -> list[str] | None:
    if value is None or value == "":
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


def parse_csv_int(value: str | None) -> list[int] | None:
    items = parse_csv(value)
    return [int(item) for item in items] if items else None


def timestamp_to_iso(value: Any) -> str | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    seconds = number / 1000 if number > 10_000_000_000 else number
    try:
        return datetime.fromtimestamp(seconds, UTC).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def full_name(data: dict[str, Any] | None) -> str | None:
    if not data:
        return None
    parts = [data.get("lastName"), data.get("firstName"), data.get("middleName")]
    name = " ".join(str(part) for part in parts if part)
    return name or None


def list_items(container: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(container, dict):
        return []
    items = container.get("items")
    return items if isinstance(items, list) else []


def join_values(values: list[Any]) -> str | None:
    cleaned = [str(value) for value in values if value not in (None, "")]
    return ", ".join(cleaned) if cleaned else None


def flatten_area(area: dict[str, Any] | None) -> dict[str, Any]:
    area = area or {}
    return {
        "id": area.get("id"),
        "name": area.get("name"),
        "parent_id": area.get("parentId"),
    }


def flatten_manager(manager: dict[str, Any] | None) -> dict[str, Any]:
    manager = manager or {}
    return {
        "manager_id": manager.get("id"),
        "manager_hh_id": manager.get("hhManagerId"),
        "manager_name": full_name(manager),
        "manager_first_name": manager.get("firstName"),
        "manager_middle_name": manager.get("middleName"),
        "manager_last_name": manager.get("lastName"),
        "manager_email": manager.get("email"),
        "manager_role": manager.get("managerRole"),
        "manager_license_type": manager.get("licenseType"),
        "manager_blocked": manager.get("blocked"),
    }


def flatten_person(person: dict[str, Any] | None) -> dict[str, Any]:
    person = person or {}
    area = flatten_area(person.get("area"))
    metro = person.get("metroStation") or {}
    citizenships = list_items(person.get("citizenships"))
    contacts = list_items(person.get("contacts"))
    tags = list_items(person.get("tags"))
    files = person.get("files") or {}
    photos = list_items(person.get("photos"))
    resumes = list_items(person.get("resumes"))
    source = person.get("source") or {}

    emails = [item.get("value") for item in contacts if item.get("type") == "email"]
    phones = [item.get("value") for item in contacts if item.get("type") in {"cell", "phone"}]

    return {
        "person_id": person.get("id"),
        "person_name": full_name(person),
        "person_first_name": person.get("firstName"),
        "person_middle_name": person.get("middleName"),
        "person_last_name": person.get("lastName"),
        "age": person.get("age"),
        "birth_day": person.get("birthDay"),
        "birth_day_iso": timestamp_to_iso(person.get("birthDay")),
        "gender": person.get("gender"),
        "updated_at": person.get("updatedAt"),
        "updated_at_iso": timestamp_to_iso(person.get("updatedAt")),
        "score": person.get("score"),
        "area_id": area["id"],
        "area_name": area["name"],
        "metro_station_id": metro.get("id"),
        "metro_station_name": metro.get("name"),
        "citizenship_ids": [item.get("id") for item in citizenships],
        "citizenship_names": [item.get("name") for item in citizenships],
        "contacts": contacts,
        "emails": emails,
        "phones": phones,
        "source_id": source.get("id"),
        "source_name": source.get("name"),
        "source_type": source.get("type"),
        "tag_ids": [item.get("id") for item in tags],
        "tag_names": [item.get("name") for item in tags],
        "files_count": files.get("count"),
        "files": list_items(files),
        "photos": photos,
        "resumes": resumes,
        "responses_count": (person.get("responses") or {}).get("count"),
        "hidden_fields": person.get("hiddenFields"),
        "updatable_with_contacts": person.get("updatableWithContacts"),
    }


def flatten_vacancy(vacancy: dict[str, Any]) -> dict[str, Any]:
    salary = vacancy.get("salary") or {}
    source = vacancy.get("source") or {}
    areas = list_items(vacancy.get("areas"))
    managers = list_items(vacancy.get("vacancyManagers"))
    manager_payloads = [item.get("manager") or {} for item in managers]
    counters = vacancy.get("hiringPositionCounters") or {}
    external = vacancy.get("externalVacancies") or {}
    external_hh = external.get("hh") or {}
    external_avito = external.get("avito") or {}

    return {
        "vacancy_id": vacancy.get("id"),
        "vacancy_title": vacancy.get("title"),
        "department": vacancy.get("department"),
        "description": vacancy.get("description"),
        "status": vacancy.get("status"),
        "created_at": vacancy.get("createdAt"),
        "created_at_iso": timestamp_to_iso(vacancy.get("createdAt")),
        "status_updated_at": vacancy.get("statusUpdatedAt"),
        "status_updated_at_iso": timestamp_to_iso(vacancy.get("statusUpdatedAt")),
        "proposed_date_of_close": vacancy.get("proposedDateOfClose"),
        "proposed_date_of_close_iso": timestamp_to_iso(vacancy.get("proposedDateOfClose")),
        "url": vacancy.get("url"),
        "salary_currency": salary.get("currency"),
        "salary_from": salary.get("from"),
        "salary_to": salary.get("to"),
        "area_ids": [item.get("id") for item in areas],
        "area_names": [item.get("name") for item in areas],
        "area_names_text": join_values([item.get("name") for item in areas]),
        "source_type": source.get("type"),
        "source_href": source.get("href"),
        "planned_hires": counters.get("planned"),
        "hired_count": counters.get("hired"),
        "manager_ids": [item.get("id") for item in manager_payloads],
        "manager_names": [full_name(item) for item in manager_payloads],
        "manager_emails": [item.get("email") for item in manager_payloads],
        "manager_names_text": join_values([full_name(item) for item in manager_payloads]),
        "external_hh_count": external_hh.get("count"),
        "external_avito_count": external_avito.get("count"),
        "unread_by_owner": vacancy.get("unreadByOwner"),
        "vacancy_locks": vacancy.get("vacancyLocks"),
    }


def flatten_workflow_stage(vacancy: dict[str, Any], stage: dict[str, Any]) -> dict[str, Any]:
    counters = stage.get("personCounters") or {}
    sla = stage.get("sla") or {}
    return {
        "vacancy_id": vacancy.get("id"),
        "vacancy_title": vacancy.get("title"),
        "department": vacancy.get("department"),
        "vacancy_status": vacancy.get("status"),
        "workflow_status_id": stage.get("id"),
        "workflow_status_name": stage.get("name"),
        "workflow_status_position": stage.get("position"),
        "workflow_status_type": stage.get("statusType"),
        "current_candidates": counters.get("all"),
        "unread_candidates": counters.get("unread"),
        "sla_days": sla.get("slaDays"),
        "sla_can_edit": sla.get("canEdit"),
        "is_auto_filter_source": stage.get("isAutoFilterSource"),
        "import_from_hh_statuses": stage.get("importFromHhStatuses"),
    }


def flatten_response(
    response: dict[str, Any],
    *,
    vacancy_context: dict[str, Any] | None = None,
    stage_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    person = response.get("person") or {}
    person_row = flatten_person(person)
    workflow_status = _workflow_status_item(response.get("workflowStatus")) or stage_context or {}
    vacancy = _vacancy_item((workflow_status or {}).get("vacancy")) or vacancy_context or {}
    hh_test = response.get("hhTestResult") or {}
    hh_topic = response.get("hhVacancyTopic") or {}

    row = {
        "response_key": _response_key(person.get("id"), vacancy.get("id"), workflow_status.get("id")),
        "person_id": person.get("id"),
        "vacancy_id": vacancy.get("id"),
        "vacancy_title": vacancy.get("title"),
        "department": vacancy.get("department"),
        "workflow_status_id": workflow_status.get("id"),
        "workflow_status_name": workflow_status.get("name"),
        "workflow_status_position": workflow_status.get("position"),
        "workflow_status_type": workflow_status.get("statusType"),
        "cover_letter": response.get("coverLetter"),
        "rating": response.get("rating"),
        "unread": response.get("unread"),
        "updated_at": response.get("updatedAt"),
        "updated_at_iso": timestamp_to_iso(response.get("updatedAt")),
        "url": response.get("url"),
        "hh_test_score": hh_test.get("score"),
        "hh_test_url": hh_test.get("url"),
        "hh_vacancy_id": hh_topic.get("hhVacancyId"),
        "hh_resume_url": hh_topic.get("hhResumeUrl"),
    }
    row.update(person_row)
    return row


def flatten_history_events(
    person: dict[str, Any] | None,
    *,
    vacancy_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not person:
        return []
    person_row = flatten_person(person)
    result: list[dict[str, Any]] = []
    for event in list_items(person.get("history")):
        vacancy = _vacancy_item(event.get("vacancy")) or vacancy_context or {}
        status = event.get("status") or {}
        initiator = event.get("initiator") or {}
        discard_info = event.get("discardInfo") or {}
        hh_vacancy = event.get("hhVacancy") or {}
        result.append(
            {
                "event_id": event.get("id"),
                "event_type": event.get("__typename"),
                "event_time": event.get("eventTime"),
                "event_time_iso": timestamp_to_iso(event.get("eventTime")),
                "person_id": person_row.get("person_id"),
                "person_name": person_row.get("person_name"),
                "vacancy_id": vacancy.get("id"),
                "vacancy_title": vacancy.get("title"),
                "workflow_status_id": status.get("id"),
                "workflow_status_name": status.get("name"),
                "process_type": event.get("processType"),
                "discard_initiator": discard_info.get("initiator"),
                "discard_reasons": discard_info.get("reasons") or [],
                "initiator_type": initiator.get("__typename"),
                "initiator_manager_id": initiator.get("id"),
                "initiator_name": full_name(initiator),
                "initiator_email": initiator.get("email"),
                "hh_response_type": event.get("responseType"),
                "hh_vacancy_id": hh_vacancy.get("id"),
                "hh_vacancy_name": hh_vacancy.get("name"),
                "hh_vacancy_link": hh_vacancy.get("link"),
            }
        )
    return result


def flatten_hiring_request(item: dict[str, Any]) -> dict[str, Any]:
    salary = item.get("salary") or {}
    counters = item.get("hiringPositionCounters") or {}
    managers = list_items(item.get("managers"))
    areas = list_items(item.get("areas"))
    vacancy = _vacancy_item(item.get("vacancy")) or {}
    custom_fields = list_items(item.get("customFields"))
    return {
        "hiring_request_id": item.get("id"),
        "name": item.get("name"),
        "department": item.get("department"),
        "description": item.get("description"),
        "status": item.get("status"),
        "creation_reason": item.get("creationReason"),
        "created_at": item.get("createdAt"),
        "created_at_iso": timestamp_to_iso(item.get("createdAt")),
        "approved_at": item.get("approvedAt"),
        "approved_at_iso": timestamp_to_iso(item.get("approvedAt")),
        "updated_at": item.get("updatedAt"),
        "updated_at_iso": timestamp_to_iso(item.get("updatedAt")),
        "withdrawn_at": item.get("withdrawnAt"),
        "withdrawn_at_iso": timestamp_to_iso(item.get("withdrawnAt")),
        "proposed_date_of_close": item.get("proposedDateOfClose"),
        "proposed_date_of_close_iso": timestamp_to_iso(item.get("proposedDateOfClose")),
        "withdraw_reason": item.get("withdrawReason"),
        "withdraw_comment": item.get("withdrawComment"),
        "salary_currency": salary.get("currency"),
        "salary_from": salary.get("from"),
        "salary_to": salary.get("to"),
        "area_ids": [area.get("id") for area in areas],
        "area_names": [area.get("name") for area in areas],
        "planned_hires": counters.get("planned"),
        "hired_count": counters.get("hired"),
        "manager_ids": [manager.get("id") for manager in managers],
        "manager_names": [full_name(manager) for manager in managers],
        "manager_emails": [manager.get("email") for manager in managers],
        "custom_fields": custom_fields,
        "vacancy_id": vacancy.get("id"),
        "vacancy_title": vacancy.get("title"),
        "can_edit": item.get("canEdit"),
        "can_request_approve": item.get("canRequestApprove"),
        "can_withdraw": item.get("canWithdraw"),
    }


def aggregate_source_breakdown(responses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[tuple[Any, ...]] = Counter()
    for row in responses:
        key = (
            row.get("vacancy_id"),
            row.get("vacancy_title"),
            row.get("workflow_status_id"),
            row.get("workflow_status_name"),
            row.get("source_id"),
            row.get("source_name") or "unknown",
            row.get("source_type") or "unknown",
        )
        counter[key] += 1

    return [
        {
            "vacancy_id": key[0],
            "vacancy_title": key[1],
            "workflow_status_id": key[2],
            "workflow_status_name": key[3],
            "source_id": key[4],
            "source_name": key[5],
            "source_type": key[6],
            "count": count,
        }
        for key, count in sorted(counter.items(), key=lambda item: (str(item[0][1]), str(item[0][3]), str(item[0][5])))
    ]


def aggregate_discard_reasons(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[tuple[Any, ...]] = Counter()
    for event in events:
        reasons = event.get("discard_reasons") or []
        for reason in reasons:
            key = (
                event.get("vacancy_id"),
                event.get("vacancy_title"),
                event.get("workflow_status_id"),
                event.get("workflow_status_name"),
                event.get("discard_initiator") or "unknown",
                reason or "unknown",
            )
            counter[key] += 1

    return [
        {
            "vacancy_id": key[0],
            "vacancy_title": key[1],
            "workflow_status_id": key[2],
            "workflow_status_name": key[3],
            "discard_initiator": key[4],
            "discard_reason": key[5],
            "count": count,
        }
        for key, count in sorted(counter.items(), key=lambda item: (str(item[0][1]), str(item[0][5])))
    ]


def _workflow_status_item(workflow_status: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(workflow_status, dict):
        return None
    if workflow_status.get("__typename") in {"WorkflowStatusItem", "WorkflowStatusPublicItem"}:
        return workflow_status
    return None


def _vacancy_item(vacancy: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(vacancy, dict):
        return None
    if vacancy.get("__typename") in {"VacancyItem", "VacancyPublicItem"}:
        return vacancy
    return None


def _response_key(person_id: Any, vacancy_id: Any, workflow_status_id: Any) -> str:
    return f"{person_id or 'unknown'}:{vacancy_id or 'unknown'}:{workflow_status_id or 'unknown'}"
