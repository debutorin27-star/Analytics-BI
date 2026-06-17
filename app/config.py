from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    talantix_base_url: str = "https://api.talantix.ru"
    talantix_access_token: str | None = None
    talantix_refresh_token: str | None = None
    talantix_token_file: str | None = ".talantix_tokens.json"
    talantix_user_agent: str = "HR Link BI Integration"
    talantix_page_size: int = Field(default=20, ge=1, le=50)
    talantix_vacancy_page_size: int = Field(default=50, ge=1, le=200)
    talantix_max_pages: int | None = Field(default=None, ge=1, le=100000)
    talantix_concurrency: int = Field(default=5, ge=1, le=20)

    service_api_key: str | None = None
    powerbi_bearer_token: str | None = None

    sync_enabled: bool = True
    sync_on_startup: bool = True
    sync_interval_seconds: int = Field(default=3600, ge=60)
    bi_cache_file: str = "data/talantix_bi_export.json"
    bi_sync_page_size: int = Field(default=20, ge=1, le=50)
    bi_sync_person_page_size: int = Field(default=5, ge=1, le=50)
    bi_sync_max_pages: int | None = Field(default=None, ge=1)
    bi_sync_max_stages: int | None = Field(default=None, ge=1)
    bi_sync_history_first: int = Field(default=20, ge=1, le=100)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("talantix_max_pages", "bi_sync_max_pages", "bi_sync_max_stages", mode="before")
    @classmethod
    def empty_string_to_none(cls, value: object) -> object:
        return None if value == "" else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
