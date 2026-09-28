from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração lida de variáveis de ambiente (.env em dev, variáveis do
    provedor de hospedagem em produção — nunca commitadas)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    # Preenchido na Fase 2 (deploy real) com a connection string do Supabase.
    # Ausente em dev local até então — o app roda sem banco até a Fase 3.
    database_url: str | None = None
    # Fase 4: só usados uma vez, para criar o primeiro Admin Superior quando
    # ainda não existe nenhum usuário com papel_global no banco (ver
    # app/db.py `_bootstrap_admin` e README.md). Depois do primeiro login,
    # os demais usuários são criados por `POST /usuarios` — pode remover
    # essas variáveis do Render sem afetar nada.
    admin_bootstrap_email: str | None = None
    admin_bootstrap_senha: str | None = None
    # Fase 6 (2026-09-28): pop-up de suporte, envia por SMTP direto — sem
    # essas três variáveis (host/usuário/senha), o botão continua aparecendo
    # mas o envio recusa com um erro amigável (ver services/suporte.py).
    # `smtp_remetente` é opcional: se vazio, usa o próprio `smtp_usuario`
    # como remetente (comum quando o provedor exige que From == usuário
    # autenticado, como Gmail).
    smtp_host: str | None = None
    smtp_porta: int = 587
    smtp_usuario: str | None = None
    smtp_senha: str | None = None
    smtp_remetente: str | None = None
    smtp_destinatario_suporte: str = "claracosta@elitemediacoes.com.br"


settings = Settings()
