from app.normalizers import (
    aggregate_discard_reasons,
    aggregate_source_breakdown,
    flatten_history_events,
    flatten_response,
    flatten_vacancy,
    timestamp_to_iso,
)


def test_timestamp_to_iso_handles_milliseconds() -> None:
    assert timestamp_to_iso(1703513801000) == "2023-12-25T14:16:41+00:00"


def test_timestamp_to_iso_ignores_out_of_range_values() -> None:
    assert timestamp_to_iso("-6817599744000") is None


def test_flatten_vacancy_keeps_bi_dimensions() -> None:
    row = flatten_vacancy(
        {
            "id": 1,
            "title": "Manager",
            "department": "Sales",
            "status": "active",
            "createdAt": 1703513801000,
            "salary": {"currency": "RUR", "from": 100000, "to": 150000},
            "areas": {"items": [{"id": "1", "name": "Moscow"}]},
            "source": {"type": "TMS", "href": "https://example.com"},
            "hiringPositionCounters": {"planned": 2, "hired": 1},
            "vacancyManagers": {
                "items": [
                    {
                        "vacancyRole": "OWNER",
                        "manager": {
                            "id": 10,
                            "firstName": "Ivan",
                            "lastName": "Petrov",
                            "email": "ivan@example.com",
                        },
                    }
                ]
            },
            "externalVacancies": {"hh": {"count": 1}, "avito": {"count": 0}},
        }
    )

    assert row["vacancy_id"] == 1
    assert row["salary_from"] == 100000
    assert row["area_names"] == ["Moscow"]
    assert row["manager_names"] == ["Petrov Ivan"]
    assert row["external_hh_count"] == 1


def test_flatten_response_and_source_breakdown() -> None:
    response = {
        "rating": 5,
        "unread": True,
        "updatedAt": 1703513801000,
        "workflowStatus": {
            "__typename": "WorkflowStatusItem",
            "id": 7,
            "name": "Offer",
            "position": 4,
            "statusType": "OFFER",
            "vacancy": {
                "__typename": "VacancyItem",
                "id": 3,
                "title": "Manager",
                "department": "Sales",
            },
        },
        "person": {
            "id": 99,
            "firstName": "Anna",
            "lastName": "Ivanova",
            "source": {"id": 5, "name": "hh.ru", "type": "HH"},
            "contacts": {"items": [{"type": "email", "value": "a@example.com"}]},
        },
    }

    row = flatten_response(response)
    assert row["response_key"] == "99:3:7"
    assert row["person_name"] == "Ivanova Anna"
    assert row["source_name"] == "hh.ru"

    breakdown = aggregate_source_breakdown([row])
    assert breakdown == [
        {
            "vacancy_id": 3,
            "vacancy_title": "Manager",
            "workflow_status_id": 7,
            "workflow_status_name": "Offer",
            "source_id": 5,
            "source_name": "hh.ru",
            "source_type": "HH",
            "count": 1,
        }
    ]


def test_flatten_history_events_and_discard_reasons() -> None:
    person = {
        "id": 99,
        "firstName": "Anna",
        "lastName": "Ivanova",
        "history": {
            "items": [
                {
                    "__typename": "WorkflowStatusChanged",
                    "id": "event-1",
                    "eventTime": 1703513801000,
                    "status": {"id": 8, "name": "Rejected"},
                    "vacancy": {"__typename": "VacancyItem", "id": 3, "title": "Manager"},
                    "discardInfo": {"initiator": "EMPLOYER", "reasons": ["No experience"]},
                }
            ]
        },
    }

    events = flatten_history_events(person)
    assert events[0]["discard_reasons"] == ["No experience"]

    aggregate = aggregate_discard_reasons(events)
    assert aggregate[0]["discard_reason"] == "No experience"
    assert aggregate[0]["count"] == 1
