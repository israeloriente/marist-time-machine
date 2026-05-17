from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(alias="DATABASE_URL")
    jwt_secret: str = Field(alias="JWT_SECRET")

    supabase_url: str = Field(default="http://kong:8000", alias="SUPABASE_URL")
    supabase_service_key: str = Field(alias="SUPABASE_SERVICE_KEY")

    ml_internal_url: str = Field(default="http://ml:8081", alias="ML_INTERNAL_URL")

    cluster_max_distance: float = Field(default=0.5, alias="CLUSTER_MAX_DISTANCE")
    cluster_min_faces: int = Field(default=3, alias="CLUSTER_MIN_FACES")

    cors_origins: list[str] = Field(default_factory=lambda: ["*"], alias="CORS_ORIGINS")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, v):
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v


@lru_cache
def settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
