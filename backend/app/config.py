from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração lida de variáveis de ambiente (.env em dev, variáveis do
    provedor de hospedagem em produção — nunca commitadas)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    # Preenchido na Fase 2 (deploy real) com a connection string do Supabase.
    # Ausente em dev local até então — o app roda sem banco até a Fase 3.
    database_url: str | None = None


settings = Settings()
