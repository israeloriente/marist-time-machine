from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(alias="DATABASE_URL")
    jwt_secret: str = Field(alias="JWT_SECRET")

    supabase_url: str = Field(default="http://kong:8000", alias="SUPABASE_URL")
    # Public URL of Supabase (used in signed URLs returned to the browser).
    # Falls back to supabase_url if not set.
    supabase_public_url: str = Field(default="", alias="SUPABASE_PUBLIC_URL")
    supabase_service_key: str = Field(alias="SUPABASE_SERVICE_KEY")

    ml_internal_url: str = Field(default="http://ml:8081", alias="ML_INTERNAL_URL")

    cluster_max_distance: float = Field(default=0.5, alias="CLUSTER_MAX_DISTANCE")
    cluster_min_faces: int = Field(default=3, alias="CLUSTER_MIN_FACES")

    # Stored as raw string; expose .cors_origins_list to consumers.
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")

    @property
    def cors_origins_list(self) -> list[str]:
        return [s.strip() for s in self.cors_origins.split(",") if s.strip()] or ["*"]


@lru_cache
def settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
