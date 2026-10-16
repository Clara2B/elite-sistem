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
    # Fase 1 — Solicitação de Audiência (2026-10-16): acesso à planilha de
    # controle (Google Sheets) via conta de serviço do Google, a pedido da
    # Clara. `google_service_account_json` é o conteúdo inteiro do arquivo
    # .json da conta de serviço (não um caminho de arquivo); gerado pela
    # própria Clara no Google Cloud Console (ver ARCHITECTURE.md/DECISIONS.md
    # — não existia nenhuma integração com Google antes disso). O e-mail da
    # conta de serviço (dentro do .json) precisa estar com permissão de
    # Editor na planilha. `google_sheets_id` é o ID da planilha (o trecho
    # entre /d/ e /edit na URL) — em dev/teste, a cópia com dados fictícios;
    # em produção, a planilha real.
    google_service_account_json: str | None = None
    google_sheets_id: str | None = None
    # Envio das Cartas Convite por e-mail (Fase 1, 2026-10-16) — provedor
    # escolhido pela Clara depois do histórico de três tentativas
    # fracassadas no pop-up de suporte (ver DISCORD_WEBHOOK_SUPORTE acima):
    # Postmark é API HTTPS (não depende de porta SMTP, que foi o primeiro
    # bloqueio) e tem reputação de IP diferente da Resend (não repete
    # necessariamente o bloqueio do Cloudflare visto antes).
    # `postmark_remetente` precisa ser um e-mail com Sender Signature (ou
    # domínio) verificado na conta Postmark.
    #
    # Modo de teste (a pedido explícito da Clara: "nenhum email real deve
    # ser enviado durante o desenvolvimento e os testes") — `False` por
    # padrão, de propósito: só manda pra destinatário de verdade quando
    # alguém liga EMAIL_ENVIO_REAL=true explicitamente no Render. Em modo
    # de teste, o e-mail é enviado de verdade (não só uma simulação) mas
    # SEMPRE pra `email_destinatario_teste`, nunca pro cliente/banco.
    postmark_server_token: str | None = None
    postmark_remetente: str | None = None
    email_envio_real: bool = False
    email_destinatario_teste: str | None = None


settings = Settings()
