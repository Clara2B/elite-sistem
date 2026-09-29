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
    # Fase 6 (2026-09-28): pop-up de suporte. Primeira versão enviava por
    # SMTP direto (smtplib) — trocado em 2026-09-29 pra API HTTP da Resend
    # depois de confirmar, em produção, que o Render derruba/bloqueia
    # conexão de saída por SMTP (primeiro "[Errno 101] Network is
    # unreachable", depois "timed out" mesmo forçando IPv4 — sintoma de
    # firewall de saída, não bug de código; ver DECISIONS.md 2026-09-29).
    # Sem `resend_api_key`, o botão continua aparecendo mas o envio recusa
    # com um erro amigável (ver services/suporte.py). `resend_remetente`
    # usa o endereço de teste da própria Resend por padrão — funciona sem
    # precisar verificar um domínio próprio; troque depois de verificar
    # elitemediacoes.com.br no painel da Resend, se quiser.
    resend_api_key: str | None = None
    resend_remetente: str = "Elite Sistem <onboarding@resend.dev>"
    destinatario_suporte: str = "claracosta@elitemediacoes.com.br"


settings = Settings()
