from typing import Any

from pydantic import BaseModel, Field


class GraphQLRequest(BaseModel):
    query: str
    variables: dict[str, Any] | None = None
    operation_name: str | None = Field(default=None, alias="operationName")


class ApiEnvelope(BaseModel):
    items: list[dict[str, Any]]
    count: int
    meta: dict[str, Any] = Field(default_factory=dict)

