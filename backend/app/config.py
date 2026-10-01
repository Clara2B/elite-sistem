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
    # Fase 6 (2026-09-28): pop-up de suporte. Três tentativas de enviar por
    # e-mail não vingaram em produção — SMTP bloqueado pelo Render, depois a
    # API HTTP da Resend bloqueada pelo Cloudflare, depois o domínio
    # elitemediacoes.com.br não verificando na Resend (mesmo em duas
    # tentativas da Clara) — ver DECISIONS.md 2026-10-01. Trocado pra
    # guardar o chamado direto no banco (sempre funciona, nenhum provedor
    # externo envolvido — ver services/suporte.py e a tela de Configuração
    # > Chamados). `discord_webhook_suporte` é só um aviso complementar,
    # opcional: sem ele, o chamado continua sendo salvo normalmente, só não
    # avisa ninguém na hora.
    discord_webhook_suporte: str | None = None


settings = Settings()
