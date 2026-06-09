import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _env_first(*names: str) -> str | None:
    for name in names:
        val = os.environ.get(name, "").strip()
        if val:
            return val
    return None


class MetaSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    meta_access_token: str | None = Field(default=None, alias="META_ACCESS_TOKEN")
    meta_app_id: str | None = Field(default=None, alias="META_APP_ID")
    meta_app_secret: str | None = Field(default=None, alias="META_APP_SECRET")
    meta_ad_account_id: str | None = Field(default=None, alias="META_AD_ACCOUNT_ID")
    ig_user_id: str | None = Field(default=None, alias="IG_USER_ID")
    fb_page_id: str | None = Field(default=None, alias="FB_PAGE_ID")
    wa_token: str | None = Field(default=None, alias="WA_TOKEN")
    wa_phone_number_id: str | None = Field(default=None, alias="WA_PHONE_NUMBER_ID")

    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-4-20250514", alias="ANTHROPIC_MODEL")

    delegado_ai_provider: str = Field(default="ollama", alias="DELEGADO_AI_PROVIDER")
    delegado_ai_model: str | None = Field(default=None, alias="DELEGADO_AI_MODEL")
    delegado_ollama_model: str = Field(default="llama3.2:3b", alias="DELEGADO_OLLAMA_MODEL")

    supabase_url: str | None = Field(default=None, alias="SUPABASE_URL")
    supabase_anon_key: str | None = Field(default=None, alias="SUPABASE_ANON_KEY")
    supabase_service_role_key: str | None = Field(default=None, alias="SUPABASE_SERVICE_ROLE_KEY")

    allowed_emails: str = Field(
        default="infinity.shop288@gmail.com",
        alias="DELEGADO_ALLOWED_EMAILS",
        description="Lista separada por vírgula de e-mails autorizados no dashboard.",
    )

    api_cors_origins: str = Field(
        default="http://127.0.0.1:8765,http://localhost:8765,https://www.naintegracursos.com.br",
        alias="DELEGADO_CORS_ORIGINS",
    )

    delegado_schema: str = Field(default="delegado", alias="DELEGADO_SCHEMA")

    @property
    def supabase_url_resolved(self) -> str | None:
        return self.supabase_url or _env_first("LEX_AGENT_SUPABASE_URL", "SUPABASE_URL")

    @property
    def supabase_key_resolved(self) -> str:
        return (
            self.supabase_service_role_key
            or _env_first("SUPABASE_SERVICE_ROLE_KEY", "LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY")
            or self.supabase_anon_key
            or _env_first("SUPABASE_ANON_KEY")
            or ""
        )

    @property
    def allowed_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.allowed_emails.split(",") if e.strip()}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]
