from app.cache import dataset_table, dictionary_table, filter_dataset_since, parse_datetime, table_registry


def test_filter_dataset_since_filters_tables_and_rebuilds_aggregates() -> None:
    dataset = {
        "vacancies": [
            {"vacancy_id": "v1", "created_at_iso": "2024-04-01T00:00:00+00:00", "status_updated_at_iso": None},
            {"vacancy_id": "v2", "created_at_iso": "2024-06-01T00:00:00+00:00", "status_updated_at_iso": None},
            {"vacancy_id": "v3", "created_at_iso": "2024-04-01T00:00:00+00:00", "status_updated_at_iso": None},
        ],
        "workflow_stages": [
            {"workflow_status_id": "s1", "vacancy_id": "v1"},
            {"workflow_status_id": "s2", "vacancy_id": "v2"},
            {"workflow_status_id": "s3", "vacancy_id": "v3"},
        ],
        "responses": [
            {
                "id": "r1",
                "vacancy_id": "v1",
                "person_id": "p1",
                "updated_at_iso": "2024-04-01T00:00:00+00:00",
                "source_id": "hh",
                "source_name": "hh.ru",
            },
            {
                "id": "r2",
                "vacancy_id": "v1",
                "person_id": "p1",
                "updated_at_iso": "2024-06-01T00:00:00+00:00",
                "source_id": "avito",
                "source_name": "Avito",
            },
        ],
        "candidate_events": [
            {
                "id": "e1",
                "vacancy_id": "v3",
                "person_id": "p3",
                "event_time_iso": "2024-04-01T00:00:00+00:00",
                "discard_reasons": ["Не устроила зарплата"],
            },
            {
                "id": "e2",
                "vacancy_id": "v1",
                "person_id": "p1",
                "event_time_iso": "2024-06-01T00:00:00+00:00",
                "discard_reasons": ["Не подходит опыт"],
            },
        ],
        "persons": [
            {"person_id": "p1", "updated_at_iso": "2024-04-01T00:00:00+00:00"},
            {"person_id": "p2", "updated_at_iso": "2024-06-01T00:00:00+00:00"},
            {"person_id": "p3", "updated_at_iso": "2024-04-01T00:00:00+00:00"},
        ],
        "person_sources": [{"id": "hh", "name": "hh.ru"}],
        "meta": {},
    }

    result = filter_dataset_since(dataset, "2024-05-01")

    assert {row["vacancy_id"] for row in result["vacancies"]} == {"v1", "v2"}
    assert {row["workflow_status_id"] for row in result["workflow_stages"]} == {"s1", "s2"}
    assert [row["id"] for row in result["responses"]] == ["r2"]
    assert [row["id"] for row in result["candidate_events"]] == ["e2"]
    assert {row["person_id"] for row in result["persons"]} == {"p1", "p2"}
    assert result["person_sources"] == [{"id": "hh", "name": "hh.ru"}]
    assert result["source_breakdown"][0]["source_name"] == "Avito"
    assert result["discard_reasons"][0]["discard_reason"] == "Не подходит опыт"
    assert result["meta"]["updated_from"] == "2024-05-01"


def test_parse_datetime_accepts_unix_milliseconds() -> None:
    assert parse_datetime("1717200000000").isoformat() == "2024-06-01T00:00:00+00:00"


def test_dataset_table_returns_flat_rows_and_strips_vacancy_description() -> None:
    dataset = {
        "vacancies": [
            {
                "vacancy_id": 1,
                "vacancy_title": "Manager",
                "description": "large html text",
                "area_names": ["Moscow", "Kazan"],
                "salary": {"from": 100000, "to": 150000},
            }
        ],
        "meta": {},
    }

    rows = dataset_table(dataset, "vacancies")

    assert rows == [
        {
            "vacancy_id": 1,
            "vacancy_title": "Manager",
            "area_names": "Moscow, Kazan",
            "salary_from": 100000,
            "salary_to": 150000,
        }
    ]
    assert "description" not in dataset["vacancies"][0]


def test_dictionary_table_flattens_dictionary_items() -> None:
    dataset = {
        "dictionaries": {
            "languages": {
                "items": [
                    {
                        "id": "en",
                        "name": "English",
                        "level": {"id": "b2", "name": "B2"},
                    }
                ]
            }
        }
    }

    assert dictionary_table(dataset, "languages") == [
        {
            "dictionary_name": "languages",
            "id": "en",
            "name": "English",
            "level_id": "b2",
            "level_name": "B2",
        }
    ]


def test_table_registry_exposes_preferred_table_endpoints() -> None:
    registry = table_registry({"vacancies": [], "workflow_stages": []})

    assert registry == [
        {
            "name": "vacancies",
            "canonical_name": "vacancies",
            "rows": 0,
            "endpoint": "/api/v1/bi/tables/vacancies",
        },
        {
            "name": "workflow-stages",
            "canonical_name": "workflow_stages",
            "rows": 0,
            "endpoint": "/api/v1/bi/tables/workflow-stages",
        },
    ]
