from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.cache import BIDataCache, CacheNotReadyError
from app.config import Settings, get_settings
from app.models import GraphQLRequest
from app.normalizers import compact_dict, parse_csv, parse_csv_int
from app.services import TalantixBIService, person_filter_params, vacancy_filter_params
from app.talantix_client import TalantixClient, TalantixError


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    client = TalantixClient(settings)
    service = TalantixBIService(client, settings)
    cache = BIDataCache(service, settings)
    app.state.settings = settings
    app.state.talantix_client = client
    app.state.bi_service = service
    app.state.bi_cache = cache
    cache.start()
    try:
        yield
    finally:
        await cache.stop()
        await client.close()


app = FastAPI(
    title="HR Link Talantix BI API",
    description="REST/JSON facade over Talantix GraphQL API for Power BI.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(TalantixError)
async def talantix_error_handler(_: Request, exc: TalantixError) -> JSONResponse:
    status_code = exc.status_code if 400 <= exc.status_code < 500 else 502
    return JSONResponse(
        status_code=status_code,
        content={
            "error": exc.message,
            "details": exc.details,
            "talantix_request_id": exc.request_id,
        },
    )


@app.exception_handler(CacheNotReadyError)
async def cache_not_ready_handler(request: Request, exc: CacheNotReadyError) -> JSONResponse:
    cache: BIDataCache = request.app.state.bi_cache
    return JSONResponse(
        status_code=503,
        content={
            "error": str(exc),
            "sync_status": cache.status(),
        },
    )


def get_service(request: Request) -> TalantixBIService:
    return request.app.state.bi_service


def get_client(request: Request) -> TalantixClient:
    return request.app.state.talantix_client


def get_cache(request: Request) -> BIDataCache:
    return request.app.state.bi_cache


def require_api_key(
    request: Request,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    api_key: str | None = Query(default=None),
) -> None:
    settings: Settings = request.app.state.settings
    configured_tokens = {token for token in (settings.service_api_key, settings.powerbi_bearer_token) if token}
    if not configured_tokens:
        return

    bearer_token = _extract_bearer_token(authorization)
    provided_tokens = {token for token in (x_api_key, api_key, bearer_token) if token}
    if configured_tokens.intersection(provided_tokens):
        return
    raise HTTPException(status_code=401, detail="Invalid or missing API key")


ApiKeyDependency = Depends(require_api_key)
ServiceDependency = Annotated[TalantixBIService, Depends(get_service)]
ClientDependency = Annotated[TalantixClient, Depends(get_client)]
CacheDependency = Annotated[BIDataCache, Depends(get_cache)]


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"ok": True}


@app.get("/api/v1/auth/check", dependencies=[ApiKeyDependency])
async def auth_check(client: ClientDependency) -> dict[str, Any]:
    return await client.auth_check()


@app.post("/api/v1/graphql", dependencies=[ApiKeyDependency])
async def graphql_proxy(payload: GraphQLRequest, client: ClientDependency) -> dict[str, Any]:
    return await client.execute(payload.query, payload.variables, payload.operation_name)


@app.get("/api/v1/vacancies", dependencies=[ApiKeyDependency])
async def vacancies(
    service: ServiceDependency,
    vacancy_id: str | None = Query(default=None, description="Comma-separated Talantix vacancy IDs"),
    status: str | None = Query(default=None, description="Talantix VacancyStatus, for example ACTIVE"),
    department: str | None = Query(default=None, description="Comma-separated department names"),
    area_id: str | None = Query(default=None, description="Comma-separated area IDs"),
    vacancy_title: str | None = None,
    page_size: int | None = Query(default=None, ge=1, le=50),
    max_pages: int | None = Query(default=None, ge=1),
) -> dict[str, Any]:
    return await service.list_vacancies(
        **vacancy_filter_params(
            vacancy_id=vacancy_id,
            status=status,
            department=department,
            area_id=area_id,
            vacancy_title=vacancy_title,
        ),
        page_size=page_size,
        max_pages=max_pages,
    )


@app.get("/api/v1/workflow-stages", dependencies=[ApiKeyDependency])
async def workflow_stages(
    service: ServiceDependency,
    vacancy_id: str | None = Query(default=None, description="Comma-separated Talantix vacancy IDs"),
    status: str | None = Query(default=None, description="Talantix VacancyStatus, for example ACTIVE"),
    department: str | None = Query(default=None, description="Comma-separated department names"),
    page_size: int | None = Query(default=None, ge=1, le=50),
    max_pages: int | None = Query(default=None, ge=1),
) -> dict[str, Any]:
    return await service.list_workflow_stages(
        vacancy_ids=parse_csv_int(vacancy_id),
        status=status,
        departments=parse_csv(department),
        page_size=page_size,
        max_pages=max_pages,
    )


@app.get("/api/v1/responses", dependencies=[ApiKeyDependency])
async def responses(
    service: ServiceDependency,
    workflow_status_id: int | None = None,
    vacancy_id: str | None = Query(default=None, description="Comma-separated Talantix vacancy IDs"),
    vacancy_status: str | None = Query(default=None, description="Talantix VacancyStatus, for example ACTIVE"),
    department: str | None = Query(default=None, description="Comma-separated department names"),
    include_history: bool = False,
    history_first: int = Query(default=20, ge=1, le=100),
    unread: str | None = Query(default=None, description="UnreadFilter enum value"),
    area_id: str | None = Query(default=None, description="Comma-separated area IDs"),
    citizenship_id: str | None = None,
    gender: str | None = None,
    education_level_id: str | None = None,
    page_size: int | None = Query(default=None, ge=1, le=50),
    max_pages: int | None = Query(default=None, ge=1),
    max_stages: int | None = Query(default=None, ge=1),
) -> dict[str, Any]:
    response_filter = compact_dict(
        {
            "unread": unread,
            "areaIds": parse_csv(area_id),
            "citizenshipId": citizenship_id,
            "gender": gender,
            "educationLevelId": education_level_id,
        }
    )
    return await service.list_responses(
        workflow_status_id=workflow_status_id,
        vacancy_ids=parse_csv_int(vacancy_id),
        vacancy_status=vacancy_status,
        departments=parse_csv(department),
        response_filter=response_filter or None,
        include_history=include_history,
        history_first=history_first,
        page_size=page_size,
        max_pages=max_pages,
        max_stages=max_stages,
    )


@app.get("/api/v1/funnel", dependencies=[ApiKeyDependency])
async def funnel(
    service: ServiceDependency,
    vacancy_id: str | None = Query(default=None, description="Comma-separated Talantix vacancy IDs"),
    vacancy_status: str | None = Query(default=None, description="Talantix VacancyStatus, for example ACTIVE"),
    department: str | None = Query(default=None, description="Comma-separated department names"),
    include_responses: bool = True,
    include_history: bool = False,
    history_first: int = Query(default=20, ge=1, le=100),
    page_size: int | None = Query(default=None, ge=1, le=50),
    max_pages: int | None = Query(default=None, ge=1),
    max_stages: int | None = Query(default=None, ge=1),
) -> dict[str, Any]:
    return await service.funnel(
        vacancy_ids=parse_csv_int(vacancy_id),
        vacancy_status=vacancy_status,
        departments=parse_csv(department),
        include_responses=include_responses,
        include_history=include_history,
        history_first=history_first,
        page_size=page_size,
        max_pages=max_pages,
        max_stages=max_stages,
    )


@app.get("/api/v1/bi/export", dependencies=[ApiKeyDependency])
async def bi_export(
    cache: CacheDependency,
    updated_from: str | None = Query(
        default=None,
        description="Return rows updated from this date/datetime. Supports YYYY-MM-DD, ISO datetime, Unix seconds/ms.",
    ),
    refresh: bool = Query(default=False, description="Synchronize Talantix before returning cached data."),
) -> dict[str, Any]:
    if refresh:
        try:
            await cache.sync_once(force=True)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"BI sync failed: {exc}") from exc
    try:
        return await cache.get(updated_from=updated_from)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid updated_from: {updated_from}") from exc


@app.get("/api/v1/bi/sync/status", dependencies=[ApiKeyDependency])
async def bi_sync_status(cache: CacheDependency) -> dict[str, Any]:
    return cache.status()


@app.post("/api/v1/bi/sync", dependencies=[ApiKeyDependency])
async def bi_sync(
    cache: CacheDependency,
    force: bool = Query(default=False, description="If a sync is already running, wait and start another one after it."),
    page_size: int | None = Query(default=None, ge=1, le=50),
    person_page_size: int | None = Query(default=None, ge=1, le=50),
    max_pages: int | None = Query(default=None, ge=1),
    max_stages: int | None = Query(default=None, ge=1),
    history_first: int | None = Query(default=None, ge=1, le=100),
) -> dict[str, Any]:
    try:
        return await cache.sync_once(
            force=force,
            page_size=page_size,
            person_page_size=person_page_size,
            max_pages=max_pages,
            max_stages=max_stages,
            history_first=history_first,
        )
    except TalantixError:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"BI sync failed: {exc}") from exc


@app.get("/api/v1/bi/export/live", dependencies=[ApiKeyDependency])
async def bi_export_live(
    service: ServiceDependency,
    vacancy_id: str | None = Query(default=None, description="Comma-separated Talantix vacancy IDs"),
    vacancy_status: str | None = Query(default=None, description="Talantix VacancyStatus, for example ACTIVE"),
    department: str | None = Query(default=None, description="Comma-separated department names"),
    include_responses: bool = True,
    include_history: bool = True,
    include_persons: bool = True,
    include_dictionaries: bool = True,
    include_reference_data: bool = True,
    history_first: int = Query(default=20, ge=1, le=100),
    lean_persons: bool = Query(default=True, description="Use lightweight person fields that fit Talantix complexity limits."),
    page_size: int | None = Query(default=None, ge=1, le=50),
    person_page_size: int | None = Query(default=None, ge=1, le=50),
    max_pages: int | None = Query(default=None, ge=1),
    max_stages: int | None = Query(default=None, ge=1),
) -> dict[str, Any]:
    return await service.bi_export(
        vacancy_ids=parse_csv_int(vacancy_id),
        vacancy_status=vacancy_status,
        departments=parse_csv(department),
        include_responses=include_responses,
        include_history=include_history,
        include_persons=include_persons,
        include_dictionaries=include_dictionaries,
        include_reference_data=include_reference_data,
        history_first=history_first,
        lean_persons=lean_persons,
        page_size=page_size,
        person_page_size=person_page_size,
        max_pages=max_pages,
        max_stages=max_stages,
    )


@app.get("/api/v1/persons", dependencies=[ApiKeyDependency])
async def persons(
    service: ServiceDependency,
    search: str | None = None,
    source_id: str | None = Query(default=None, description="Comma-separated source IDs"),
    vacancy_id: str | None = Query(default=None, description="Comma-separated vacancy IDs"),
    wf_status_name: str | None = Query(default=None, description="Comma-separated status names"),
    current_wf_status_name: str | None = Query(default=None, description="Comma-separated current status names"),
    discard_reason_id: str | None = Query(default=None, description="Comma-separated discard reason IDs"),
    discard_type: str | None = None,
    include_history: bool = False,
    history_first: int = Query(default=20, ge=1, le=100),
    lean: bool = Query(default=True, description="Use lightweight person fields that fit Talantix complexity limits."),
    page_size: int | None = Query(default=None, ge=1, le=50),
    max_pages: int | None = Query(default=None, ge=1),
) -> dict[str, Any]:
    return await service.list_persons(
        **person_filter_params(
            search=search,
            source_id=source_id,
            vacancy_id=vacancy_id,
            wf_status_name=wf_status_name,
            current_wf_status_name=current_wf_status_name,
            discard_reason_id=discard_reason_id,
            discard_type=discard_type,
        ),
        include_history=include_history,
        history_first=history_first,
        lean=lean,
        page_size=page_size,
        max_pages=max_pages,
    )


@app.get("/api/v1/person-sources", dependencies=[ApiKeyDependency])
async def person_sources(
    service: ServiceDependency,
    filter_by_name: str | None = None,
    page_size: int | None = Query(default=None, ge=1, le=50),
    max_pages: int | None = Query(default=None, ge=1),
) -> dict[str, Any]:
    return await service.list_person_sources(
        filter_by_name=filter_by_name,
        page_size=page_size,
        max_pages=max_pages,
    )


@app.get("/api/v1/dictionaries", dependencies=[ApiKeyDependency])
async def dictionaries(service: ServiceDependency) -> dict[str, Any]:
    return await service.dictionaries()


@app.get("/api/v1/managers", dependencies=[ApiKeyDependency])
async def managers(
    service: ServiceDependency,
    search_by_name: str | None = None,
    search_by_email: str | None = None,
    role: str | None = Query(default=None, description="Comma-separated ManagerRole enum values"),
    page_size: int | None = Query(default=None, ge=1, le=50),
    max_pages: int | None = Query(default=None, ge=1),
) -> dict[str, Any]:
    return await service.list_managers(
        search_by_name=search_by_name,
        search_by_email=search_by_email,
        roles=parse_csv(role),
        page_size=page_size,
        max_pages=max_pages,
    )


@app.get("/api/v1/hiring-requests", dependencies=[ApiKeyDependency])
async def hiring_requests(
    service: ServiceDependency,
    status: str | None = Query(default=None, description="Comma-separated HiringRequestStatus enum values"),
    page_size: int | None = Query(default=None, ge=1, le=50),
    max_pages: int | None = Query(default=None, ge=1),
) -> dict[str, Any]:
    return await service.list_hiring_requests(
        statuses=parse_csv(status),
        page_size=page_size,
        max_pages=max_pages,
    )


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()
